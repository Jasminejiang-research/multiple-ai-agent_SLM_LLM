"""Bounded single-dispatch controller shared by all S2 roles, batches and providers."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from dataclasses import dataclass
import json
import os
from pathlib import Path
from queue import Queue, Empty
from threading import Event, Thread
import time
from uuid import uuid4

from pydantic import BaseModel
from schemas.evidence import canonical_hash
from workflow.llm_client import StructuredOutputValidationError
from workflow.review_events import utc_now
from workflow.run_budget import RunBudget, RunBudgetExceededError


class RunCancelled(RuntimeError): pass
class WallClockExceeded(TimeoutError): pass
class ProviderBusy(RuntimeError): pass
class SharedBudgetStop(RuntimeError): pass


class ProviderFailure(RuntimeError):
    def __init__(self, error_type, *, retryable=False, request_finished=False):
        super().__init__(error_type)
        self.error_type = error_type
        self.retryable = retryable
        self.request_finished = request_finished


@dataclass(frozen=True)
class PhysicalRequest:
    prompt: str
    schema: type[BaseModel]
    system_instruction: str | None
    temperature: int
    max_output_tokens: int
    timeout_seconds: float


@dataclass(frozen=True)
class PhysicalResponse:
    text: str
    usage_raw: dict | None = None
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None


class LocalRequestLease:
    """Cross-process lease keyed by endpoint, across all runs/models on that server.

    A crashed/abandoned request leaves a marker. S3 must confirm server idle and
    explicitly reconcile it; waiting for our worker thread alone is insufficient.
    """
    def __init__(self, directory, endpoint):
        self.path = Path(directory) / (canonical_hash(endpoint) + ".lease.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.owned = False

    def acquire(self, run_id, attempt_id):
        try:
            with self.path.open("x", encoding="utf-8") as stream:
                json.dump(dict(run_id=run_id, attempt_id=attempt_id, status="inflight_or_unknown"), stream)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as exc:
            raise ProviderBusy("local endpoint has an inflight/unknown request; confirm server idle before reconciliation") from exc
        self.owned = True

    def release_finished(self):
        if self.owned:
            self.path.unlink()
            self.owned = False


_ATTEMPT = ContextVar("s2_attempt", default=None)


class BoundedClient:
    """Provider must implement exactly one physical invoke(request), with SDK retries disabled.

    Token reservations use UTF-8 byte lengths of prompt/system/schema plus the
    output cap (conservative estimate, not a provider token measurement). Missing
    usage retains that charge. Actual usage always stays null when unavailable.
    """
    def __init__(self, provider, config, journal, *, cancel=None, clock=time.monotonic,
                 local_lease=None, planned_id=None):
        if config.provider != provider.provider or config.model_exact_id != provider.model_exact_id:
            raise ValueError("provider identity must match explicit run configuration")
        if config.provider == "local" and local_lease is None:
            raise ValueError("local provider requires a shared endpoint lease")
        self.provider, self.config, self.journal = provider, config, journal
        self.cancel = cancel if cancel is not None else Event()
        self.clock, self.local_lease, self.planned_id = clock, local_lease, planned_id
        self.budget = RunBudget(max_requests=config.max_requests, max_total_tokens=config.max_total_tokens)
        self.started = clock()
        self.node_started = None
        self.node_scope_id = None
        self.input_refs = []
        self.attempt_counts = {}
        self.first_physical_pass = {}
        self.last_attempt = None
        self.usage_missing_calls = 0
        self.actual_prompt_tokens = 0
        self.actual_output_tokens = 0
        self.actual_total_tokens = 0
        self.structure_repair_request_count = 0
        self.revision_request_count = 0

    def snapshot(self):
        budget = self.budget.snapshot()
        charge = budget.pop("total_tokens")
        budget.pop("prompt_tokens")
        budget.pop("output_tokens")
        return {**budget, "charged_total_tokens": charge, "token_counter_basis": "budget_charge_actual_or_retained_estimate",
            "actual_prompt_tokens_known": self.actual_prompt_tokens,
            "actual_output_tokens_known": self.actual_output_tokens,
            "actual_total_tokens_known": self.actual_total_tokens, "usage_missing_calls": self.usage_missing_calls,
            "transport_retry_count": self.budget.snapshot()["retry_count"],
            "structure_repair_request_count": self.structure_repair_request_count,
            "revision_request_count": self.revision_request_count,
            "run_elapsed_seconds": self.clock() - self.started,
            "node_elapsed_seconds": None if self.node_started is None else self.clock() - self.node_started,
            "node_scope_id": self.node_scope_id}

    def check(self):
        if self.cancel.is_set():
            raise RunCancelled("run cancellation requested")
        now = self.clock()
        remaining = self.config.run_seconds - (now - self.started)
        if self.node_started is not None:
            remaining = min(remaining, self.config.node_seconds - (now - self.node_started))
        if remaining <= 0:
            raise WallClockExceeded("shared node/run wall-clock budget exhausted")
        return remaining

    def begin_node(self, role):
        if self.node_started is not None:
            raise RuntimeError("cannot reset a parent node clock for a nested batch/critic/revision")
        self.check()
        self.node_scope_id = f"{self.journal.run_id}.{role}"
        self.node_started = self.clock()
        self.journal.emit("node", dict(node_scope_id=self.node_scope_id, status="started", budget=self.snapshot()))

    def end_node(self, status):
        self.journal.emit("node", dict(node_scope_id=self.node_scope_id, status=status, budget=self.snapshot()))
        if status == "completed":
            self.check()
        self.node_started = None
        self.node_scope_id = None

    @contextmanager
    def attempt_scope(self, **metadata):
        token = _ATTEMPT.set(metadata)
        self.last_attempt = None
        outcome = {}
        try:
            yield outcome
        except BaseException as exc:
            self.journal.emit("contract_check", dict(**metadata, attempt_id=self.last_attempt,
                passed=False, error_type=type(exc).__name__))
            raise
        else:
            self.journal.emit("contract_check", dict(**metadata, attempt_id=self.last_attempt, passed=True, error_type=None))
        finally:
            outcome["first_physical_attempt_passed"] = self.first_physical_pass.get(metadata["logical_task_id"])
            _ATTEMPT.reset(token)

    def _wait(self, request):
        queue = Queue(maxsize=1)
        copied = copy_context()
        def dispatch():
            try:
                queue.put((True, copied.run(self.provider.invoke, request)))
            except BaseException as exc:
                queue.put((False, exc))
        worker = Thread(target=dispatch, daemon=True)
        worker.start()
        deadline = self.clock() + request.timeout_seconds
        while True:
            self.check()
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise WallClockExceeded("physical request deadline reached; dispatch outcome may be unknown")
            try:
                ok, result = queue.get(timeout=min(.05, remaining))
            except Empty:
                continue
            if ok:
                return result
            raise result

    def _charge(self, response, estimate, event):
        fields = ("prompt_tokens", "output_tokens", "total_tokens")
        counts = [getattr(response, f, None) for f in fields]
        if any(v is not None and (type(v) is not int or v < 0) for v in counts):
            counts = [None, None, None]
        prompt, output, total = counts
        if total is not None and total < (prompt or 0) + (output or 0):
            counts = [None, None, None]
            prompt, output, total = counts
        event.update(zip(fields, counts))
        event["usage_raw"] = None if response is None else response.usage_raw
        missing = any(v is None for v in counts)
        event["usage_missing_reason"] = "provider usage missing or incomplete; reservation retained where total is unknown" if missing else None
        self.usage_missing_calls += int(missing)
        self.actual_prompt_tokens += prompt or 0
        self.actual_output_tokens += output or 0
        self.actual_total_tokens += total or 0
        charge = total if total is not None else max(estimate, (prompt or 0) + (output or 0))
        self.budget.record_usage(total_tokens=charge)
        event["budget_token_charge"] = charge

    def generate_structured_once(self, prompt, schema, *, temperature=0, system_instruction=None, output_validator=None):
        metadata = _ATTEMPT.get()
        if metadata is None or self.node_started is None:
            raise RuntimeError("S2 physical calls require a logical task and parent node scope")
        if temperature != 0:
            raise ValueError("common temperature is frozen at zero")
        combined = prompt + (system_instruction or "")
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        estimate = len((combined + schema_json).encode("utf-8")) + self.config.max_output_tokens
        if len(combined) > self.config.max_prompt_chars:
            self.journal.emit("blocked_task", dict(**metadata, reason="prompt_limit"))
            raise SharedBudgetStop("shared prompt cap exceeded")
        retry_of = None
        for transport_index in range(self.config.transport_retries + 1):
            attempt_id = str(uuid4())
            acquired = False
            try:
                remaining = self.check()
                if self.local_lease:
                    self.local_lease.acquire(self.journal.run_id, attempt_id)
                    acquired = True
                before = self.snapshot()
                self.budget.reserve_request(estimated_tokens=estimate)
            except Exception as exc:
                if acquired:
                    self.local_lease.release_finished()
                self.journal.emit("blocked_task", dict(**metadata, reason=type(exc).__name__, budget=self.snapshot()))
                raise
            logical_id = metadata["logical_task_id"]
            self.attempt_counts[logical_id] = self.attempt_counts.get(logical_id, 0) + 1
            started = self.clock()
            event = dict(run_id=self.journal.run_id, planned_id=self.planned_id, run_kind=self.config.run_kind,
                logical_task_id=logical_id, node_scope_id=self.node_scope_id, batch_id=metadata["batch_number"],
                attempt_id=attempt_id, attempt_index=self.attempt_counts[logical_id],
                role="Revision" if metadata["task_purpose"] == "revision" else metadata["role"],
                task_role=metadata["role"], purpose=metadata["purpose"], task_purpose=metadata["task_purpose"],
                transport_retry_of=retry_of, provider=self.config.provider, model_exact_id=self.config.model_exact_id,
                model_config_version=self.config.model_config_version, config_sha256=self.config.sha256,
                prompt_hash=canonical_hash(dict(prompt=prompt, system_instruction=system_instruction)),
                schema_hash=metadata["schema_sha256"], evidence_hash=metadata["packet_sha256"],
                input_artifact_refs=self.input_refs, output_artifact_ref=None,
                started_at_utc=utc_now(), ended_at_utc=None, elapsed_seconds=None,
                status="dispatching", error_type=None, usage_raw=None, prompt_tokens=None,
                output_tokens=None, total_tokens=None, usage_missing_reason="request not completed",
                budget_before=before, budget_after=self.snapshot(), reservation_tokens=estimate)
            self.last_attempt = attempt_id
            if transport_index:
                self.budget.record_retry()
            self.structure_repair_request_count += int(metadata["purpose"] == "structure_repair")
            self.revision_request_count += int(metadata["task_purpose"] == "revision")
            # Both JSONL and optional SQLite commit must succeed before provider dispatch.
            self.journal.emit("call", event)
            response = None
            error = None
            confirmed_finished = False
            try:
                request = PhysicalRequest(prompt, schema, system_instruction, 0, self.config.max_output_tokens,
                    min(remaining, self.check(), self.config.request_seconds))
                response = self._wait(request)
                confirmed_finished = True
                if not isinstance(response, PhysicalResponse):
                    response = None
                    raise TypeError("provider must return PhysicalResponse")
                event["raw_output"] = response.text
                event["finish_reason"] = response.finish_reason
                if response.finish_reason in ("length", "MAX_TOKENS"):
                    raise StructuredOutputValidationError("provider output truncated", raw_output=response.text)
                try:
                    candidate = schema.model_validate_json(response.text)
                except ValueError as exc:
                    raise StructuredOutputValidationError("provider JSON/schema validation failed", raw_output=response.text) from exc
                if output_validator:
                    output_validator(candidate)
                event["output_artifact_ref"] = dict(sha256=canonical_hash(candidate.model_dump(mode="json")), kind="physical_response")
                event["status"] = "succeeded"
            except BaseException as exc:
                error = exc
                confirmed_finished = confirmed_finished or (isinstance(exc, ProviderFailure) and exc.request_finished)
                event["status"] = ("cancelled" if isinstance(exc, (RunCancelled, KeyboardInterrupt)) else
                    "timeout" if isinstance(exc, TimeoutError) else "invalid_output" if isinstance(exc, StructuredOutputValidationError) else "failed")
                event["error_type"] = getattr(exc, "error_type", type(exc).__name__)
            finally:
                # Native diagnostics include partial/error responses, once per physical attempt.
                diagnostic = getattr(self.provider, "last_diagnostic", None)
                if diagnostic is not None:
                    self.journal.emit("physical_provider_diagnostic", dict(attempt_id=attempt_id, diagnostic=diagnostic))
                self.first_physical_pass.setdefault(logical_id, event["status"] == "succeeded")
                self._charge(response, estimate, event)
                event.update(ended_at_utc=utc_now(), elapsed_seconds=self.clock() - started, budget_after=self.snapshot())
                self.journal.emit("call", event)
                if self.local_lease and confirmed_finished:
                    self.local_lease.release_finished()
            if error:
                retryable = isinstance(error, ProviderFailure) and error.retryable and error.request_finished
                if retryable and transport_index < self.config.transport_retries:
                    retry_of = attempt_id
                    continue
                raise error
            self.check()
            if self.budget.snapshot()["total_tokens"] > self.config.max_total_tokens:
                raise SharedBudgetStop("provider usage exceeded remaining shared token budget")
            return candidate
