"""Offline acceptance for the explicit S5 LLM-only-after-D-no-go branch."""
from pathlib import Path

import pytest

from evaluation.s4_runner import D_POLICY_STATUS, LLM_ONLY_BRANCH, check_freeze, status
from evaluation.s4_statistics import paired
from evaluation.s5_llm_only import conservative_cost, prepare, run_config
from schemas.compact_wire import ClaimWire
from workflow.compact_protocol import (
    GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION,
    MECHANICAL_FINANCE_NOTICE_REPAIR_VERSION, PROMPT_VERSION, instruction_for,
    prompt_contract, protocol_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/final_sprint/s6-fast-generation-v1/next_s5_entry"
AUTH = ROOT / "docs/final_sprint/s6-fast-generation-v1/LLM_ONLY_S5_INLINE_CITATION_AUTHORIZATION.json"


def test_frozen_abc_config_matches_approved_per_run_limits():
    for arm in "ABC":
        cfg = run_config(arm, "formal")
        assert (cfg.condition, cfg.provider, cfg.model_exact_id) == (arm, "gemini", "gemini-2.5-flash")
        assert (cfg.max_requests, cfg.max_total_tokens, cfg.run_seconds) == (18, 160000, 3600)
        assert cfg.transport_retries == 0 and cfg.max_output_tokens == 8192
        assert cfg.thinking_budget == 1024
        assert cfg.config_version == GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION


def test_gemini_8192_manifest_raises_every_effective_role_cap_without_wire_change():
    manifest = protocol_manifest(GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION)
    assert manifest["wire_version"] == "compact-json-wire-v1-s6"
    assert manifest["prompt_version"] == PROMPT_VERSION
    assert set(manifest["role_output_tokens"].values()) == {8192}
    assert manifest["mechanical_claim_repair"] == MECHANICAL_FINANCE_NOTICE_REPAIR_VERSION


def test_critic_patch_adapter_is_enabled_only_for_new_config():
    from types import SimpleNamespace
    from workflow.contract_generation import ContractGenerator
    from workflow.compact_protocol import GEMINI_8192_FINANCE_MARKER_PREFIX_CONFIG_VERSION

    current = run_config("C", "smoke")
    old = current.model_copy(update={"config_version": GEMINI_8192_FINANCE_MARKER_PREFIX_CONFIG_VERSION})
    assert ContractGenerator(SimpleNamespace(config=current)).critic_patch_adapter is True
    assert ContractGenerator(SimpleNamespace(config=old)).critic_patch_adapter is False
    assert ContractGenerator(SimpleNamespace()).critic_patch_adapter is False


def test_minimal_prompt_keeps_strict_schema_and_brevity_contract():
    for role in ("single", "writer"):
        value = instruction_for(role)
        assert len(value) <= 500
        assert "13 sections in given order" in value
        assert "sentence/claim each" in value
        assert "text=t exactly" in value
        assert "schema-valid" in value
    contract = prompt_contract("single")
    assert contract["section_keys"] == [
        "executive_summary", "problem", "target_customer", "market_opportunity",
        "solution", "value_proposition", "competitor_analysis", "business_model",
        "go_to_market_strategy", "financial_assumptions", "risks_and_mitigations",
        "implementation_roadmap", "appendix"]
    assert contract["claim"]["k"] == ["factual", "assumption", "recommendation", "projection"]
    assert contract["claim"]["c"] == ["low", "medium", "high"]
    assert contract["claim"]["i"] == "claim ID; at least 3 chars; unique within the response"
    assert contract["claim"]["d"] == "brief reason; 2-200 chars"
    assert contract["claim"]["q"] == "0..1; never 1..5"
    assert "recommendation=>p nonempty" in contract["claim"]["rules"][1]
    assert contract["each_section"].startswith("one 40-100 char sentence")
    assert contract["claim"]["t"] == "equal to parent text character-for-character; <=100 chars"
    assert "mirror each e as a separate [E##] token" in contract["claim"]["rules"][2]
    assert prompt_contract("finance")["gaps"] == "0..3 claims"
    assert prompt_contract("research")["exactly_one_object_each"] == [
        "market", "customer", "competition"]


def test_gemini_credential_selection_is_single_named_and_value_free():
    from workflow.review_providers import resolve_gemini_credential

    key, source = resolve_gemini_credential(environment={
        "GOOGLE_API_KEY": "same-secret", "GEMINI_API_KEY": "same-secret"})
    assert (key, source) == ("same-secret", "GOOGLE_API_KEY")
    with pytest.raises(ValueError, match="conflicting"):
        resolve_gemini_credential(environment={
            "GOOGLE_API_KEY": "one", "GEMINI_API_KEY": "two"})
    with pytest.raises(ValueError, match="frozen selection"):
        resolve_gemini_credential(expected_source="GOOGLE_API_KEY",
            environment={"GEMINI_API_KEY": "only"})


def test_approved_claim_id_and_reason_bounds_are_strict():
    base = dict(i="C01", t="abc", k="factual", d="x" * 200, s="unsupported",
        e=[], f=[], ss="none", q=1, c="low", cr="no_evidence")
    assert len(ClaimWire.model_validate(base).d) == 200
    with pytest.raises(ValueError):
        ClaimWire.model_validate({**base, "i": "C1"})
    with pytest.raises(ValueError):
        ClaimWire.model_validate({**base, "d": "x" * 201})


def test_conservative_claim_repair_is_bounded_auditable_and_version_gated():
    import json
    from schemas.evidence import StrictModel
    from workflow.compact_protocol import mechanical_repair_json

    class Envelope(StrictModel):
        claims: list[ClaimWire]

    base = dict(t="abc", k="factual", d="reason", e=[], f=[], ss="direct", q=1,
        c="high", cr="directly_supported")
    raw = json.dumps({"claims": [
        {**base, "i": "P1", "s": "sourced_fact"},
        {**base, "i": "P01", "s": "unsupported", "ss": "none", "cr": "no_evidence"},
    ]})
    with pytest.raises(ValueError):
        mechanical_repair_json(raw, Envelope)
    candidate, changes = mechanical_repair_json(raw, Envelope, conservative_claim_repair=True)
    assert [claim.i for claim in candidate.claims] == ["P001", "P01"]
    repaired = candidate.claims[0]
    assert (repaired.s, repaired.ss, repaired.cr, repaired.e) == (
        "unsupported", "none", "no_evidence", [])
    assert {item["op"] for item in changes} == {
        "pad_claim_id", "downgrade_unsubstantiated_source"}
    assert all(item.get("evidence_ids_added", []) == [] for item in changes)


def test_preserved_v6_response_repair_exposes_exact_span_blocker_without_network():
    import json
    from workflow.compact_protocol import expand_role_wire, mechanical_repair_json
    from workflow.contract_context import ContractContext
    from schemas.compact_wire import ProposalWire

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v6"
    records = [json.loads(line) for line in
        (run_root / "smokes/ai_education-A/events.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"]["status"] != "dispatching")
    candidate, changes = mechanical_repair_json(raw, ProposalWire, conservative_claim_repair=True)
    assert all(len(claim.i) >= 3 for section in candidate.sections for claim in section.claims)
    assert all(not (claim.s == "sourced_fact" and not claim.e)
        for section in candidate.sections for claim in section.claims)
    assert all(item.get("evidence_ids_added", []) == [] for item in changes)
    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education", condition="A")
    with pytest.raises(ValueError, match="exact sentence/span"):
        expand_role_wire(context, "single", candidate, version=1)


def test_terminal_punctuation_repair_replays_v6_to_next_strict_canonical_blocker():
    import json
    from workflow.compact_protocol import expand_role_wire, mechanical_repair_json
    from workflow.contract_context import ContractContext
    from schemas.compact_wire import ProposalWire

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v6"
    records = [json.loads(line) for line in
        (run_root / "smokes/ai_education-A/events.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"]["status"] != "dispatching")
    candidate, changes = mechanical_repair_json(raw, ProposalWire,
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True)
    punctuation_changes = [item for item in changes
        if item["op"] == "delete_terminal_claim_punctuation"]
    assert len(punctuation_changes) == 10
    assert all(item["removed"] == "." and item["removed_codepoint"] == "U+002E"
        and item["words_changed"] is False for item in punctuation_changes)

    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education",
        condition="A", execution_mode="formal_frozen")
    with pytest.raises(ValueError, match="explicit premise"):
        expand_role_wire(context, "single", candidate, version=1)


