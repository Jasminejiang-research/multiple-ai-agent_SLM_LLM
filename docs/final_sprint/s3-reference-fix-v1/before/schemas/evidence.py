"""Versioned frozen evidence, model-proposed claims, and separate human verdicts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EvidenceSource(BaseModel):
    # Capture metadata from S0 is retained, including original response hashes.
    model_config = ConfigDict(extra="allow")
    source_id: str = Field(min_length=1)
    source_type: Literal["web", "rag"]
    title: str = Field(min_length=1)
    publisher: str
    url: str | None
    final_url: str | None
    published_date: str | None
    retrieved_at_utc: str
    txt_path: str
    txt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    limitation: str
    human_support_status: Literal["pending"]


class FrozenChunk(StrictModel):
    # Do not strip whitespace: offsets refer to the exact archived text.
    model_config = ConfigDict(extra="forbid")
    chunk_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    text: str = Field(min_length=1)


class EvidencePacket(StrictModel):
    model_config = ConfigDict(extra="forbid")
    packet_version: str
    case_id: str
    review_status: Literal["pending", "approved"]
    approval_record: dict[str, Any] | str | None
    allowlist_source_ids: list[str]
    allowlist_urls: list[str]
    sources: list[EvidenceSource]
    chunks: list[FrozenChunk]
    evidence_scope: str = "Only fixed chunks are available; human support is pending."
    packet_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="before")
    @classmethod
    def verify_hash(cls, value: Any) -> Any:
        if isinstance(value, dict):
            body = {k: v for k, v in value.items() if k != "packet_sha256"}
            if canonical_hash(body) != value.get("packet_sha256"):
                raise ValueError("packet hash mismatch")
        return value

    @model_validator(mode="after")
    def verify_links(self) -> EvidencePacket:
        ids = [s.source_id for s in self.sources]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("source IDs must be nonempty and unique")
        if len(set(self.allowlist_source_ids)) != len(self.allowlist_source_ids) or set(ids) != set(self.allowlist_source_ids):
            raise ValueError("source allowlist mismatch")
        for source in self.sources:
            for url in (source.url, source.final_url):
                if source.source_type == "web" and (not url or not url.startswith("https://")):
                    raise ValueError("web sources require captured HTTPS URLs")
                if url and url not in self.allowlist_urls:
                    raise ValueError("URL outside allowlist")
        chunk_ids = [c.chunk_id for c in self.chunks]
        if not chunk_ids or len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError("chunk IDs must be nonempty and unique")
        for chunk in self.chunks:
            if chunk.source_id not in ids or chunk.line_end < chunk.line_start:
                raise ValueError("invalid chunk source or line range")
        if self.review_status == "approved" and not self.approval_record:
            raise ValueError("approval requires an explicit user record")
        return self

    def verify_snapshots(self, root: Path) -> None:
        """Read only the named local files; never fetch URLs or query an index."""
        texts = {}
        root = root.resolve()
        for source in self.sources:
            data = source.model_dump(exclude_unset=True)
            for kind in ("html", "txt", "original"):
                if kind + "_path" not in data:
                    continue
                relative = Path(data[kind + "_path"])
                path = (root / relative).resolve()
                if relative.is_absolute() or not path.is_relative_to(root):
                    raise ValueError("snapshot path escapes packet root")
                content = path.read_bytes()
                if hashlib.sha256(content).hexdigest() != data.get(kind + "_sha256"):
                    raise ValueError(f"snapshot hash mismatch: {source.source_id}/{kind}")
                if kind == "txt":
                    texts[source.source_id] = content.decode("utf-8").splitlines()
        for chunk in self.chunks:
            lines = texts[chunk.source_id]
            if chunk.line_end > len(lines) or "\n".join(lines[chunk.line_start - 1:chunk.line_end]) != chunk.text:
                raise ValueError("chunk content differs from snapshot")


class SourceAnchor(StrictModel):
    source_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    quote: str = Field(min_length=1)


Confidence = Literal["low", "medium", "high"]
ConfidenceReason = Literal["no_evidence", "partial_support", "conflict", "assumption_dominant",
                           "pruned", "critic_unresolved", "directly_supported"]


class GroundedClaim(StrictModel):
    claim_id: str = Field(min_length=1)
    parent_claim_id: str | None
    claim_text: str = Field(min_length=1)
    claim_type: Literal["factual", "assumption", "recommendation", "projection"]
    claim_domain: str = Field(min_length=1)
    evidence_status: Literal["sourced_fact", "needs_validation", "assumption", "unsupported"]
    source_ids: list[str]
    source_support: Literal["direct", "partial", "contextual", "none"]
    source_quality: float = Field(ge=0, le=1, allow_inf_nan=False)
    source_recency: float | None = Field(ge=0, le=1, allow_inf_nan=False)
    support_assessed_by: Literal["model_proposed"]
    critic_status: Literal["not_reviewed", "passed", "unresolved", "unverified_after_revision"]
    decision_critical: bool
    high_impact: bool
    conflict: bool
    pruned: bool
    major_issue: bool
    confidence: Confidence
    confidence_reason: ConfidenceReason
    content_anchor: str = Field(min_length=1)
    source_anchors: list[SourceAnchor]
    financial_value_ids: list[str]
    premise: str
    artifact_version: int = Field(ge=1)

    @model_validator(mode="after")
    def check_disposition(self) -> GroundedClaim:
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("duplicate claim source IDs")
        if set(a.source_id for a in self.source_anchors) != set(self.source_ids):
            raise ValueError("every claim source needs a snapshot anchor")
        if self.evidence_status == "sourced_fact" and (self.claim_type != "factual" or not self.source_ids or self.source_support != "direct"):
            raise ValueError("sourced_fact requires factual type and proposed direct anchored support")
        if self.claim_type in ("assumption", "projection", "recommendation") and not self.premise:
            raise ValueError("assumptions, projections and recommendations require an explicit premise")
        if self.claim_type in ("assumption", "projection") and self.evidence_status != "assumption":
            raise ValueError("assumption/projection must remain explicitly marked assumption")
        return self


class HumanSupportVerdict(StrictModel):
    """External Gold Ledger row. Never populated by a model or a validator."""
    claim_id: str
    artifact_sha256: str
    verdict: Literal["pending", "supported", "partial", "unsupported", "conflict"] = "pending"
    reviewer: str | None = None
    review_note: str | None = None

    @model_validator(mode="after")
    def require_reviewer(self) -> HumanSupportVerdict:
        if self.verdict != "pending" and (not self.reviewer or not self.review_note):
            raise ValueError("non-pending human verdict requires reviewer and note")
        return self
