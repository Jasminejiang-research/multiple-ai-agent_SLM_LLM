"""Code-owned scenario disclosure; preserved v18 full canonical replay."""
import json
from pathlib import Path

import pytest

from schemas.compact_wire import Finance8Wire, FinanceWire
from schemas.evidence import canonical_hash
from workflow.compact_protocol import (
    GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION, MECHANICAL_FINANCE_NOTICE_REPAIR_VERSION,
    FINANCE_ASSUMPTION_POLICY_SENTENCE, _append_finance_assumption_notice,
    evidence_catalog, expand_role_wire, mechanical_repair_json, normalize_exact_text_parent_lineage,
    preserve_upstream_dispositions, protocol_manifest,
)
from workflow.contract_context import ContractArtifact, ContractContext
from workflow.grounding import apply_confidence, validate_grounding


ROOT = Path(__file__).resolve().parents[1]
CONFIG = GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION


def load_saved():
    run = ROOT / "docs/final_sprint/s5-llm-only-v18"
    path = run / "smokes/ai_education-B/events.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in rows if event["kind"] == "call"
        and event["payload"].get("task_role") == "finance" and event["payload"].get("raw_output"))
    context = ContractContext.from_case(run / "frozen_inputs", "ai_education",
        condition="B", execution_mode="formal_frozen")
    upstream = []
    for role in ("research", "strategy"):
        saved = next(event["payload"]["artifact"] for event in rows if event["kind"] == "artifact"
            and event["payload"]["artifact_ref"]["artifact_id"] == f"{role}.effective")
        artifact = ContractArtifact(role=role, version=saved["artifact_version"], case_id=saved["case_id"],
            packet_sha256=saved["packet_sha256"], brief_sha256=saved["brief_sha256"],
            payload_json=json.dumps(saved["payload"]), changes_json=json.dumps(saved["confidence_changes"]),
            pruned=saved["pruned"], unresolved_major=saved["unresolved_major"], contract_version=saved["contract_version"])
        context.verify_artifact(artifact)
        assert artifact.sha256 == canonical_hash(saved)
        upstream.append(artifact)
    return context, tuple(upstream), raw


def repair(raw, context, *, enabled=True):
    return mechanical_repair_json(raw, Finance8Wire,
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
        source_disposition_claim_repair=True, citation_list_format_claim_repair=True,
        inline_citation_mirror_claim_repair=True, financial_marker_claim_repair=True,
        source_quality_scale_5_claim_repair=True, existing_claim_body_assembly_claim_repair=True,
        invalid_source_recency_claim_repair=True, finance_note_partition_repair=True,
        finance_assumption_notice_repair=enabled,
        repair_evidence_catalog=evidence_catalog(context.packet), repair_financial_ids=set(context.finance.value_ids))


def test_actual_v18_finance_notice_replay_full_canonical_chain():
    context, upstream, raw = load_saved()
    original = json.loads(raw)
    old_wire, _ = repair(raw, context, enabled=False)
    with pytest.raises(ValueError, match="assumption_notice"):
        expand_role_wire(context, "finance", old_wire, version=1, config_version=CONFIG)
    wire, changes = repair(raw, context)
    assert wire.notice == original["notice"] + " " + FINANCE_ASSUMPTION_POLICY_SENTENCE
    before, after = old_wire.model_dump(mode="json"), wire.model_dump(mode="json")
    before.pop("notice")
    after.pop("notice")
    assert before == after
    disclosure = [change for change in changes if change["op"] == "append_code_owned_finance_assumption_disclosure"]
    assert len(disclosure) == 1 and disclosure[0]["code_owned_disclosure"] is True
    assert disclosure[0]["original_notice_sha256"] == canonical_hash(original["notice"])
    candidate = expand_role_wire(context, "finance", wire, version=1, config_version=CONFIG)
    normalize_exact_text_parent_lineage(candidate, upstream)
    preserve_upstream_dispositions(candidate, upstream)
    context.validate(candidate, version=1, upstream=upstream, transitive_lineage=True)
    accepted = context.accept("finance", candidate, upstream=upstream, transitive_lineage=True)
    effective, _ = apply_confidence(accepted.payload(), context.packet, version=1)
    validate_grounding(effective, context.packet, version=1)
    context.verify_artifact(accepted)
    assert effective.financial_values == context.finance.expected_values()
    assert len(effective.financial_values) == 21


@pytest.mark.parametrize("notice", ["Scenario assumptions are illustrative.",
    "These scenario figures are not forecasts.", "A normalized operating scenario requires validation."])
def test_missing_either_policy_word_appends_exact_fixed_disclosure(notice):
    data = {"notice": notice}
    changes = _append_finance_assumption_notice(data, Finance8Wire)
    assert data["notice"] == notice + " " + FINANCE_ASSUMPTION_POLICY_SENTENCE
    assert changes[0]["original_notice_preserved_verbatim"] is True
    assert changes[0]["financial_values_changed"] is False and changes[0]["evidence_ids_added"] == []


def test_notice_repair_is_idempotent_and_not_enabled_for_legacy_schema():
    data = {"notice": "Assumptions are not forecasts; validation is pending."}
    assert _append_finance_assumption_notice(data, Finance8Wire) == []
    legacy = {"notice": "A normalized operating scenario requires validation."}
    original = legacy.copy()
    assert _append_finance_assumption_notice(legacy, FinanceWire) == [] and legacy == original


def test_disclosure_does_not_truncate_to_fit_notice_cap():
    context, _, raw = load_saved()
    data = json.loads(raw)
    data["notice"] = "x" * 390
    with pytest.raises(ValueError):
        repair(json.dumps(data), context)


def test_latest_manifest_retains_all_prior_transport_adapters():
    manifest = protocol_manifest(CONFIG)
    assert manifest["mechanical_claim_repair"] == MECHANICAL_FINANCE_NOTICE_REPAIR_VERSION
    assert manifest["lossless_view_compression"] == "lossless-default-view-v3-s5"
    assert manifest["finance_capacity_wire"] == "compact-finance-claims-eight-v1-s5"
    assert manifest["canonical_citation_wire_adapter"] == "existing-anchor-citation-roundtrip-v1-s5"
    assert set(manifest["role_output_tokens"].values()) == {8192}