def test_terminal_punctuation_repair_refuses_word_change_and_old_version_behavior():
    import json
    from workflow.compact_protocol import expand_role_wire, mechanical_repair_json
    from workflow.contract_context import ContractContext
    from schemas.compact_wire import ProposalWire

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v6"
    records = [json.loads(line) for line in
        (run_root / "smokes/ai_education-A/events.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"]["status"] != "dispatching")
    data = json.loads(raw)
    data["sections"][1]["claims"][0]["t"] = "These are different words."
    changed_raw = json.dumps(data)
    candidate, changes = mechanical_repair_json(changed_raw, ProposalWire,
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True)
    assert not any(item["op"] == "delete_terminal_claim_punctuation" and
        item["path"] == "$.sections.1.claims.0.t" for item in changes)
    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education",
        condition="A", execution_mode="formal_frozen")
    with pytest.raises(ValueError, match="exact sentence/span"):
        expand_role_wire(context, "single", candidate, version=1)

    old_candidate, old_changes = mechanical_repair_json(raw, ProposalWire,
        conservative_claim_repair=True)
    assert not any(item["op"] == "delete_terminal_claim_punctuation" for item in old_changes)
    with pytest.raises(ValueError, match="exact sentence/span"):
        expand_role_wire(context, "single", old_candidate, version=1)


