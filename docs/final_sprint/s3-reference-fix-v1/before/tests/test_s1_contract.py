"""Offline engineering fixtures; no real model or human quality verdicts."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from schemas.contract_outputs import (ContractProposal, ContractResearchAnalysis, ContractStrategyAnalysis,
    ContractFinanceAssumptions, CONTRACT_VERSION)
from schemas.evidence import EvidencePacket, GroundedClaim, HumanSupportVerdict, canonical_hash
from schemas.financial import FinancialValue
from schemas.workflow import ProposalDraft, PROPOSAL_SECTION_FIELD_NAMES, PROPOSAL_SECTION_TITLES
from workflow.contract_context import ContractContext
from workflow.contract_generation import ContractGenerator
from workflow.evidence_policy import frozen_evidence_scope, FrozenEvidenceAccessError
from workflow.finance_contract import FinanceContract
from workflow.generation_batches import CONTRACT_BATCH_MODELS, PROPOSAL_SECTION_BATCHES
from workflow.grounding import (aggregate_confidence, apply_confidence, CitationPollutionError,
                                validate_grounding, validate_lineage)
from workflow.llm_client import StructuredOutputValidationError

ROOT = Path(__file__).resolve().parents[1] / "docs/final_sprint/s0-v1"


@pytest.fixture
def context():
    return ContractContext.from_case(ROOT, "ai_education", condition="C")


def claim(context, **overrides):
    chunk = context.packet.chunks[0]
    source = next(s for s in context.packet.sources if s.source_id == chunk.source_id)
    text = "The archived source includes the quoted pricing excerpt."
    result = dict(claim_id="research.pricing", parent_claim_id=None, claim_text=text,
        claim_type="factual", claim_domain="competitor", evidence_status="sourced_fact",
        source_ids=[source.source_id], source_support="direct", source_quality=.9, source_recency=None,
        support_assessed_by="model_proposed", critic_status="not_reviewed", decision_critical=True,
        high_impact=False, conflict=False, pruned=False, major_issue=False,
        confidence="low", confidence_reason="no_evidence", content_anchor=text,
        source_anchors=[dict(source_id=source.source_id, chunk_id=chunk.chunk_id,
            line_start=chunk.line_start, line_end=chunk.line_end, snapshot_sha256=source.txt_sha256,
            quote=chunk.text)], financial_value_ids=[], premise="", artifact_version=1)
    result.update(overrides)
    return result


def component_payload(context, role, *, version=1):
    c = claim(context, artifact_version=version)
    item = dict(topic="Pricing evidence", rationale=c["claim_text"] + " Source support is a proposed relationship.",
                confidence="low", confidence_reason="no_evidence", claims=[c])
    result = dict(analysis_summary="Synthetic analysis for offline contract checks only.", needs_human_review=[])
    if role == "research":
        item["finding"] = c["claim_text"]
        result.update({key: [deepcopy(item)] for key in ("market_trends", "customer_notes", "competitor_assumptions")})
        result["unsupported_claims"] = []
    elif role == "strategy":
        item["recommendation"] = c["claim_text"]
        result.update({key: [deepcopy(item)] for key in ("value_proposition", "business_model_logic", "gtm_strategy", "moat_hypotheses")})
        result["unsupported_market_data"] = []
    else:
        item.update(assumption=c["claim_text"], value_ids=["base.monthly_revenue"], needs_validation=[])
        result.update({key: [deepcopy(item)] for key in ("revenue_assumptions", "cost_assumptions", "unit_economics_assumptions")})
        result.update(break_even_discussion="All financial results describe assumptions in an offline scenario.",
            assumption_notice="These values are scenario assumptions, not forecasts or measured outcomes.",
            unsupported_financial_claims=[], financial_values=[v.model_dump(mode="json") for v in context.finance.expected_values()])
    return result


def proposal_payload(context, *, version=1):
    result = {"title": "Synthetic contract validation proposal"}
    for key, title in zip(PROPOSAL_SECTION_FIELD_NAMES, PROPOSAL_SECTION_TITLES, strict=True):
        c = claim(context, artifact_version=version)
        result[key] = dict(title=title, content=c["claim_text"] + f" [{c['source_ids'][0]}] This text is a synthetic engineering fixture.",
            key_claims=[c], source_ids=c["source_ids"], confidence="low", confidence_reason="no_evidence")
    result["financial_assumptions"]["financial_values"] = [v.model_dump(mode="json") for v in context.finance.expected_values()]
    return result


class FakeClient:
    def __init__(self, context):
        self.context = context
        self.calls = []
        self.before = None

    def generate_structured_once(self, prompt, schema, **kwargs):
        self.calls.append((prompt, schema, kwargs))
        if self.before:
            self.before(prompt, schema)
        roles = {ContractResearchAnalysis: "research", ContractStrategyAnalysis: "strategy", ContractFinanceAssumptions: "finance"}
        if schema in roles:
            payload = component_payload(self.context, roles[schema])
        else:
            full = proposal_payload(self.context)
            payload = {key: full[key] for key in schema.model_fields}
        return schema.model_validate(payload)


@pytest.mark.parametrize("case_id", ["ai_education", "intelligent_ring"])
def test_s0_packet_and_complete_brief_are_shared_by_all_conditions(case_id):
    contexts = [ContractContext.from_case(ROOT, case_id, condition=c) for c in "ABCD"]
    assert len({c.packet_sha256 for c in contexts}) == 1
    assert len({c.brief_sha256 for c in contexts}) == 1
    for ctx in contexts:
        assert "financial_inputs" in ctx.input_payload("research")["user_brief"]
        assert "decision_questions" in ctx.brief
        assert ctx.packet.review_status == "pending"
        assert all(s.human_support_status == "pending" for s in ctx.packet.sources)


def test_packet_is_copy_isolated_and_rechecks_hash(context):
    modified = context.packet.model_dump(mode="json", exclude_unset=True)
    modified["chunks"][0]["text"] = "tampered"
    with pytest.raises(ValueError, match="hash"):
        EvidencePacket.model_validate(modified)
    detached = context.packet
    detached.chunks[0].text = "mutated"
    assert context.packet.chunks[0].text != "mutated"
    detached_brief = context.brief
    detached_brief["financial_inputs"] = {}
    assert context.brief["financial_inputs"]


@pytest.mark.parametrize("mutation", ["allowlist", "duplicate_chunk", "location", "snapshot", "path"])
def test_packet_detects_structural_and_snapshot_tampering(context, mutation):
    raw = context.packet.model_dump(mode="json", exclude_unset=True)
    if mutation == "allowlist": raw["allowlist_urls"] = []
    if mutation == "duplicate_chunk": raw["chunks"].append(deepcopy(raw["chunks"][0]))
    if mutation == "location": raw["chunks"][0]["line_start"] += 1
    if mutation == "snapshot": raw["sources"][0]["txt_sha256"] = "0" * 64
    if mutation == "path": raw["sources"][0]["txt_path"] = "../outside.txt"
    raw["packet_sha256"] = canonical_hash({k:v for k,v in raw.items() if k != "packet_sha256"})
    with pytest.raises(ValueError):
        EvidencePacket.model_validate(raw).verify_snapshots(ROOT)


def test_formal_case_approval_is_required():
    with pytest.raises(ValueError, match="approval"):
        ContractContext.from_case(ROOT, "ai_education", condition="A", execution_mode="formal_frozen")


def test_web_and_rag_have_the_same_confidence_rules(context):
    web = context.accept("writer", proposal_payload(context)).payload()
    raw = context.packet.model_dump(mode="json", exclude_unset=True)
    for source in raw["sources"]: source["source_type"] = "rag"
    raw["packet_sha256"] = canonical_hash({k:v for k,v in raw.items() if k != "packet_sha256"})
    rag, _ = apply_confidence(ContractProposal.model_validate(proposal_payload(context)), EvidencePacket.model_validate(raw), version=1)
    assert web.problem.confidence == rag.problem.confidence == "high"
    # Eligible labels do not create human Gold verdicts or assert verified truth.
    assert HumanSupportVerdict(claim_id="research.pricing", artifact_sha256="fixture").verdict == "pending"


def test_ordinary_assumptions_do_not_make_supported_facts_low(context):
    factual = GroundedClaim.model_validate(claim(context))
    assumption = GroundedClaim.model_validate(claim(context, claim_id="scenario.assumption", claim_type="assumption",
        evidence_status="assumption", source_ids=[], source_anchors=[], source_support="none", premise="hypothetical user choice"))
    assert aggregate_confidence([factual, assumption]) == ("medium", "assumption_dominant")
    assert aggregate_confidence([factual, factual.model_copy(update={"claim_id":"second"}), assumption])[0] == "high"


@pytest.mark.parametrize("overrides,reason", [
    ({"evidence_status":"unsupported", "source_ids":[], "source_anchors":[], "source_support":"none", "high_impact":True}, "no_evidence"),
    ({"evidence_status":"needs_validation", "source_support":"partial"}, "partial_support"),
    ({"conflict":True}, "conflict"), ({"pruned":True}, "pruned"),
    ({"critic_status":"unverified_after_revision"}, "critic_unresolved"),
    ({"major_issue":True}, "critic_unresolved"),
])
def test_confidence_blocks_unsupported_conflict_pruned_unverified(context, overrides, reason):
    value = GroundedClaim.model_validate(claim(context, confidence="high", **overrides))
    assert aggregate_confidence([value]) == ("low", reason)


@pytest.mark.parametrize("mutation", ["source", "inline", "url", "chunk", "hash", "quote", "anchor", "source_loss", "new_gold"])
def test_source_and_claim_contract_errors(context, mutation):
    payload = proposal_payload(context)
    c = payload["problem"]["key_claims"][0]
    if mutation == "source": c["source_ids"] = ["MADE-UP"]; c["source_anchors"][0]["source_id"] = "MADE-UP"
    if mutation == "inline": payload["problem"]["content"] += " [MADE-UP]"
    if mutation == "url": payload["problem"]["content"] += " https://invented.invalid/source"
    if mutation == "chunk": c["source_anchors"][0]["chunk_id"] = "invented"
    if mutation == "hash": c["source_anchors"][0]["snapshot_sha256"] = "0"*64
    if mutation == "quote": c["source_anchors"][0]["quote"] = "not in archived text"
    if mutation == "anchor": c["content_anchor"] = "missing from prose"
    if mutation == "source_loss": payload["problem"]["source_ids"] = []
    if mutation == "new_gold": c["human_verdict"] = "supported"
    with pytest.raises(ValueError):
        context.accept("writer", payload)


def test_all_13_sections_and_full_finance_are_required(context):
    payload = proposal_payload(context)
    del payload["appendix"]
    with pytest.raises(ValueError): context.accept("writer", payload)
    payload = proposal_payload(context)
    payload["appendix"]["title"] = "Unexpected"
    with pytest.raises(ValueError): context.accept("writer", payload)
    payload = proposal_payload(context)
    payload["financial_assumptions"]["financial_values"] = []
    with pytest.raises(ValueError): context.accept("writer", payload)


@pytest.mark.parametrize("case_id,ending_cash,break_even", [
    ("ai_education", "57000.00", "500"), ("intelligent_ring", "698576.00", "3176")])
def test_decimal_recomputation_against_independent_known_values(case_id, ending_cash, break_even):
    ctx = ContractContext.from_case(ROOT, case_id, condition="A")
    rows = ctx.finance.expected_values()
    ctx.finance.validate(rows)
    by_id = {v.value_id:v for v in rows}
    assert by_id["base.ending_cash"].value == Decimal(ending_cash)
    suffix = "break_even_users" if case_id == "ai_education" else "break_even_units"
    assert by_id["base." + suffix].value == Decimal(break_even)


@pytest.mark.parametrize("mutation", ["value", "unit", "currency", "period", "formula", "input", "origin", "missing", "duplicate", "rounding"])
def test_finance_contract_rejects_wrong_results_and_metadata(context, mutation):
    rows = context.finance.expected_values()
    if mutation == "value": rows[0].value += Decimal(".02")
    if mutation == "unit": rows[0].unit = "EUR/month"
    if mutation == "currency": rows[0].currency = "EUR"
    if mutation == "period": rows[0].period = "year_1"
    if mutation == "formula": rows[0].formula_id = "invented"
    if mutation == "input": rows[0].input_ids = ["invented"]
    if mutation == "origin": rows[0].origin = "user_input"
    if mutation == "missing": rows.pop()
    if mutation == "duplicate": rows.append(rows[0])
    if mutation == "rounding": rows[0].value += Decimal(".001")
    with pytest.raises(ValueError): context.finance.validate(rows)


def test_money_tolerance_and_exact_counts(context):
    rows = context.finance.expected_values()
    rows[0].value += Decimal(".01")
    context.finance.validate(rows)
    next(r for r in rows if r.value_id == "base.break_even_users").value += 1
    with pytest.raises(ValueError): context.finance.validate(rows)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", True])
def test_nonfinite_financial_values_are_rejected(context, value):
    row = context.finance.expected_values()[0].model_dump()
    row["value"] = value
    with pytest.raises(ValueError): FinancialValue.model_validate(row)


def test_zero_contribution_is_explicit_not_applicable(context):
    brief = context.brief
    brief["financial_inputs"]["subscription_price"]["value"] = 4
    finance = FinanceContract("ai_education", brief, set(context.packet.allowlist_source_ids))
    finance.validate(finance.expected_values())
    row = next(r for r in finance.expected_values() if r.value_id == "base.break_even_users")
    assert row.value is None and row.status == "not_applicable" and row.reason


@pytest.mark.parametrize("condition", list("ABCD"))
def test_common_generation_path_and_first_research_evidence(condition, tmp_path):
    ctx = ContractContext.from_case(ROOT, "ai_education", condition=condition)
    client = FakeClient(ctx)
    generator = ContractGenerator(client)
    upstream = []
    if condition != "A":
        for role in ("research", "strategy", "finance"):
            upstream.append(generator.generate(ctx, role, upstream=tuple(upstream)))
    result = generator.generate(ctx, "single" if condition == "A" else "writer", upstream=tuple(upstream))
    assert len(client.calls) == (4 if condition == "A" else 7)  # S1 primitives, no S2 Critic graph.
    assert [len(fields) for fields in PROPOSAL_SECTION_BATCHES] == [4, 3, 3, 3]
    assert tuple(c[1] for c in client.calls[-4:]) == CONTRACT_BATCH_MODELS
    for prompt, _, kwargs in client.calls:
        assert ctx.packet_sha256 in prompt
        assert ctx.packet.chunks[0].text.splitlines()[1] in prompt
        assert kwargs["temperature"] == 0
    assert all(t.first_output_passed for t in generator.tasks)
    assert result.contract_version == CONTRACT_VERSION
    assert ctx.review_input(result)["evidence_packet"]["packet_sha256"] == ctx.packet_sha256
    output = ctx.export(result, tmp_path / condition)
    saved = json.loads((output / "proposal.json").read_text(encoding="utf-8"))
    assert saved["packet_sha256"] == ctx.packet_sha256
    assert saved["payload"]["problem"]["key_claims"][0]["source_anchors"]
    assert len([line for line in (output / "proposal.md").read_text(encoding="utf-8").splitlines() if line.startswith("## ")]) == 13
    with pytest.raises(FileExistsError): ctx.export(result, output)


def test_a_cannot_invoke_specialists(context):
    ctx = ContractContext.from_case(ROOT, "ai_education", condition="A")
    generator = ContractGenerator(FakeClient(ctx))
    with pytest.raises(ValueError, match="only one"): generator.generate(ctx, "research")
    assert generator.tasks == []


def test_first_schema_failure_is_never_rewritten_after_repair(context):
    client = FakeClient(context)
    def fail_once(*args):
        if len(client.calls) == 1:
            raise StructuredOutputValidationError("bad first JSON", raw_output="{broken")
    client.before = fail_once
    records = []
    generator = ContractGenerator(client, task_sink=records.append)
    generator.generate(context, "research")
    task = generator.tasks[0]
    assert not task.first_output_passed
    assert [a.passed for a in task.attempts] == [False, True]
    assert [a.purpose for a in task.attempts] == ["generate", "structure_repair"]
    assert task.attempts[0].raw_output == "{broken"
    assert records[-1]["first_output_passed"] is False
    with pytest.raises(ValueError, match="already triggered"): generator.generate(context, "research")
    assert len(client.calls) == 2


def test_only_one_repair_and_timeout_not_repaired(context):
    for error in (StructuredOutputValidationError("invalid"), TimeoutError("timeout")):
        client = FakeClient(context)
        def fail(*args): raise error
        client.before = fail
        generator = ContractGenerator(client)
        with pytest.raises(type(error)): generator.generate(context, "research")
        assert len(client.calls) == (2 if isinstance(error, StructuredOutputValidationError) else 1)
        assert not generator.tasks[0].first_output_passed


def test_source_pollution_is_fatal_without_silent_patch(context):
    client = FakeClient(context)
    def polluted(prompt, schema, **kwargs):
        data = component_payload(context, "research")
        for group in ("market_trends", "customer_notes", "competitor_assumptions"):
            c = data[group][0]["claims"][0]
            c["source_ids"] = ["invented"]
            c["source_anchors"][0]["source_id"] = "invented"
        client.calls.append((prompt, schema, kwargs))
        return schema.model_validate(data)
    client.generate_structured_once = polluted
    generator = ContractGenerator(client)
    with pytest.raises(CitationPollutionError): generator.generate(context, "research")
    assert len(client.calls) == 1
    assert not generator.tasks[0].first_output_passed


def test_review_revision_preserve_source_and_pending_semantics(context):
    original = context.accept("writer", proposal_payload(context), unresolved_major=True)
    revised = context.accept("writer", proposal_payload(context, version=2), version=2, previous=original)
    assert original.version == 1 and revised.version == 2
    assert revised.payload().problem.confidence == "low"
    assert revised.payload().problem.confidence_reason == "critic_unresolved"
    assert revised.unresolved_major
    lost = proposal_payload(context, version=2)
    for field in PROPOSAL_SECTION_FIELD_NAMES:
        c = lost[field]["key_claims"][0]
        c.update(source_ids=[], source_anchors=[], evidence_status="unsupported", source_support="none")
        lost[field]["source_ids"] = []
        lost[field]["content"] = lost[field]["content"].replace(" [EDU-01]", "")
    with pytest.raises(ValueError, match="lost upstream"):
        context.accept("writer", lost, version=2, previous=original)


def test_cannot_upgrade_unsupported_factual_claim_without_new_evidence(context):
    old = GroundedClaim.model_validate(claim(context, evidence_status="needs_validation", source_support="partial"))
    new = GroundedClaim.model_validate(claim(context, artifact_version=2))
    with pytest.raises(ValueError, match="without new evidence"):
        validate_lineage(old, new, revision=True)


def test_wrong_case_handoff_rejected(context):
    original = context.accept("research", component_payload(context, "research"))
    other = ContractContext.from_case(ROOT, "intelligent_ring", condition="C")
    with pytest.raises(ValueError, match="different input"): other.review_input(original)


def test_frozen_scope_blocks_live_web_rag_and_restores_product_mode(monkeypatch, context):
    from agents.research import ResearchAgent
    from tools.web_search import search_web
    from tools.tavily_search import TavilySearchClient
    from rag.retriever import retrieve
    from rag.knowledge_base import retrieve_writer_evidence, load_knowledge_base_documents
    monkeypatch.setattr("tools.web_search._search_provider", lambda *args: [])
    calls = [lambda: search_web("fixture"), lambda: ResearchAgent().collect_web_sources(context.brief),
        lambda: TavilySearchClient("fixture-key").search("fixture", None, None, 1),
        lambda: retrieve("fixture", index=None), lambda: retrieve_writer_evidence({}, []),
        lambda: load_knowledge_base_documents("nonexistent")]
    with frozen_evidence_scope():
        for action in calls:
            with pytest.raises(FrozenEvidenceAccessError): action()
    assert search_web("fixture") == []


def test_generation_scope_also_blocks_accidental_live_evidence(context):
    from tools.web_search import search_web
    client = FakeClient(context)
    client.before = lambda *args: search_web("unexpected fetch")
    generator = ContractGenerator(client)
    with pytest.raises(FrozenEvidenceAccessError): generator.generate(context, "research")
    assert len(client.calls) == 1


def test_legacy_graph_cannot_be_mistaken_for_formal(context):
    from workflow.multi_agent_graph import build_multi_agent_workflow_graph
    with pytest.raises(ValueError, match="Legacy graph"):
        build_multi_agent_workflow_graph().invoke({"user_brief":context.brief, "execution_mode":"formal_frozen"})


def test_legacy_string_claim_output_still_loads_without_promotion():
    payload = {"title":"Legacy history"}
    for key, title in zip(PROPOSAL_SECTION_FIELD_NAMES, PROPOSAL_SECTION_TITLES, strict=True):
        payload[key] = {"title":title, "content":"Legacy business proposal content remains available for historical inspection.",
                        "key_claims":["A legacy assumption"], "confidence":"medium"}
    old = ProposalDraft.model_validate(payload)
    assert old.problem.key_claims[0].claim_type == "general"
    assert old.problem.confidence == "low"
    with pytest.raises(ValueError): ContractProposal.model_validate(payload)


def test_financial_claims_link_to_frozen_values(context):
    payload = proposal_payload(context)
    c = payload["financial_assumptions"]["key_claims"][0]
    c.update(claim_id="finance.calculation", claim_domain="financial_calculation", financial_value_ids=["unknown"])
    with pytest.raises(ValueError, match="unknown financial"):
        context.accept("writer", payload)
    c["financial_value_ids"] = []
    with pytest.raises(ValueError, match="requires linked"):
        context.accept("writer", payload)
    c["financial_value_ids"] = ["base.monthly_revenue"]
    context.accept("writer", payload)


def test_global_pruning_and_changes_are_retained(context):
    original_payload = proposal_payload(context)
    result = context.accept("writer", original_payload, pruned=True)
    assert result.pruned
    assert result.payload().problem.confidence_reason == "pruned"
    assert original_payload["problem"]["confidence_reason"] == "no_evidence"
    changed = json.loads(result.changes_json)
    assert changed and all(c["reason"] == "pruned" for c in changed)
    assert all(c["basis"].endswith("not_human_gold") for c in changed)


def test_revision_cannot_be_repeated(context):
    original = context.accept("writer", proposal_payload(context))
    revised = context.accept("writer", proposal_payload(context, version=2), version=2, previous=original)
    with pytest.raises(ValueError, match="exactly one"):
        context.accept("writer", proposal_payload(context, version=3), version=3, previous=revised)


def test_revision_may_not_launder_ids(context):
    original = GroundedClaim.model_validate(claim(context))
    renamed = GroundedClaim.model_validate(claim(context, claim_id="new-id"))
    with pytest.raises(ValueError, match="upstream ID"):
        validate_lineage(original, renamed)
    renamed.parent_claim_id = original.claim_id
    validate_lineage(original, renamed, revision=True)


def test_batch_finance_failure_uses_its_only_repair(context):
    ctx = ContractContext.from_case(ROOT, "ai_education", condition="A")
    client = FakeClient(ctx)
    original = client.generate_structured_once
    corrupted = False
    def wrong_finance(prompt, schema, **kwargs):
        nonlocal corrupted
        candidate = original(prompt, schema, **kwargs)
        if "financial_assumptions" in schema.model_fields and not corrupted:
            corrupted = True
            candidate.financial_assumptions.financial_values[0].value += 100
        return candidate
    client.generate_structured_once = wrong_finance
    generator = ContractGenerator(client)
    result = generator.generate(ctx, "single")
    assert result
    assert len(client.calls) == 5
    assert not generator.tasks[2].first_output_passed
    assert generator.tasks[2].attempts[-1].passed
    assert generator.terminal_checks[-1]["passed"]


def test_cross_batch_collision_fails_terminal_without_extra_repair():
    ctx = ContractContext.from_case(ROOT, "ai_education", condition="A")
    client = FakeClient(ctx)
    original = client.generate_structured_once
    def inconsistent(prompt, schema, **kwargs):
        candidate = original(prompt, schema, **kwargs)
        if schema is CONTRACT_BATCH_MODELS[-1]:
            for key in PROPOSAL_SECTION_BATCHES[-1]:
                getattr(candidate, key).key_claims[0].source_quality = .1
        return candidate
    client.generate_structured_once = inconsistent
    generator = ContractGenerator(client)
    with pytest.raises(ValueError, match="inconsistent meaning"):
        generator.generate(ctx, "single")
    assert len(client.calls) == 4
    assert all(t.first_output_passed for t in generator.tasks)
    assert generator.terminal_checks[-1]["passed"] is False


def test_all_provider_schemas_can_be_prepared_locally():
    from workflow.gemini_schema import relaxed_response_schema
    from google.genai.types import Schema
    from workflow.schema_contract import schema_enum_contract
    for schema in (ContractResearchAnalysis, ContractStrategyAnalysis, ContractFinanceAssumptions, *CONTRACT_BATCH_MODELS):
        assert relaxed_response_schema(schema)
        Schema.model_validate(relaxed_response_schema(schema))
        assert "model_proposed" in schema_enum_contract(schema)
        assert "source_anchors" in json.dumps(schema.model_json_schema())


@pytest.mark.parametrize("feedback", [
    {"source_ids":["invented"]}, {"issues":[{"source_id":"invented"}]},
    {"issues":[{"chunk_id":"invented"}]}, {"issues":[{"affected_claim_ids":["invented"]}]},
])
def test_critic_feedback_cannot_invent_source_or_claim_ids(context, feedback):
    artifact = context.accept("research", component_payload(context, "research"))
    with pytest.raises(ValueError): context.validate_review_feedback(artifact, feedback)


def test_revision_prompt_carries_checked_feedback_and_original_packet(context):
    previous = context.accept("research", component_payload(context, "research"))
    client = FakeClient(context)
    def revision(prompt, schema, **kwargs):
        client.calls.append((prompt, schema, kwargs))
        return schema.model_validate(component_payload(context, "research", version=2))
    client.generate_structured_once = revision
    generator = ContractGenerator(client)
    result = generator.generate(context, "research", previous=previous, version=2,
        revision_feedback={"issues":[{"affected_claim_ids":["research.pricing"], "description":"Clarify the quoted evidence limitation."}]},
        unresolved_major=True)
    assert result.version == 2 and result.unresolved_major
    assert context.packet_sha256 in client.calls[0][0]
    assert "Clarify the quoted evidence limitation" in client.calls[0][0]
    assert generator.tasks[0].attempts[0].purpose == "revision"


def test_approved_synthetic_formal_mode_blocks_live_access(context):
    packet = context.packet.model_dump(mode="json", exclude_unset=True)
    packet.update(review_status="approved", approval_record="SYNTHETIC TEST ONLY, not a real case approval")
    packet["packet_sha256"] = canonical_hash({k:v for k,v in packet.items() if k != "packet_sha256"})
    formal = ContractContext(brief=context.brief, packet=packet, expected_packet_hash=packet["packet_sha256"],
        snapshot_root=ROOT, condition="C", execution_mode="formal_frozen")
    from tools.web_search import search_web
    client = FakeClient(formal)
    client.before = lambda *args: search_web("must not reach provider")
    with pytest.raises(FrozenEvidenceAccessError): ContractGenerator(client).generate(formal, "research")
