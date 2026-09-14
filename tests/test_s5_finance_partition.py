"""Preserved v17 replay: missing recency and bounded ordered note partition."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from schemas.compact_wire import Finance8Wire, ClaimWire
from schemas.evidence import canonical_hash
from workflow.compact_protocol import (
    GEMINI_8192_FINANCE_PARTITION_CONFIG_VERSION, MECHANICAL_FINANCE_PARTITION_REPAIR_VERSION,
    evidence_catalog, expand_role_wire, mechanical_repair_json, normalize_exact_text_parent_lineage,
    preserve_upstream_dispositions, protocol_manifest, compact_role_output,
)
from workflow.contract_context import ContractArtifact, ContractContext
from workflow.grounding import apply_confidence, validate_grounding


ROOT = Path(__file__).resolve().parents[1]
CONFIG = GEMINI_8192_FINANCE_PARTITION_CONFIG_VERSION


def load_saved():
    run = ROOT / "docs/final_sprint/s5-llm-only-v17"
    event_path = run / "smokes/ai_education-B/events.jsonl"
    records = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records if event["kind"] == "call"
        and event["payload"].get("status") == "invalid_output"
        and event["payload"].get("task_role") == "finance")
    context = ContractContext.from_case(run / "frozen_inputs", "ai_education",
        condition="B", execution_mode="formal_frozen")
    upstream = []
    for role in ("research", "strategy"):
        saved = next(event["payload"]["artifact"] for event in records if event["kind"] == "artifact"
            and event["payload"]["artifact_ref"]["artifact_id"] == f"{role}.effective")
        artifact = ContractArtifact(role=role, version=saved["artifact_version"], case_id=saved["case_id"],
            packet_sha256=saved["packet_sha256"], brief_sha256=saved["brief_sha256"],
            payload_json=json.dumps(saved["payload"]), changes_json=json.dumps(saved["confidence_changes"]),
            pruned=saved["pruned"], unresolved_major=saved["unresolved_major"], contract_version=saved["contract_version"])
        context.verify_artifact(artifact)
        assert artifact.sha256 == canonical_hash(saved)
        upstream.append(artifact)
    return context, tuple(upstream), raw


def repair(raw, context):
    return mechanical_repair_json(raw, Finance8Wire,
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
        source_disposition_claim_repair=True, citation_list_format_claim_repair=True,
        inline_citation_mirror_claim_repair=True, financial_marker_claim_repair=True,
        source_quality_scale_5_claim_repair=True, existing_claim_body_assembly_claim_repair=True,
        invalid_source_recency_claim_repair=True, finance_note_partition_repair=True,
        repair_evidence_catalog=evidence_catalog(context.packet), repair_financial_ids=set(context.finance.value_ids))


def test_preserved_v17_finance_full_canonical_chain_with_actual_upstream():
    context, upstream, raw = load_saved()
    original = json.loads(raw)
    wire, changes = repair(raw, context)
    recency = [change for change in changes if change["op"] == "discard_invalid_source_recency_score"]
    partitions = [change for change in changes if change["op"] == "partition_existing_finance_note_claims"]
    original_bad_recencies = [claim["r"] for field in ("revenue", "costs", "economics")
        for note in original[field] for claim in note["claims"]
        if type(claim.get("r")) in (int, float) and not 0 <= claim["r"] <= 1]
    assert len(recency) == len(original_bad_recencies) == 19
    assert sorted(change["from"] for change in recency) == sorted(original_bad_recencies)
    assert all(change["to"] is None for change in recency)
    assert len(partitions) == 1 and partitions[0]["source_claim_count"] == 10
    assert [len(note.claims) for note in wire.economics] == [8, 2]
    assert sum(len(note.claims) for key in ("revenue", "costs", "economics")
        for note in getattr(wire, key)) + len(wire.gaps) == 24
    original_claims = original["economics"][0]["claims"]
    new_claims = [claim for note in wire.economics for claim in note.claims]
    assert [c.i for c in new_claims] == [c["i"] for c in original_claims]
    assert [c.t for c in new_claims] == [c["t"] for c in original_claims]
    assert [c.f for c in new_claims] == [c["f"] for c in original_claims]
    assert all(note.text.startswith(original["economics"][0]["text"]) for note in wire.economics)
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
    critic_wire = compact_role_output(context, "finance", effective, config_version=CONFIG)
    assert [len(note.claims) for note in critic_wire.economics] == [8, 2]


@pytest.mark.parametrize("value,expected", [(0, 0), (1, 1), (.3, .3), (None, None),
    (-.5, None), (1900, None), (4, None)])
def test_only_finite_out_of_range_source_recency_becomes_missing(value, expected):
    claim = {"i": "C01", "t": "The claim text and all financial data stay unchanged.", "k": "factual",
        "d": "test", "s": "unsupported", "e": [], "f": [], "ss": "none", "q": 0,
        "r": value, "c": "low", "cr": "no_evidence"}
    result, changes = mechanical_repair_json(json.dumps(claim), ClaimWire,
        conservative_claim_repair=True, invalid_source_recency_claim_repair=True)
    assert result.r == expected and result.t == claim["t"] and result.f == []
    assert len(changes) == int(value is not None and not 0 <= value <= 1)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), "1900"])
def test_nonfinite_or_string_recency_is_not_inferred(value):
    claim = {"i": "C01", "t": "The claim text remains unchanged.", "k": "factual", "d": "test",
        "s": "unsupported", "e": [], "f": [], "ss": "none", "q": 0, "r": value,
        "c": "low", "cr": "no_evidence"}
    with pytest.raises(ValueError):
        mechanical_repair_json(json.dumps(claim), ClaimWire, conservative_claim_repair=True,
            invalid_source_recency_claim_repair=True)


def test_partition_cannot_expand_beyond_existing_note_capacity():
    context, _, raw = load_saved()
    data = json.loads(raw)
    data["economics"].append(deepcopy(data["economics"][0]))
    with pytest.raises(ValueError, match="two-note array limit"):
        repair(json.dumps(data), context)


def test_partition_and_recency_repairs_are_disabled_by_default():
    _, _, raw = load_saved()
    with pytest.raises(ValueError):
        mechanical_repair_json(raw, Finance8Wire, conservative_claim_repair=True)
    assert protocol_manifest(CONFIG)["mechanical_claim_repair"] == MECHANICAL_FINANCE_PARTITION_REPAIR_VERSION