def test_preserved_v7_response_exposes_paraphrases_without_mutating_them():
    import json
    from workflow.compact_protocol import expand_role_wire, mechanical_repair_json
    from workflow.contract_context import ContractContext
    from schemas.compact_wire import ProposalWire

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v7"
    records = [json.loads(line) for line in
        (run_root / "smokes/ai_education-A/events.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"]["status"] != "dispatching")
    candidate, changes = mechanical_repair_json(raw, ProposalWire,
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True)
    non_equal = [(section.text, section.claims[0].t) for section in candidate.sections
        if section.text != section.claims[0].t]
    invalid_spans = [(parent_text, claim_text) for parent_text, claim_text in non_equal
        if claim_text not in parent_text]
    assert len(non_equal) == 12
    assert len(invalid_spans) == 10
    assert not any(item.get("op") in {"replace_words", "copy_parent_text"} for item in changes)
    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education",
        condition="A", execution_mode="formal_frozen")
    with pytest.raises(ValueError, match="exact sentence/span"):
        expand_role_wire(context, "single", candidate, version=1)


def test_preserved_v8_response_reaches_inline_citation_blocker_after_safe_repair():
    import json
    from workflow.compact_protocol import expand_role_wire, mechanical_repair_json
    from workflow.contract_context import ContractContext
    from workflow.grounding import validate_grounding
    from schemas.compact_wire import ProposalWire

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v8"
    records = [json.loads(line) for line in
        (run_root / "smokes/ai_education-A/events.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"]["status"] != "dispatching")
    with pytest.raises(ValueError, match="sourced_fact requires factual/direct evidence"):
        mechanical_repair_json(raw, ProposalWire, conservative_claim_repair=True,
            terminal_punctuation_claim_repair=True)
    candidate, changes = mechanical_repair_json(raw, ProposalWire,
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
        source_disposition_claim_repair=True)
    disposition = [item for item in changes
        if item["op"] == "downgrade_invalid_sourced_fact_disposition"]
    assert len(disposition) == 1
    assert disposition[0]["evidence_ids_preserved"] == ["E01", "E02"]
    assert disposition[0]["evidence_ids_added"] == []
    assert disposition[0]["words_changed"] is False
    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education",
        condition="A", execution_mode="formal_frozen")
    artifact = expand_role_wire(context, "single", candidate, version=1)
    with pytest.raises(ValueError, match="missing inline source citation"):
        validate_grounding(artifact, context.packet, version=1)


