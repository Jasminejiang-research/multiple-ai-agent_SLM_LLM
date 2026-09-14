"""Structural grounding checks and explainable, provider-neutral confidence rules.

Direct support is a model-proposed relation, never a human-verification verdict.
These rules cannot establish semantic support, completeness or factual truth.
"""
from __future__ import annotations

import re
from pydantic import BaseModel

from schemas.contract_outputs import (ContractProposal, ContractSection, GroundedFinding,
    GroundedInsight, GroundedFinanceAssumption, ConfidenceChange)
from schemas.evidence import EvidencePacket, GroundedClaim


class CitationPollutionError(ValueError):
    """Fatal contract pollution, not an opportunity to silently erase citations."""


def walk_models(value, path=""):
    if isinstance(value, BaseModel):
        yield path, value
        for key in type(value).model_fields:
            yield from walk_models(getattr(value, key), f"{path}.{key}".strip("."))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_models(item, f"{path}[{index}]")


def claims_in(value) -> list[GroundedClaim]:
    return [item for _, item in walk_models(value) if isinstance(item, GroundedClaim)]


def validate_grounding(artifact: BaseModel, packet: EvidencePacket, *, version: int):
    sources = {s.source_id: s for s in packet.sources}
    chunks = {c.chunk_id: c for c in packet.chunks}
    seen = {}
    for path, obj in walk_models(artifact):
        if hasattr(obj, "source_ids") and set(obj.source_ids) - set(sources):
            raise CitationPollutionError(f"{path}: unknown source ID")
        if isinstance(obj, GroundedClaim):
            if obj.artifact_version != version:
                raise ValueError(f"{path}: wrong claim artifact version")
            # Repeated occurrences may have different anchors, but not different meaning/evidence.
            identity = obj.model_dump(exclude={"content_anchor", "confidence", "confidence_reason"})
            if obj.claim_id in seen and seen[obj.claim_id] != identity:
                raise ValueError("claim ID reused with inconsistent meaning or evidence")
            seen[obj.claim_id] = identity
            for anchor in obj.source_anchors:
                source = sources.get(anchor.source_id)
                chunk = chunks.get(anchor.chunk_id)
                if not source or not chunk or chunk.source_id != anchor.source_id:
                    raise CitationPollutionError("unknown or mismatched source/chunk ID")
                if source.txt_sha256 != anchor.snapshot_sha256:
                    raise CitationPollutionError("source snapshot hash changed")
                if not chunk.line_start <= anchor.line_start <= anchor.line_end <= chunk.line_end:
                    raise ValueError("source anchor lines outside frozen chunk")
                lines = chunk.text.splitlines()
                excerpt = "\n".join(lines[anchor.line_start-chunk.line_start:anchor.line_end-chunk.line_start+1])
                if anchor.quote not in excerpt:
                    raise ValueError("source anchor quote not found at frozen location")
        if isinstance(obj, (ContractSection, GroundedFinding, GroundedInsight, GroundedFinanceAssumption)):
            content = obj.content if isinstance(obj, ContractSection) else "\n".join(
                str(getattr(obj, k, "")) for k in ("finding", "recommendation", "assumption", "rationale"))
            claims = obj.key_claims if isinstance(obj, ContractSection) else obj.claims
            for claim in claims:
                if claim.content_anchor not in content:
                    raise ValueError(f"{path}: claim content anchor not found")
                if isinstance(obj, ContractSection):
                    for source_id in claim.source_ids:
                        if f"[{source_id}]" not in content:
                            raise ValueError(f"{path}: missing inline source citation [{source_id}]")
            if isinstance(obj, ContractSection):
                expected_ids = {s for c in claims for s in c.source_ids}
                if set(obj.source_ids) != expected_ids or len(obj.source_ids) != len(set(obj.source_ids)):
                    raise ValueError(f"{path}: section source IDs must match claim sources")
                # The frozen contract reserves [ID] for citations; numbered/list references use prose.
                cited = set(re.findall(r"\[([A-Za-z0-9][A-Za-z0-9_.:-]*)\]", content))
                if cited - set(sources):
                    raise CitationPollutionError(f"{path}: invented inline source ID")
                if cited != expected_ids:
                    raise ValueError(f"{path}: inline citations differ from structured claim sources")
                urls = set(re.findall(r"https?://[^\s<>\[\]()]+", content))
                if {url.rstrip('.,;') for url in urls} - set(packet.allowlist_urls):
                    raise CitationPollutionError(f"{path}: URL outside frozen allowlist")


