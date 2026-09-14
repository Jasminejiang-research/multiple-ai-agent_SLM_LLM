"""Expected dependency inventory created before execution, independent of success."""
from schemas.evidence import canonical_hash
from workflow.review_events import utc_now


def reference(artifact_id, version, payload):
    return dict(artifact_id=artifact_id, artifact_version=version, sha256=canonical_hash(payload))


class HandoffLedger:
    def __init__(self, journal):
        self.journal = journal
        self.rows = {}
        self.available = {}

    def expect(self, upstream, downstream, artifact_id, *, branch_rule="always"):
        key = f"{upstream}->{downstream}:{artifact_id}"
        if key in self.rows:
            raise ValueError("duplicate expected handoff")
        row = dict(handoff_id=key, run_id=self.journal.run_id, upstream_node=upstream,
            downstream_node=downstream, required_artifact_id=artifact_id, required_artifact_version=None,
            required_artifact_hash=None, dependency_ids=[artifact_id], branch_rule=branch_rule,
            expected=True, status="pending", received_artifact_ref=None, occurred_at_utc=None,
            within_budget=None, failure_reason=None)
        if artifact_id in self.available:
            ref = self.available[artifact_id]
            row.update(required_artifact_version=ref["artifact_version"], required_artifact_hash=ref["sha256"])
        self.rows[key] = row
        self.journal.emit("handoff", row)

    def publish(self, ref):
        key = ref["artifact_id"]
        if key in self.available and self.available[key] != ref:
            raise ValueError("cannot overwrite an artifact reference")
        self.available[key] = ref
        for row in self.rows.values():
            if row["required_artifact_id"] == key and row["status"] == "pending":
                row.update(required_artifact_version=ref["artifact_version"], required_artifact_hash=ref["sha256"])
                self.journal.emit("handoff", row)

    def receive(self, downstream, refs):
        by_id = {ref["artifact_id"]: ref for ref in refs}
        for row in self.rows.values():
            if row["downstream_node"] != downstream or row["status"] != "pending":
                continue
            received = by_id.get(row["required_artifact_id"])
            expected = self.available.get(row["required_artifact_id"])
            valid = received is not None and expected is not None and received == expected
            row.update(status="succeeded" if valid else "failed", received_artifact_ref=received,
                occurred_at_utc=utc_now(), within_budget=True,
                failure_reason=None if valid else "missing or wrong effective artifact/version/hash")
            self.journal.emit("handoff", row)
            if not valid:
                raise ValueError("dependency handoff did not receive required effective artifact")

    def finish(self, reason):
        for row in self.rows.values():
            if row["status"] == "pending":
                row.update(status="missing", failure_reason=reason, occurred_at_utc=utc_now())
                self.journal.emit("handoff", row)