def test_approved_inline_mirror_replays_v8_through_full_canonical_chain():
    import json
    from schemas.compact_wire import ProposalWire
    from workflow.compact_protocol import (
        evidence_catalog, expand_role_wire, mechanical_repair_json,
    )
    from workflow.contract_context import ContractContext
    from workflow.grounding import apply_confidence, validate_grounding

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v8"
    records = [json.loads(line) for line in
        (run_root / "smokes/ai_education-A/events.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"]["status"] != "dispatching")
    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education",
        condition="A", execution_mode="formal_frozen")
    catalog = evidence_catalog(context.packet)
    candidate, changes = mechanical_repair_json(raw, ProposalWire,
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
        source_disposition_claim_repair=True, citation_list_format_claim_repair=True,
        inline_citation_mirror_claim_repair=True,
        repair_evidence_catalog=catalog)
    mirrored = [item for item in changes
        if item["op"] == "mirror_selected_evidence_ids_inline"]
    assert mirrored
    assert all(item["evidence_ids_added"] == [] and
        item["evidence_ids_deleted"] == [] and item["words_changed"] is False
        for item in mirrored)
    assert all(item["mapped_source_ids"] ==
        [catalog[eid]["source_id"] for eid in item["evidence_ids_mirrored"]]
        for item in mirrored)
    artifact = expand_role_wire(context, "single", candidate, version=1)
    validate_grounding(artifact, context.packet, version=1)
    effective, _ = apply_confidence(artifact, context.packet, version=1)
    validate_grounding(effective, context.packet, version=1)


def test_inline_mirror_refuses_unknown_or_unselected_evidence_ids():
    import json
    from schemas.compact_wire import ProposalWire
    from workflow.compact_protocol import evidence_catalog, mechanical_repair_json
    from workflow.contract_context import ContractContext

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v8"
    records = [json.loads(line) for line in
        (run_root / "smokes/ai_education-A/events.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"]["status"] != "dispatching")
    data = json.loads(raw)
    target = next(section for section in data["sections"]
        if section["claims"][0].get("e"))
    target["claims"][0]["e"] = ["E99"]
    target["claims"][0]["t"] = target["text"].replace("[E01]", "").strip()
    target["text"] = target["claims"][0]["t"]
    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education",
        condition="A", execution_mode="formal_frozen")
    candidate, changes = mechanical_repair_json(json.dumps(data), ProposalWire,
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
        source_disposition_claim_repair=True, citation_list_format_claim_repair=True,
        inline_citation_mirror_claim_repair=True,
        repair_evidence_catalog=evidence_catalog(context.packet))
    assert candidate
    assert not any(item["op"] == "mirror_selected_evidence_ids_inline" and
        "E99" in item["evidence_ids_mirrored"] for item in changes)


def test_preserved_v10_finance_response_remains_rejected_for_five_gaps():
    import json
    from pydantic import ValidationError
    from schemas.compact_wire import FinanceWire
    from workflow.compact_protocol import evidence_catalog, mechanical_repair_json
    from workflow.contract_context import ContractContext

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v10"
    records = [json.loads(line) for line in
        (run_root / "smokes/ai_education-B/events.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"].get("role") == "finance"
        and event["payload"]["status"] == "invalid_output")
    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education",
        condition="B", execution_mode="formal_frozen")
    with pytest.raises(ValidationError, match="at most 3 items"):
        mechanical_repair_json(raw, FinanceWire,
            conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
            source_disposition_claim_repair=True, citation_list_format_claim_repair=True,
            inline_citation_mirror_claim_repair=True,
            repair_evidence_catalog=evidence_catalog(context.packet))


def test_preserved_v11_research_response_remains_rejected_for_two_market_items():
    import json
    from pydantic import ValidationError
    from schemas.compact_wire import ResearchWire
    from workflow.compact_protocol import evidence_catalog, mechanical_repair_json
    from workflow.contract_context import ContractContext

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v11"
    records = [json.loads(line) for line in
        (run_root / "smokes/ai_education-B/events.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"].get("role") == "research"
        and event["payload"]["status"] == "invalid_output")
    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education",
        condition="B", execution_mode="formal_frozen")
    with pytest.raises(ValidationError, match="at most 1 item"):
        mechanical_repair_json(raw, ResearchWire,
            conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
            source_disposition_claim_repair=True, citation_list_format_claim_repair=True,
            inline_citation_mirror_claim_repair=True,
            repair_evidence_catalog=evidence_catalog(context.packet))


