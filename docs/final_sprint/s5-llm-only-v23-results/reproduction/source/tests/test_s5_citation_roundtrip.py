"""Actual preserved claim transport roundtrips without changing selected evidence."""
import json

import pytest

from schemas.compact_wire import ClaimWire, CriticWire
from schemas.evidence import canonical_hash
from workflow.compact_protocol import (
    CANONICAL_CITATION_WIRE_ADAPTER_VERSION, GEMINI_8192_FINANCE_CAPACITY_CONFIG_VERSION,
    _claim_to_wire, _compact_existing_citations, _compact_parent_citations, _expand_claim,
    _expand_text, evidence_catalog, compact_role_output,
    expand_critic_wire, expand_role_wire, make_envelope, normalize_exact_text_parent_lineage,
    protocol_manifest, role_view,
)
from workflow.contract_context import ROLE_SCHEMAS
from workflow.grounding import CitationPollutionError, claims_in
from test_s5_finance_capacity import ROOT, replay


CONFIG = GEMINI_8192_FINANCE_CAPACITY_CONFIG_VERSION


def all_upstream(replay):
    context, upstream, _, finance_wire, _ = replay
    finance = expand_role_wire(context, "finance", finance_wire, version=1, config_version=CONFIG)
    normalize_exact_text_parent_lineage(finance, upstream)
    accepted = context.accept("finance", finance, upstream=upstream, transitive_lineage=True)
    return context, (*upstream, accepted)


def test_all_actual_v16_upstream_claims_roundtrip_without_text_or_anchor_changes(replay):
    context, upstream = all_upstream(replay)
    view = role_view(context, "writer", upstream=upstream, config_version=CONFIG)
    count = 0
    for artifact, capsule in zip(upstream, view["upstream"], strict=True):
        originals = {c.claim_id: c for c in claims_in(artifact.payload())}
        for wire in capsule["claims"]:
            original = originals[wire["i"]]
            restored = _expand_claim(ClaimWire.model_validate(wire), context, artifact.version)
            assert restored.claim_text == original.claim_text
            assert restored.source_anchors == original.source_anchors
            assert restored.source_ids == original.source_ids
            assert restored.financial_value_ids == original.financial_value_ids
            assert restored.parent_claim_id == original.parent_claim_id
            assert wire["e"] == _claim_to_wire(original, context.packet)["e"]
            count += 1
    assert count >= 25


def test_actual_role_critic_wire_roundtrips_complete_parent_bodies(replay):
    context, upstream = all_upstream(replay)
    for artifact in upstream:
        wire = compact_role_output(context, artifact.role, artifact.payload(), config_version=CONFIG)
        restored = expand_role_wire(context, artifact.role, wire, version=artifact.version, config_version=CONFIG)
        assert canonical_hash(restored.model_dump(mode="json")) == canonical_hash(artifact.payload().model_dump(mode="json"))
        envelope = make_envelope(context, f"{artifact.role}_critic", CriticWire,
            upstream=(artifact,), config_version=CONFIG)
        assert json.loads(envelope.prompt)["view"]["reviewed_artifact"]["wire"] == wire.model_dump(mode="json")


def actual_proposal(context):
    rows = [json.loads(line) for line in (ROOT / "docs/final_sprint/s5-llm-only-v16/smokes/ai_education-A/events.jsonl")
        .read_text(encoding="utf-8").splitlines()]
    saved = next(e["payload"]["artifact"] for e in rows if e["kind"] == "artifact"
        and e["payload"]["artifact_ref"]["artifact_id"] == "single.effective")
    return context.accept("writer", ROLE_SCHEMAS["writer"].model_validate(saved["payload"]))


def test_actual_proposal_writer_final_critic_text_and_claim_are_consistent(replay):
    context, *_ = replay
    artifact = actual_proposal(context)
    envelope = make_envelope(context, "final_critic", CriticWire, upstream=(artifact,), config_version=CONFIG)
    wire = json.loads(envelope.prompt)["view"]["reviewed_artifact"]["wire"]
    assert len(wire["sections"]) == 13
    assert all(claim["t"] in section["text"] for section in wire["sections"] for claim in section["claims"])
    restored = expand_role_wire(context, "writer", wire, version=1, config_version=CONFIG)
    assert canonical_hash(restored.model_dump(mode="json")) == canonical_hash(artifact.payload().model_dump(mode="json"))


