"""Small durable, versioned experiment files; raw journals are never overwritten."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value, *, replace=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if not replace:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_csv(path, rows, fields=None):
    rows = list(rows)
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k,v in row.items()})


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def append_event(path, payload):
    from workflow.review_events import utc_now
    record = {"event_id":uuid4().hex,"occurred_at_utc":utc_now(),**payload}
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return record


def read_journal(path):
    if not Path(path).exists():
        return [], False
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    events, seen = [], {}
    for index, line in enumerate(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            if index != len(lines)-1:
                raise ValueError("corrupt journal interior; preserve and investigate")
            return events, True
        key = event["event_id"]
        if key in seen:
            if seen[key] != event:
                raise ValueError("conflicting duplicate event ID")
            continue
        seen[key] = event
        events.append(event)
    return events, False


def contained(root, relative):
    path = (Path(root)/relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(Path(root).resolve()):
        raise ValueError("artifact path escapes experiment directory")
    return path