def test_preserved_v12_response_passes_full_chain_after_structured_finance_marker_repair():
    import json
    from schemas.compact_wire import ProposalWire
    from workflow.compact_protocol import expand_role_wire, evidence_catalog, mechanical_repair_json
    from workflow.contract_context import ContractContext
    from workflow.grounding import apply_confidence, validate_grounding

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v12"
    records = [json.loads(line) for line in
        (run_root / "smokes/ai_education-A/events.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"].get("role") == "single"
        and event["payload"]["status"] == "succeeded")
    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education",
        condition="A", execution_mode="formal_frozen")
    candidate, changes = mechanical_repair_json(raw, ProposalWire,
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
        source_disposition_claim_repair=True, citation_list_format_claim_repair=True,
        inline_citation_mirror_claim_repair=True, financial_marker_claim_repair=True,
        repair_evidence_catalog=evidence_catalog(context.packet),
        repair_financial_ids=set(context.finance.value_ids))
    marker_changes = [item for item in changes
        if item["op"] == "remove_structured_financial_marker_from_prose"]
    assert len(marker_changes) == 1
    assert marker_changes[0]["financial_value_ids_selected"] == ["high.break_even_users"]
    assert marker_changes[0]["financial_value_ids_added"] == []
    assert marker_changes[0]["financial_value_ids_deleted"] == []
    assert marker_changes[0]["words_changed"] is False
    artifact = expand_role_wire(context, "single", candidate, version=1)
    validate_grounding(artifact, context.packet, version=1)
    effective, _ = apply_confidence(artifact, context.packet, version=1)
    validate_grounding(effective, context.packet, version=1)
    claim = artifact.financial_assumptions.key_claims[0]
    assert claim.financial_value_ids == ["high.break_even_users"]
    assert "[high.break_even_users]" not in claim.claim_text


def test_preserved_v13_response_passes_full_chain_after_F_prefix_marker_repair():
    import json
    from schemas.compact_wire import ProposalWire
    from workflow.compact_protocol import expand_role_wire, evidence_catalog, mechanical_repair_json
    from workflow.contract_context import ContractContext
    from workflow.grounding import apply_confidence, validate_grounding

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v13"
    records = [json.loads(line) for line in
        (run_root / "smokes/ai_education-A/events.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"].get("role") == "single"
        and event["payload"]["status"] == "succeeded")
    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education",
        condition="A", execution_mode="formal_frozen")
    candidate, changes = mechanical_repair_json(raw, ProposalWire,
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
        source_disposition_claim_repair=True, citation_list_format_claim_repair=True,
        inline_citation_mirror_claim_repair=True, financial_marker_claim_repair=True,
        repair_evidence_catalog=evidence_catalog(context.packet),
        repair_financial_ids=set(context.finance.value_ids))
    marker_changes = [item for item in changes
        if item["op"] == "remove_structured_financial_marker_from_prose"]
    assert len(marker_changes) == 3
    tokens = [token for item in marker_changes
        for token in item["financial_marker_tokens_removed"]]
    assert tokens == ["[F-subscription_price]", "[F-starting_cash]",
        "[F-fixed_operating_cost]", "[F-base.break_even_users]"]
    assert all(item["financial_value_ids_added"] == [] and
        item["financial_value_ids_deleted"] == [] and item["words_changed"] is False
        for item in marker_changes)
    artifact = expand_role_wire(context, "single", candidate, version=1)
    validate_grounding(artifact, context.packet, version=1)
    effective, _ = apply_confidence(artifact, context.packet, version=1)
    validate_grounding(effective, context.packet, version=1)
    assert artifact.business_model.key_claims[0].financial_value_ids == ["subscription_price"]
    assert artifact.financial_assumptions.key_claims[0].financial_value_ids == [
        "starting_cash", "fixed_operating_cost"]


def test_preserved_v14_response_passes_full_chain_after_source_quality_scale_repair():
    import json
    from schemas.compact_wire import ProposalWire
    from workflow.compact_protocol import expand_role_wire, evidence_catalog, mechanical_repair_json
    from workflow.contract_context import ContractContext
    from workflow.grounding import apply_confidence, validate_grounding

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v14"
    records = [json.loads(line) for line in
        (run_root / "smokes/ai_education-A/events.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"].get("role") == "single"
        and event["payload"]["status"] == "invalid_output")
    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education",
        condition="A", execution_mode="formal_frozen")
    candidate, changes = mechanical_repair_json(raw, ProposalWire,
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
        source_disposition_claim_repair=True, citation_list_format_claim_repair=True,
        inline_citation_mirror_claim_repair=True, financial_marker_claim_repair=True,
        source_quality_scale_5_claim_repair=True,
        repair_evidence_catalog=evidence_catalog(context.packet),
        repair_financial_ids=set(context.finance.value_ids))
    quality_changes = [item for item in changes
        if item["op"] == "normalize_source_quality_scale_5_to_unit"]
    assert len(quality_changes) == 11
    assert {item["from"] for item in quality_changes} <= {2, 3, 4, 5}
    assert {item["to"] for item in quality_changes} <= {.4, .6, .8, 1.0}
    assert all(item["words_changed"] is False and item["evidence_ids_added"] == []
        and item["evidence_ids_deleted"] == [] for item in quality_changes)
    artifact = expand_role_wire(context, "single", candidate, version=1)
    validate_grounding(artifact, context.packet, version=1)
    effective, _ = apply_confidence(artifact, context.packet, version=1)
    validate_grounding(effective, context.packet, version=1)


