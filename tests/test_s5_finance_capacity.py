"""Opt-in finance transport capacity, preserved v16 replay, and Critic handoff."""
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from schemas.compact_wire import CriticWire, Finance8Wire, FinanceWire
from schemas.evidence import canonical_hash
from workflow.compact_protocol import (
    GEMINI_8192_BODY_ASSEMBLY_CONFIG_VERSION, GEMINI_8192_FINANCE_CAPACITY_CONFIG_VERSION,
    FINANCE_CAPACITY_WIRE_VERSION, MECHANICAL_BODY_ASSEMBLY_REPAIR_VERSION,
    compact_role_output, evidence_catalog, expand_role_wire, make_envelope,
    mechanical_repair_json, protocol_manifest, role_wire_schema,
    normalize_exact_text_parent_lineage,
)
from workflow.contract_context import ContractArtifact, ContractContext
from workflow.contract_generation import ContractGenerator
from workflow.grounding import apply_confidence, claims_in, validate_grounding


ROOT = Path(__file__).resolve().parents[1]
CONFIG = GEMINI_8192_FINANCE_CAPACITY_CONFIG_VERSION


@pytest.fixture
def replay():
    run = ROOT / "docs/final_sprint/s5-llm-only-v16"
    path = run / "smokes/ai_education-B/events.jsonl"
    original = path.read_bytes()
    rows = [json.loads(line) for line in original.decode("utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in rows if event["kind"] == "call"
        and event["payload"].get("task_role") == "finance"
        and event["payload"].get("status") == "invalid_output")
    context = ContractContext.from_case(run / "frozen_inputs", "ai_education",
        condition="B", execution_mode="formal_frozen")
    upstream = []
    for role in ("research", "strategy"):
        event = next(event["payload"] for event in rows if event["kind"] == "artifact"
            and event["payload"]["artifact_ref"]["artifact_id"] == f"{role}.effective")
        saved = event["artifact"]
        artifact = ContractArtifact(role=saved["role"], version=saved["artifact_version"],
            case_id=saved["case_id"], packet_sha256=saved["packet_sha256"],
            brief_sha256=saved["brief_sha256"], payload_json=json.dumps(saved["payload"]),
            changes_json=json.dumps(saved["confidence_changes"]), pruned=saved["pruned"],
            unresolved_major=saved["unresolved_major"], contract_version=saved["contract_version"])
        context.verify_artifact(artifact)
        assert artifact.sha256 == canonical_hash(saved)
        upstream.append(artifact)
    wire, changes = mechanical_repair_json(raw, role_wire_schema("finance", CONFIG),
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
        source_disposition_claim_repair=True, citation_list_format_claim_repair=True,
        inline_citation_mirror_claim_repair=True, financial_marker_claim_repair=True,
        source_quality_scale_5_claim_repair=True, existing_claim_body_assembly_claim_repair=True,
        repair_evidence_catalog=evidence_catalog(context.packet),
        repair_financial_ids=set(context.finance.value_ids))
    yield context, tuple(upstream), raw, wire, changes
    assert path.read_bytes() == original


def test_v16_finance_raw_response_passes_full_canonical_chain_with_actual_upstream(replay):
    context, upstream, raw, wire, changes = replay
    original = json.loads(raw)
    assert [len(getattr(wire, key)[0].claims) for key in ("revenue", "costs", "economics")] == [5, 4, 7]
    for key in ("revenue", "costs", "economics"):
        assert [c.f for c in getattr(wire, key)[0].claims] == [c["f"] for c in original[key][0]["claims"]]
        assert [c.t for c in getattr(wire, key)[0].claims] == [c["t"] for c in original[key][0]["claims"]]
    candidate = expand_role_wire(context, "finance", wire, version=1, config_version=CONFIG)
    repairs = normalize_exact_text_parent_lineage(candidate, upstream)
    assert len(repairs) == 4
    assert {c.claim_id: c.parent_claim_id for c in claims_in(candidate) if c.claim_id == "GAP02"} == {"GAP02": "VAL02"}
    assert next(r for r in repairs if r["claim_id"] == "GAP02")["explicit_ancestor_chain"] == ["VAL02", "CUS02"]
    context.validate(candidate, version=1, upstream=upstream, transitive_lineage=True)
    accepted = context.accept("finance", candidate, version=1, upstream=upstream, transitive_lineage=True)
    effective, _ = apply_confidence(accepted.payload(), context.packet, version=1)
    validate_grounding(effective, context.packet, version=1)
    context.verify_artifact(accepted)
    assert effective.financial_values == context.finance.expected_values()
    assert len(effective.financial_values) == 21
    assert all(set(c.financial_value_ids) <= context.finance.value_ids for c in claims_in(effective))
    assert sum(len(getattr(effective, key)[0].claims) for key in (
        "revenue_assumptions", "cost_assumptions", "unit_economics_assumptions")) == 16
    assert all(change.get("financial_value_ids_added", []) == [] for change in changes)


def test_finance_capacity_stays_opt_in_and_ninth_claim_still_rejected(replay):
    _, _, _, wire, _ = replay
    data = wire.model_dump(mode="json")
    assert role_wire_schema("finance") is FinanceWire
    assert role_wire_schema("finance", GEMINI_8192_BODY_ASSEMBLY_CONFIG_VERSION) is FinanceWire
    assert role_wire_schema("finance", CONFIG) is Finance8Wire
    with pytest.raises(ValueError):
        FinanceWire.model_validate(data)
    data["revenue"][0]["claims"] = [data["revenue"][0]["claims"][0]] * 9
    with pytest.raises(ValueError):
        Finance8Wire.model_validate(data)


def test_finance_critic_receives_all_wide_notes_in_current_config(replay):
    context, upstream, _, wire, _ = replay
    candidate = expand_role_wire(context, "finance", wire, version=1, config_version=CONFIG)
    normalize_exact_text_parent_lineage(candidate, upstream)
    artifact = context.accept("finance", candidate, upstream=upstream, transitive_lineage=True)
    restored = compact_role_output(context, "finance", artifact.payload(), config_version=CONFIG)
    assert [len(getattr(restored, key)[0].claims) for key in ("revenue", "costs", "economics")] == [5, 4, 7]
    envelope = make_envelope(context, "finance_critic", CriticWire,
        upstream=(artifact,), config_version=CONFIG)
    critic_wire = json.loads(envelope.prompt)["view"]["reviewed_artifact"]["wire"]
    assert [len(critic_wire[key][0]["claims"]) for key in ("revenue", "costs", "economics")] == [5, 4, 7]
    with pytest.raises(ValueError):
        compact_role_output(context, "finance", artifact.payload())


def test_configured_generator_uses_wide_schema_for_generation_and_critic(replay):
    context, upstream, _, wire, _ = replay
    class OfflineClient:
        config = SimpleNamespace(config_version=CONFIG)
        calls = []
        def generate_structured_once(self, prompt, schema, **kwargs):
            self.calls.append((schema, json.loads(prompt)))
            return wire if schema is Finance8Wire else CriticWire(scores=[3, 3, 3, 3], status="PASS")
    client = OfflineClient()
    generator = ContractGenerator(client, protocol="compact-json-wire-v1-s6")
    artifact = generator.generate_compact(context, "finance", upstream=upstream)
    report = generator.review_compact(context, artifact, role="finance", artifact_id="finance.initial")
    assert len(client.calls) == 2 and client.calls[0][0] is Finance8Wire
    assert len(client.calls[1][1]["view"]["reviewed_artifact"]["wire"]["economics"][0]["claims"]) == 7
    assert report.provider_status == "PASS" and not report.revision_required


def test_manifest_seals_only_new_finance_schema_and_retains_repairs():
    current = protocol_manifest(CONFIG)
    previous = protocol_manifest(GEMINI_8192_BODY_ASSEMBLY_CONFIG_VERSION)
    assert current["finance_capacity_wire"] == FINANCE_CAPACITY_WIRE_VERSION
    assert previous["finance_capacity_wire"] is None
    assert current["mechanical_claim_repair"] == MECHANICAL_BODY_ASSEMBLY_REPAIR_VERSION
    assert current["wire_schemas"]["finance"] != previous["wire_schemas"]["finance"]
    assert {key: value for key, value in current["wire_schemas"].items() if key != "finance"} == {
        key: value for key, value in previous["wire_schemas"].items() if key != "finance"}
    assert current["role_output_tokens"] == previous["role_output_tokens"]


def changed_upstream(upstream, role, claim_id, change):
    result = []
    for artifact in upstream:
        if artifact.role != role:
            result.append(artifact)
            continue
        payload = artifact.payload()
        for claim in claims_in(payload):
            if claim.claim_id == claim_id:
                change(claim)
        result.append(replace(artifact, payload_json=payload.model_dump_json()))
    return tuple(result)


def test_unconnected_identical_text_is_not_inferred_as_shared_lineage(replay):
    context, upstream, _, wire, _ = replay
    upstream = changed_upstream(upstream, "strategy", "VAL02", lambda c: setattr(c, "parent_claim_id", None))
    candidate = expand_role_wire(context, "finance", wire, version=1, config_version=CONFIG)
    changes = normalize_exact_text_parent_lineage(candidate, upstream)
    assert not any(change["claim_id"] == "GAP02" for change in changes)
    with pytest.raises(ValueError, match="unchanged claim text"):
        context.validate(candidate, version=1, upstream=upstream, transitive_lineage=True)


def test_explicit_ancestry_cycle_is_rejected(replay):
    context, upstream, _, wire, _ = replay
    upstream = changed_upstream(upstream, "research", "CUS02", lambda c: setattr(c, "parent_claim_id", "VAL02"))
    candidate = expand_role_wire(context, "finance", wire, version=1, config_version=CONFIG)
    with pytest.raises(ValueError, match="cycle"):
        normalize_exact_text_parent_lineage(candidate, upstream)


@pytest.mark.parametrize("obligation,error", [("evidence", "lost upstream sources"),
    ("major", "major issue"), ("status", "semantic status")])
def test_transitive_lineage_preserves_every_ancestor_obligation(replay, obligation, error):
    context, upstream, _, wire, _ = replay
    sourced = next(c for c in claims_in(upstream[0].payload()) if c.source_anchors)
    def change(claim):
        if obligation == "evidence":
            claim.source_ids = sourced.source_ids.copy()
            claim.source_anchors = [a.model_copy(deep=True) for a in sourced.source_anchors]
        elif obligation == "major":
            claim.major_issue = True
        else:
            claim.critic_status = "unverified_after_revision"
    upstream = changed_upstream(upstream, "research", "CUS02", change)
    candidate = expand_role_wire(context, "finance", wire, version=1, config_version=CONFIG)
    normalize_exact_text_parent_lineage(candidate, upstream)
    with pytest.raises(ValueError, match=error):
        context.validate(candidate, version=1, upstream=upstream, transitive_lineage=True)


def test_legacy_direct_lineage_behavior_is_unchanged(replay):
    context, upstream, _, wire, _ = replay
    candidate = expand_role_wire(context, "finance", wire, version=1, config_version=CONFIG)
    normalize_exact_text_parent_lineage(candidate, upstream)
    with pytest.raises(ValueError, match="unchanged claim text"):
        context.validate(candidate, version=1, upstream=upstream)
