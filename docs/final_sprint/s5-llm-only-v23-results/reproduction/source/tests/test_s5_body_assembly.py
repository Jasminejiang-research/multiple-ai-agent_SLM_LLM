"""Preserved raw-response replay and closed, append-only body assembly checks."""
import json
from pathlib import Path

import pytest

from schemas.compact_wire import ResearchNoteWire, ResearchWire
from schemas.evidence import canonical_hash
from workflow.compact_protocol import (
    GEMINI_8192_BODY_ASSEMBLY_CONFIG_VERSION, MECHANICAL_BODY_ASSEMBLY_REPAIR_VERSION,
    apply_patch_wire, evidence_catalog, expand_role_wire, mechanical_repair_json,
    protocol_manifest,
)
from workflow.contract_context import ContractContext
from workflow.grounding import CitationPollutionError, apply_confidence, validate_grounding


ROOT = Path(__file__).resolve().parents[1]


def repair(raw, schema=ResearchNoteWire, **extra):
    return mechanical_repair_json(raw, schema, conservative_claim_repair=True,
        terminal_punctuation_claim_repair=True, source_disposition_claim_repair=True,
        citation_list_format_claim_repair=True, inline_citation_mirror_claim_repair=True,
        financial_marker_claim_repair=True, source_quality_scale_5_claim_repair=True,
        existing_claim_body_assembly_claim_repair=True, **extra)


def note():
    claim = {"i": "C01", "t": "The original parent sentence is preserved.",
        "k": "factual", "d": "test", "s": "unsupported", "e": [], "f": [],
        "ss": "none", "q": 0, "c": "low", "cr": "no_evidence"}
    return {"topic": "Existing model note", "text": claim["t"] + "  ",
        "why": "This model-proposed statement requires human validation.",
        "c": "low", "cr": "no_evidence", "claims": [claim,
            {**claim, "i": "C02", "t": "The second whole model claim is preserved."},
            {**claim, "i": "C03", "t": "The third whole model claim is preserved."}]}


def test_preserved_v15_b_full_canonical_chain_after_existing_claim_assembly():
    run = ROOT / "docs/final_sprint/s5-llm-only-v15"
    event_path = run / "smokes/ai_education-B/events.jsonl"
    original_bytes = event_path.read_bytes()
    records = [json.loads(line) for line in original_bytes.decode("utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"].get("raw_output"))
    original = json.loads(raw)
    context = ContractContext.from_case(run / "frozen_inputs", "ai_education",
        condition="B", execution_mode="formal_frozen")
    wire, changes = repair(raw, ResearchWire, repair_evidence_catalog=evidence_catalog(context.packet),
        repair_financial_ids=set(context.finance.value_ids))
    assembly = [change for change in changes if change["op"] == "append_existing_same_parent_claim_text"]
    assert len(assembly) == 4
    assert sum(len(getattr(wire, key)[0].claims) for key in ("market", "customer", "competition")) == 7
    for key in ("market", "customer", "competition"):
        before, after = original[key][0], getattr(wire, key)[0]
        assert after.text.startswith(before["text"])
        assert len(after.claims) == len(before["claims"])
        assert [c.e for c in after.claims] == [c["e"] for c in before["claims"]]
        assert all(c.t in after.text for c in after.claims)
    canonical = expand_role_wire(context, "research", wire, version=1)
    context.validate(canonical, version=1)
    accepted = context.accept("research", canonical, version=1)
    effective, _ = apply_confidence(accepted.payload(), context.packet, version=1)
    validate_grounding(effective, context.packet, version=1)
    context.verify_artifact(accepted)
    assert event_path.read_bytes() == original_bytes


def test_append_order_and_original_text_are_exact_and_audited():
    original = note()
    wire, changes = repair(json.dumps(original), repair_evidence_catalog={}, repair_financial_ids=set())
    assert wire.text == original["text"] + " " + original["claims"][1]["t"] + " " + original["claims"][2]["t"]
    assert wire.model_dump(mode="json")["claims"] == ResearchNoteWire.model_validate(original).model_dump(mode="json")["claims"]
    assert [c["appended_text"] for c in changes] == [c["t"] for c in original["claims"][1:]]
    assert all(c["original_parent_sha256"] == canonical_hash(original["text"]) for c in changes)
    assert all(c["novel_content_added"] is False and c["evidence_ids_added"] == [] for c in changes)


def test_punctuation_fix_runs_before_body_assembly():
    original = note()
    original["claims"] = [original["claims"][0]]
    original["text"] = original["claims"][0]["t"][:-1]
    wire, changes = repair(json.dumps(original), repair_evidence_catalog={}, repair_financial_ids=set())
    assert wire.text == original["text"] and wire.claims[0].t == original["text"]
    assert [c["op"] for c in changes] == ["delete_terminal_claim_punctuation"]


@pytest.mark.parametrize("field,invalid,error", [("e", "E99", CitationPollutionError),
    ("f", "invented.value", ValueError)])
def test_assembly_rejects_unknown_structured_references(field, invalid, error):
    original = note()
    original["claims"][1][field] = [invalid]
    with pytest.raises(error):
        repair(json.dumps(original), repair_evidence_catalog={}, repair_financial_ids=set())


def test_assembly_never_truncates_to_fit_dto_body_limit():
    original = note()
    original["text"] = "x" * 880
    with pytest.raises(ValueError):
        repair(json.dumps(original), repair_evidence_catalog={}, repair_financial_ids=set())


def test_disabled_assembly_preserves_old_missing_anchor_behavior():
    original = note()
    wire, changes = mechanical_repair_json(json.dumps(original), ResearchNoteWire,
        conservative_claim_repair=True)
    assert wire.text == original["text"].strip() and changes == []
    assert wire.claims[1].t not in wire.text


def test_explicit_null_patch_text_is_not_accepted_as_noop():
    with pytest.raises(ValueError, match="explicitly null"):
        apply_patch_wire(None, None, None,
            {"claims": [{"issue": "issue001", "i": "claim001", "t": None}]},
            critic_patch_adapter=True)


def test_v19_manifest_inherits_caps_and_critic_adapter():
    manifest = protocol_manifest(GEMINI_8192_BODY_ASSEMBLY_CONFIG_VERSION)
    assert manifest["mechanical_claim_repair"] == MECHANICAL_BODY_ASSEMBLY_REPAIR_VERSION
    assert manifest["critic_patch_adapter"] == "compact-critic-patch-adapter-v1-s5"
    assert set(manifest["role_output_tokens"].values()) == {8192}