def test_source_quality_scale_repair_leaves_one_and_noninteger_invalid_values_unchanged():
    import json
    from schemas.evidence import StrictModel
    from workflow.compact_protocol import mechanical_repair_json

    class Envelope(StrictModel):
        claims: list[ClaimWire]

    base = dict(i="C01", t="abc", k="factual", d="reason", s="unsupported",
        e=[], f=[], ss="none", c="low", cr="no_evidence")
    candidate, changes = mechanical_repair_json(json.dumps({"claims": [{**base, "q": 1}]}),
        Envelope, conservative_claim_repair=True, source_quality_scale_5_claim_repair=True)
    assert candidate.claims[0].q == 1
    assert not any(item["op"] == "normalize_source_quality_scale_5_to_unit" for item in changes)
    with pytest.raises(ValueError):
        mechanical_repair_json(json.dumps({"claims": [{**base, "q": 1.5}]}), Envelope,
            conservative_claim_repair=True, source_quality_scale_5_claim_repair=True)


def test_compact_claim_mirrors_selected_short_id_to_frozen_source_id():
    from workflow.compact_protocol import _expand_claim, evidence_catalog
    from workflow.contract_context import ContractContext

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v8"
    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education",
        condition="A", execution_mode="formal_frozen")
    catalog = evidence_catalog(context.packet)
    wire = ClaimWire(i="C01", t="Supported frozen claim [E01]", k="factual", d="test",
        s="sourced_fact", e=["E01"], f=[], ss="direct", q=1, c="high",
        cr="directly_supported")
    claim = _expand_claim(wire, context, 1)
    frozen_marker = f"[{catalog['E01']['source_id']}]"
    assert claim.claim_text == f"Supported frozen claim {frozen_marker}"
    assert claim.content_anchor == claim.claim_text
    assert claim.source_ids == [catalog["E01"]["source_id"]]


