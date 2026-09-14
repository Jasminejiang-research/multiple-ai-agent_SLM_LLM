"""Append-only fsynced S2 events plus optional existing SQLite JSON-column projection."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

EVENT_VERSION = "review-events-v1-s2"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class EventJournal:
    """A new run owns a new directory. Existing runs require explicit S4 reconciliation."""
    def __init__(self, directory, run_id, *, session_factory=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.path = self.directory / "events.jsonl"
        self.run_id = run_id
        self.session_factory = session_factory
        self._lock = Lock()
        self._ids = set()
        self.events = []

    def emit(self, kind, payload, *, event_id=None):
        if kind in ("call", "handoff"):
            from schemas.review_events import CallEventPayload, ExpectedHandoff
            schema = CallEventPayload if kind == "call" else ExpectedHandoff
            payload = schema.model_validate(payload).model_dump(mode="json")
        # Serialize/copy before dispatch; no credentials or provider exception bodies are stored.
        event = json.loads(json.dumps(dict(event_version=EVENT_VERSION, event_id=event_id or str(uuid4()),
            run_id=self.run_id, kind=kind, occurred_at_utc=utc_now(), payload=payload), allow_nan=False))
        with self._lock:
            if event["event_id"] in self._ids:
                return
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            self._ids.add(event["event_id"])
            self.events.append(event)
            if self.session_factory:
                from storage.repositories import save_node_output, save_agent_output, save_error
                with self.session_factory() as session:
                    save_node_output(session, run_id=self.run_id, node_name=f"s2.{kind}", output_snapshot=event)
                    if kind in ("artifact", "critique"):
                        body = event["payload"]
                        role = body["artifact"]["role"] if kind == "artifact" else body["role"]
                        save_agent_output(session, run_id=self.run_id, agent_name=role,
                            output_type=f"s2.{kind}", output_payload=body)
                    if kind == "failure":
                        body = event["payload"]
                        save_error(session, run_id=self.run_id, error_type=body["error_type"],
                            error_message=body["status"], step_name=body["node"])
                    session.commit()
        return event


def replay_events(path):
    """Idempotent reduction; an unclosed dispatch remains unknown, never 'not called'."""
    events, seen, attempts, handoffs = [], set(), {}, {}
    truncated_tail = False
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            if index != len(lines) - 1:
                raise
            truncated_tail = True
            break
        if event["event_id"] in seen:
            continue
        seen.add(event["event_id"])
        events.append(event)
        data = event["payload"]
        if event["kind"] == "call":
            attempts[data["attempt_id"]] = data
        if event["kind"] == "handoff":
            handoffs[data["handoff_id"]] = data
    for key, attempt in list(attempts.items()):
        if attempt["status"] == "dispatching":
            attempts[key] = {**attempt, "status": "interrupted_unknown", "usage_missing_reason": "dispatch has no durable completion"}
    return dict(events=events, attempts=list(attempts.values()), handoffs=list(handoffs.values()),
                truncated_tail=truncated_tail, automatic_resume_allowed=False)