def test_actual_revision_view_uses_same_existing_short_ids_in_field_and_claim(replay):
    context, upstream, *_ = replay
    artifact = upstream[0]
    target = next(c for c in claims_in(artifact.payload()) if c.claim_id == "MKT01")
    report = expand_critic_wire(context, artifact, "research", "research.initial",
        {"scores": [2, 2, 2, 2], "status": "FAIL", "issues": [{"i": "issue001", "sev": "high",
            "criterion": "source_integrity", "claims": [target.claim_id], "fields": ["market.0.text"],
            "e": [], "fix": "clarify_scope", "note": "Clarify the scope of this existing claim."}]},
        critic_patch_adapter=True)
    view = role_view(context, "revision", previous=artifact, review=report, config_version=CONFIG)
    assert view["claims"][0]["t"] in view["fields"]["market_trends.0.finding"]
    assert "[E03]" in view["claims"][0]["t"]
    assert "[EDU-02]" not in view["fields"]["market_trends.0.finding"]


def test_unknown_or_unresolved_ambiguous_citations_are_not_guessed():
    with pytest.raises(CitationPollutionError, match="selected frozen anchor"):
        _compact_existing_citations("Unknown source [EDU-99].", {"EDU-02": ["E03"]})
    with pytest.raises(CitationPollutionError, match="ambiguous"):
        _compact_existing_citations("Ambiguous source [EDU-02].", {"EDU-02": ["E03", "E04"]})
    assert _compact_existing_citations("Two selected citations [EDU-02][EDU-02].",
        {"EDU-02": ["E03", "E04"]}, ordered_repeated_claim=True) == "Two selected citations [E03][E04]."


def test_old_config_claim_transport_is_unchanged(replay):
    context, upstream, *_ = replay
    original = next(c for c in claims_in(upstream[0].payload()) if c.claim_id == "MKT01")
    wire = _claim_to_wire(original, context.packet)
    assert "[EDU-02]" in wire["t"]
    with pytest.raises(CitationPollutionError):
        _expand_claim(ClaimWire.model_validate(wire), context, 1)
    assert protocol_manifest(CONFIG)["canonical_citation_wire_adapter"] == CANONICAL_CITATION_WIRE_ADAPTER_VERSION


def test_parent_source_alias_is_reversible_and_never_selects_new_evidence(replay):
    context, upstream, *_ = replay
    note = upstream[0].payload().competitor_assumptions[0]
    before = [c.model_dump(mode="json") for c in note.claims]
    compact = _compact_parent_citations(note.finding, note.claims, context.packet)
    assert "district tools with custom pricing [E01]" in compact
    assert _expand_text(compact, evidence_catalog(context.packet)) == note.finding
    assert [c.model_dump(mode="json") for c in note.claims] == before
    assert protocol_manifest(CONFIG)["source_alias_selection"] == "first_existing_selected_anchor_no_support_inference"
    with pytest.raises(CitationPollutionError, match="selected frozen anchor"):
        _compact_parent_citations("Unselected parent source [EDU-02].", note.claims, context.packet)


def test_field_only_revision_supplies_parent_selected_evidence(replay):
    context, upstream, *_ = replay
    artifact = upstream[0]
    report = expand_critic_wire(context, artifact, "research", "research.initial",
        {"scores": [2, 2, 2, 2], "status": "FAIL", "issues": [{"i": "issue001", "sev": "high",
            "criterion": "source_integrity", "claims": [], "fields": ["market.0.text"],
            "e": [], "fix": "clarify_scope", "note": "Clarify the scope of this existing field."}]},
        critic_patch_adapter=True)
    view = role_view(context, "revision", previous=artifact, review=report, config_version=CONFIG)
    assert view["claims"] == []
    assert {entry["id"] for entry in view["evidence"]} == {"E03", "E04"}