def test_preserved_v9_response_passes_full_canonical_chain_after_format_repair():
    import json
    from schemas.compact_wire import ProposalWire
    from workflow.compact_protocol import expand_role_wire, mechanical_repair_json
    from workflow.contract_context import ContractContext
    from workflow.grounding import apply_confidence, validate_grounding

    run_root = ROOT / "docs/final_sprint/s5-llm-only-v9"
    records = [json.loads(line) for line in
        (run_root / "smokes/ai_education-A/events.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = next(event["payload"]["raw_output"] for event in records
        if event["kind"] == "call" and event["payload"]["status"] != "dispatching")
    candidate, changes = mechanical_repair_json(raw, ProposalWire,
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
        source_disposition_claim_repair=True, citation_list_format_claim_repair=True)
    format_changes = [item for item in changes
        if item["op"] == "split_compact_citation_bracket_list"]
    assert len(format_changes) == 1
    assert format_changes[0]["from"] == "[E03, E04]"
    assert format_changes[0]["to"] == "[E03] [E04]"
    assert format_changes[0]["evidence_ids"] == ["E03", "E04"]
    assert format_changes[0]["evidence_ids_added"] == []
    assert format_changes[0]["words_changed"] is False
    context = ContractContext.from_case(run_root / "frozen_inputs", "ai_education",
        condition="A", execution_mode="formal_frozen")
    artifact = expand_role_wire(context, "single", candidate, version=1)
    validate_grounding(artifact, context.packet, version=1)
    effective, _ = apply_confidence(artifact, context.packet, version=1)
    validate_grounding(effective, context.packet, version=1)


def test_inline_citation_authorization_is_versioned_and_evidence_closed():
    import json
    record = json.loads(AUTH.read_text(encoding="utf-8"))
    repair = record["mechanical_repair_change"]
    assert record["approved"] is True
    assert repair["version"] == MECHANICAL_FINANCE_NOTICE_REPAIR_VERSION
    assert repair["append_existing_same_parent_claim_text_only"] is True
    assert repair["preserve_original_body_verbatim"] is True
    assert repair["delete_terminal_punctuation_on_exact_parent_match"] is True
    assert repair["max_terminal_characters_deleted"] == 1
    assert repair["normalize_invalid_sourced_fact_disposition"] is True
    assert repair["may_change_words"] is False
    assert repair["may_add_evidence_ids"] is False
    assert repair["may_mechanically_insert_inline_citations"] is True
    assert repair["mirror_only_selected_frozen_evidence_ids"] is True
    assert repair["remove_only_selected_frozen_financial_markers_from_prose"] is True
    assert repair["accepted_financial_marker_forms_for_removal"] == [
        "[<selected frozen f ID>]", "[F-<selected frozen f ID>]"]
    assert repair["normalize_integer_source_quality_scale_5_to_unit"] is True
    assert repair["q_equals_1_unchanged"] is True
    assert repair["other_invalid_q_rejected"] is True
    assert repair["split_compact_citation_bracket_lists"] is True
    assert record["prompt_change"]["text_equals_claim_required"] is True
    assert record["prompt_change"]["mirror_selected_evidence_ids_inline"] is True
    assert record["prompt_change"]["finance_gap_max_items"] == 3
    assert record["prompt_change"]["exactly_one_object_per_named_main_array"] is True
    assert record["external_data_authorization"]["credential_source_variable"] == "GOOGLE_API_KEY"
    assert record["contingent_quality_tolerance_authorization"]["enabled_in_this_version"] is False


def test_cost_accounting_includes_non_candidate_tokens_at_output_rate():
    assert conservative_cost(1000, 200, 1500) == pytest.approx(.00155)
    with pytest.raises(ValueError):
        conservative_cost(1000, 600, 1500)


def test_prepare_preserves_eight_rows_and_seals_D_without_formal_start(tmp_path):
    experiment = tmp_path / "llm-only"
    result = prepare(SOURCE, experiment, AUTH)
    state = status(experiment)
    assert result["planned_rows"] == 8 and result["D_rows_sealed"] == 2
    assert state["formal_runs_started"] == 0
    assert len(state["rows"]) == 8
    assert [row["planned_id"] for row in state["rows"]] == [
        "ai_education-A", "ai_education-D", "ai_education-B", "ai_education-C",
        "intelligent_ring-C", "intelligent_ring-B", "intelligent_ring-D", "intelligent_ring-A"]
    d_rows = [row for row in state["rows"] if row["condition"] == "D"]
    assert all(row["execution"] == D_POLICY_STATUS and row["run_id"] is None for row in d_rows)
    freeze = __import__("json").loads((experiment / "freeze.json").read_text(encoding="utf-8"))
    assert freeze["execution_branch"] == LLM_ONLY_BRANCH
    assert set(freeze["configs"]) == set("ABC")
    assert freeze["comparison_policy"]["unavailable"] == {"C-D": "D_preflight_no_go"}


def test_prepare_does_not_bypass_smoke_or_frozen_inventory_gates(tmp_path):
    experiment = tmp_path / "llm-only"
    prepare(SOURCE, experiment, AUTH)
    gate = check_freeze(experiment)
    assert not gate["ready"]
    assert "S6 compact protocol/common 30/60 limits are not frozen" not in gate["blockers"]
    assert "formal freeze pending (S4 is engineering/offline only)" in gate["blockers"]
    assert all(f"{arm} real smoke with matching common config pending" in gate["blockers"] for arm in "ABC")


def test_llm_only_pairing_reports_only_authorized_comparisons():
    rows = [
        {"case_id": case, "condition": arm, "metric": value, "metric_state": "observed",
         "execution": "succeeded"}
        for case, offset in (("ai_education", 0), ("intelligent_ring", 10))
        for arm, value in (("A", 1 + offset), ("B", 2 + offset), ("C", 4 + offset))
    ]
    details, summaries = paired(rows, "metric", comparisons=(("B", "A"), ("C", "B")))
    assert {row["comparison"] for row in details + summaries} == {"B-A", "C-B"}
    assert all(row["complete_pairs"] == 2 for row in summaries)