def claim_confidence(claim: GroundedClaim):
    if claim.pruned:
        return "low", "pruned"
    if claim.conflict:
        return "low", "conflict"
    if claim.major_issue or claim.critic_status in ("unresolved", "unverified_after_revision"):
        return "low", "critic_unresolved"
    if claim.claim_type in ("assumption", "projection", "recommendation"):
        return "medium", "assumption_dominant"
    if claim.evidence_status != "sourced_fact" or claim.source_support != "direct" or not claim.source_anchors:
        return "low", "partial_support" if claim.source_support in ("partial", "contextual") else "no_evidence"
    return "high", "directly_supported"


def aggregate_confidence(claims: list[GroundedClaim], *, pruned=False, unresolved=False):
    if pruned:
        return "low", "pruned"
    if unresolved:
        return "low", "critic_unresolved"
    for claim in claims:
        label, reason = claim_confidence(claim)
        if label == "low" and (claim.decision_critical or claim.high_impact or claim.conflict or claim.pruned or claim.major_issue):
            return label, reason
    # A section must not be high merely because an empty set of facts is supported.
    facts = [c for c in claims if c.claim_type == "factual"]
    assumptions = [c for c in claims if c.claim_type in ("assumption", "projection")]
    if not facts or len(assumptions) >= len(facts):
        return "medium", "assumption_dominant"
    if any(claim_confidence(c)[0] != "high" for c in facts):
        return "medium", "partial_support"
    return "high", "directly_supported"


def apply_confidence(artifact, packet, *, version, pruned=False, unresolved=False):
    """Return a copy and changes; never rewrite the first submitted artifact."""
    validate_grounding(artifact, packet, version=version)
    result = artifact.model_copy(deep=True)
    changes = []
    for path, obj in walk_models(result):
        if isinstance(obj, GroundedClaim):
            label, reason = ("low", "pruned") if pruned else ("low", "critic_unresolved") if unresolved else claim_confidence(obj)
        elif isinstance(obj, (ContractSection, GroundedFinding, GroundedInsight, GroundedFinanceAssumption)):
            claims = obj.key_claims if isinstance(obj, ContractSection) else obj.claims
            label, reason = aggregate_confidence(claims, pruned=pruned, unresolved=unresolved)
        else:
            continue
        if obj.confidence != label or obj.confidence_reason != reason:
            changes.append(ConfidenceChange(artifact_version=version, location=path, previous=obj.confidence, current=label, reason=reason))
        obj.confidence, obj.confidence_reason = label, reason
    return result, changes


def validate_lineage(previous: BaseModel, candidate: BaseModel, *, revision=False):
    """Preserve evidence on retained claims and prevent source/status laundering."""
    before = {c.claim_id: c for c in claims_in(previous)}
    after = {c.claim_id: c for c in claims_in(candidate)}
    if revision:
        # Explicit removals/splits can be added to a later version; v1 refuses silent loss.
        covered = set(after) | {c.parent_claim_id for c in after.values() if c.parent_claim_id}
        if set(before) - covered:
            raise ValueError("revision silently dropped claim IDs; retain or explicitly split claims")
    for current in after.values():
        old = before.get(current.claim_id) or before.get(current.parent_claim_id)
        if old is None and any(c.claim_text == current.claim_text for c in before.values()):
            raise ValueError("unchanged claim text requires its upstream ID or parent_claim_id")
        if old is None:
            continue
        old_anchors = {a.model_dump_json() for a in old.source_anchors}
        new_anchors = {a.model_dump_json() for a in current.source_anchors}
        if not set(old.source_ids) <= set(current.source_ids) or not old_anchors <= new_anchors:
            raise ValueError("retained claim lost upstream sources or anchors")
        if old.claim_type == "factual" and current.claim_type != "factual":
            raise ValueError("factual claim cannot be relabeled to remove its evidence obligation")
        if (old.conflict and not current.conflict) or (old.pruned and not current.pruned) or (old.major_issue and not current.major_issue):
            raise ValueError("unverified conflict/pruning/major issue cannot be cleared")
        if old.critic_status in ("unresolved", "unverified_after_revision") and current.critic_status not in ("unresolved", "unverified_after_revision"):
            raise ValueError("unverified semantic status cannot be cleared by structural validation")
        if old.claim_type == "factual" and claim_confidence(old)[0] == "low" and claim_confidence(current)[0] != "low" and new_anchors <= old_anchors:
            raise ValueError("unsupported factual claim cannot be upgraded without new evidence")
