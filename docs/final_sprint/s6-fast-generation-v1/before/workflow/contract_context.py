"""S1 input and artifact boundary for S2 graph nodes and S4 experiment runners."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from schemas.contract_outputs import (CONTRACT_VERSION, ContractProposal, ContractFinanceAssumptions,
                                     ContractResearchAnalysis, ContractStrategyAnalysis)
from schemas.evidence import EvidencePacket, canonical_hash
from workflow.finance_contract import FinanceContract
from workflow.grounding import apply_confidence, validate_lineage, validate_grounding, walk_models, claims_in
from schemas.contract_outputs import GroundedFinanceAssumption

ROLE_SCHEMAS = {"research": ContractResearchAnalysis, "strategy": ContractStrategyAnalysis,
                "finance": ContractFinanceAssumptions, "single": ContractProposal, "writer": ContractProposal}


@dataclass(frozen=True)
class ContractArtifact:
    role: str
    version: int
    case_id: str
    packet_sha256: str
    brief_sha256: str
    payload_json: str
    changes_json: str = "[]"
    pruned: bool = False
    unresolved_major: bool = False
    contract_version: str = CONTRACT_VERSION

    @property
    def sha256(self):
        return canonical_hash(self.as_dict())

    def payload(self):
        return ROLE_SCHEMAS[self.role].model_validate_json(self.payload_json)

    def as_dict(self):
        return {"role": self.role, "artifact_version": self.version, "case_id": self.case_id,
                "packet_sha256": self.packet_sha256, "brief_sha256": self.brief_sha256,
                "contract_version": self.contract_version, "payload": json.loads(self.payload_json),
                "confidence_changes": json.loads(self.changes_json), "pruned": self.pruned,
                "unresolved_major": self.unresolved_major,
                "confidence_basis": "proposed_support_structurally_checked_not_human_gold"}


class ContractContext:
    """Freeze full brief and packet once, before the first Research/Single call.

    This is an input boundary, not a formal experiment runner or a B/C/D graph.
    S4 must additionally enforce protocol/config and workflow acceptance gates.
    """
    def __init__(self, *, brief, packet, expected_packet_hash, snapshot_root, condition,
                 execution_mode="fixture", brief_sha256=None):
        if condition not in "ABCD" or len(condition) != 1:
            raise ValueError("condition must be A, B, C or D")
        if execution_mode not in ("fixture", "formal_frozen"):
            raise ValueError("ContractContext requires an explicit frozen evidence mode")
        raw = packet.model_dump(mode="json", exclude_unset=True) if isinstance(packet, EvidencePacket) else packet
        validated = EvidencePacket.model_validate(raw)
        if validated.packet_sha256 != expected_packet_hash:
            raise ValueError("packet does not match the expected case hash")
        validated.verify_snapshots(Path(snapshot_root))
        if execution_mode == "formal_frozen" and validated.review_status != "approved":
            raise ValueError("formal evidence packet awaits user approval")
        from workflow.nodes import validate_user_brief
        errors = validate_user_brief(brief)
        if errors:
            raise ValueError("invalid complete brief: " + "; ".join(errors))
        self._brief_json = json.dumps(brief, ensure_ascii=False, allow_nan=False)
        self._packet_json = json.dumps(raw, ensure_ascii=False, allow_nan=False)
        self.brief_sha256 = brief_sha256 or canonical_hash(brief)
        self.packet_sha256 = validated.packet_sha256
        self.case_id = validated.case_id
        self.condition = condition
        self.execution_mode = execution_mode
        self.finance = FinanceContract(self.case_id, self.brief, set(validated.allowlist_source_ids))

    @classmethod
    def from_case(cls, root: Path, case_id: str, *, condition, execution_mode="fixture"):
        if case_id not in ("ai_education", "intelligent_ring"):
            raise ValueError("case must have a frozen finance contract")
        folder = Path(root) / "cases" / case_id
        case = json.loads((folder / "case.json").read_text(encoding="utf-8"))
        brief_bytes = (folder / "brief.json").read_bytes()
        brief_hash = hashlib.sha256(brief_bytes).hexdigest()
        packet = json.loads((folder / "packet.json").read_text(encoding="utf-8"))
        if case["case_id"] != case_id or packet["case_id"] != case_id or case["brief_sha256"] != brief_hash:
            raise ValueError("case identity/brief hash mismatch")
        if execution_mode == "formal_frozen" and (case["review_status"] != "approved" or not case.get("approval_record")):
            raise ValueError("complete case/brief awaits user approval")
        return cls(brief=json.loads(brief_bytes), packet=packet, expected_packet_hash=case["packet_sha256"],
                   snapshot_root=root, condition=condition, execution_mode=execution_mode, brief_sha256=brief_hash)

    @property
    def packet(self):
        return EvidencePacket.model_validate_json(self._packet_json)

    @property
    def brief(self):
        return json.loads(self._brief_json)

    def verify_artifact(self, artifact):
        if (artifact.case_id, artifact.packet_sha256, artifact.brief_sha256, artifact.contract_version) != (
                self.case_id, self.packet_sha256, self.brief_sha256, CONTRACT_VERSION):
            raise ValueError("upstream artifact belongs to different input or contract version")
        payload = artifact.payload()
        self.validate(payload, version=artifact.version)
        return payload

    def input_payload(self, role, upstream=(), previous=None):
        for artifact in (*upstream, *((previous,) if previous else ())):
            self.verify_artifact(artifact)
        return {"user_brief": self.brief, "evidence_packet": json.loads(self._packet_json),
                "packet_sha256": self.packet_sha256, "brief_sha256": self.brief_sha256,
                "upstream_artifacts": [a.as_dict() for a in upstream],
                "previous_artifact": previous.as_dict() if previous else None,
                "finance_contract": self.finance.prompt_spec() if role in ("single", "finance", "writer", "revision", "critic") else None,
                "support_warning": "source_support is model-proposed; human Gold Ledger verdicts remain pending."}

    def validate(self, candidate, *, version, upstream=(), previous=None):
        validate_grounding(candidate, self.packet, version=version)
        financial_ids = self.finance.value_ids
        for claim in claims_in(candidate):
            if set(claim.financial_value_ids) - financial_ids:
                raise ValueError("claim refers to unknown financial value ID")
            if claim.claim_domain == "financial_calculation" and not claim.financial_value_ids:
                raise ValueError("financial calculation claim requires linked value IDs")
        if isinstance(candidate, ContractFinanceAssumptions):
            self.finance.validate(candidate.financial_values)
            ids = financial_ids
            for _, obj in walk_models(candidate):
                if isinstance(obj, GroundedFinanceAssumption) and set(obj.value_ids) - ids:
                    raise ValueError("finance note refers to unknown value ID")
        if isinstance(candidate, ContractProposal):
            self.finance.validate(candidate.financial_assumptions.financial_values)
        for artifact in upstream:
            validate_lineage(self.verify_artifact(artifact), candidate)
        if previous:
            validate_lineage(self.verify_artifact(previous), candidate, revision=True)

    def accept(self, role, candidate, *, version=1, upstream=(), previous=None,
               pruned=False, unresolved_major=False):
        if role not in ROLE_SCHEMAS:
            raise ValueError("unknown generation role")
        if previous and (previous.role != role or previous.version != 1 or version != 2):
            raise ValueError("revision requires the same role and exactly one revision (v1 to v2)")
        if not previous and version != 1:
            raise ValueError("initial artifact version must be 1")
        payload = candidate.model_dump(mode="json") if isinstance(candidate, BaseModel) else candidate
        candidate = ROLE_SCHEMAS[role].model_validate(payload)
        self.validate(candidate, version=version, upstream=upstream, previous=previous)
        pruned = pruned or bool(previous and previous.pruned) or any(a.pruned for a in upstream)
        unresolved_major = unresolved_major or bool(previous and previous.unresolved_major) or any(a.unresolved_major for a in upstream)
        effective, changes = apply_confidence(candidate, self.packet, version=version,
                                               pruned=pruned, unresolved=unresolved_major)
        return ContractArtifact(role, version, self.case_id, self.packet_sha256, self.brief_sha256,
                              effective.model_dump_json(), json.dumps([c.model_dump() for c in changes]),
                                pruned, unresolved_major)

    def review_input(self, artifact):
        """Exact same packet and effective artifact for S2 Critic/Revision."""
        return self.input_payload("critic", upstream=(artifact,))

    def validate_review_feedback(self, artifact, feedback):
        """S1 source/claim boundary for the role-aware reports implemented in S2."""
        from workflow.grounding import CitationPollutionError
        payload = self.verify_artifact(artifact)
        ids = {c.claim_id for c in claims_in(payload)}
        sources = set(self.packet.allowlist_source_ids)
        chunks = {c.chunk_id for c in self.packet.chunks}
        data = feedback.model_dump(mode="json") if isinstance(feedback, BaseModel) else feedback
        if not isinstance(data, dict) or not data:
            raise ValueError("review feedback must be a nonempty structured object")
        def check(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in ("source_ids", "affected_source_ids") and (not isinstance(item, list) or set(item) - sources):
                        raise CitationPollutionError("Critic/Revision introduced unknown source IDs")
                    if key == "source_id" and item not in sources:
                        raise CitationPollutionError("Critic/Revision introduced unknown source ID")
                    if key == "chunk_id" and item not in chunks:
                        raise CitationPollutionError("Critic/Revision introduced unknown chunk ID")
                    if key == "affected_claim_ids" and (not isinstance(item, list) or set(item) - ids):
                        raise ValueError("review references unknown claim IDs")
                    check(item)
            elif isinstance(value, list):
                for item in value: check(item)
        check(data)
        return json.loads(json.dumps(data, allow_nan=False))

    def export(self, artifact, destination: Path):
        """Internal review export retains full provenance and refuses overwrite."""
        proposal = self.verify_artifact(artifact)
        if not isinstance(proposal, ContractProposal):
            raise ValueError("terminal export requires the common complete 13-section proposal")
        from schemas.workflow import PROPOSAL_SECTION_FIELD_NAMES
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=False)
        (destination / "proposal.json").write_text(json.dumps(artifact.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        (destination / "packet.json").write_text(self._packet_json, encoding="utf-8")
        (destination / "brief.json").write_text(self._brief_json, encoding="utf-8")
        text = [f"# {proposal.title}", "Confidence uses structurally checked model-proposed support. Human fact verification is pending."]
        for field in PROPOSAL_SECTION_FIELD_NAMES:
            section = getattr(proposal, field)
            text.extend([f"## {section.title}", section.content,
                         f"Confidence: {section.confidence}; reason: {section.confidence_reason}"])
            if field == "financial_assumptions":
                text.append("Scenario calculations (input provenance is retained in brief.json; these are not forecasts):\n\n"
                            "| Value ID | Value | Unit | Period | Origin | Formula |\n"
                            "|---|---:|---|---|---|---|\n" + "\n".join(
                                f"| {v.value_id} | {v.value if v.value is not None else 'not_applicable: '+v.reason} | {v.unit} | {v.period} | {v.origin} | {v.formula_id} |"
                                for v in section.financial_values))
        text.append("Frozen sources (Appendix):")
        text.extend(f"[{s.source_id}] {s.title} — {s.url or s.txt_path}; snapshot SHA-256: {s.txt_sha256}" for s in self.packet.sources)
        (destination / "proposal.md").write_text("\n\n".join(text) + "\n", encoding="utf-8")
        return destination
