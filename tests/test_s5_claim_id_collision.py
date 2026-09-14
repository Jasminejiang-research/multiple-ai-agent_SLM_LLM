"""Preserved v21 raw Writer identity collision; all provider responses are fixtures."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from schemas.evidence import canonical_hash
from workflow.compact_protocol import (
    CLAIM_ID_COLLISION_ADAPTER_VERSION, GEMINI_8192_ID_COLLISION_CONFIG_VERSION,
    GEMINI_8192_LINEAGE_ID_CONFIG_VERSION, compact_role_output, evidence_catalog,
    expand_role_wire, mechanical_repair_json, normalize_claim_id_collisions,
    normalize_exact_text_parent_lineage, preserve_upstream_dispositions,
    protocol_manifest, role_wire_schema,
)
from workflow.contract_context import ContractArtifact, ContractContext
from workflow.grounding import ClaimIdentityCollisionError, claims_in, validate_lineage


ROOT = Path(__file__).resolve().parents[1]
CONFIG = GEMINI_8192_ID_COLLISION_CONFIG_VERSION
RUN = ROOT / "docs/final_sprint/s5-llm-only-v21"


def repair(raw, role, context):
    return mechanical_repair_json(raw, role_wire_schema(role, CONFIG),
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
        source_disposition_claim_repair=True, citation_list_format_claim_repair=True,
        inline_citation_mirror_claim_repair=True, financial_marker_claim_repair=True,
        source_quality_scale_5_claim_repair=True, existing_claim_body_assembly_claim_repair=True,
        invalid_source_recency_claim_repair=True, finance_note_partition_repair=True,
        finance_assumption_notice_repair=True, repair_evidence_catalog=evidence_catalog(context.packet),
        repair_financial_ids=set(context.finance.value_ids))[0]


@pytest.fixture
def actual():
    source = RUN / "smokes/ai_education-B/events.jsonl"
    untouched = source.read_bytes()
    rows = [json.loads(line) for line in untouched.decode("utf-8").splitlines()]
    raw = {event["payload"]["task_role"]: event["payload"]["raw_output"] for event in rows
        if event["kind"] == "call" and event["payload"].get("raw_output")}
    context = ContractContext.from_case(RUN / "frozen_inputs", "ai_education",
        condition="B", execution_mode="formal_frozen")
    upstream = []
    for role in ("research", "strategy", "finance"):
        saved = next(event["payload"]["artifact"] for event in rows if event["kind"] == "artifact"
            and event["payload"]["artifact_ref"]["artifact_id"] == f"{role}.effective")
        artifact = ContractArtifact(role=role, version=saved["artifact_version"], case_id=saved["case_id"],
            packet_sha256=saved["packet_sha256"], brief_sha256=saved["brief_sha256"],
            payload_json=json.dumps(saved["payload"]), changes_json=json.dumps(saved["confidence_changes"]),
            pruned=saved["pruned"], unresolved_major=saved["unresolved_major"], contract_version=saved["contract_version"])
        context.verify_artifact(artifact)
        assert artifact.sha256 == canonical_hash(saved)
        wire, _ = normalize_claim_id_collisions(context, repair(raw[role], role, context), upstream,
            config_version=CONFIG)
        candidate = expand_role_wire(context, role, wire, version=1, config_version=CONFIG)
        normalize_exact_text_parent_lineage(candidate, upstream)
        preserve_upstream_dispositions(candidate, upstream, lineage_identity_continuity=True)
        accepted = context.accept(role, candidate, upstream=upstream, transitive_lineage=True,
            lineage_identity_continuity=True)
        assert canonical_hash(accepted.payload().model_dump(mode="json")) == canonical_hash(saved["payload"])
        upstream.append(artifact)
    yield context, tuple(upstream), repair(raw["writer"], "writer", context)
    assert source.read_bytes() == untouched


def normalize(context, wire, upstream):
    return normalize_claim_id_collisions(context, wire, upstream, config_version=CONFIG)


def test_actual_latest_raw_complete_chain_only_changes_duplicate_id_and_declared_parent(actual, tmp_path):
    context, upstream, wire = actual
    before = wire.model_dump(mode="json")
    candidate = expand_role_wire(context, "writer", wire, version=1, config_version=CONFIG)
    with pytest.raises(ClaimIdentityCollisionError, match="CUS01"):
        context.validate(candidate, version=1, upstream=upstream, transitive_lineage=True,
            lineage_identity_continuity=True)
    result, audit = normalize(context, wire, upstream)
    expected = json.loads(json.dumps(before))
    expected["sections"][1]["claims"][0].update(i="CUS01__02", pi="CUS01")
    assert result.model_dump(mode="json") == expected
    assert wire.model_dump(mode="json") == before
    assert len(audit) == 1 and audit[0]["version"] == CLAIM_ID_COLLISION_ADAPTER_VERSION
    assert audit[0]["occurrences"][0]["path"] == "sections[1].claims[0]"
    assert audit[0]["evidence_ids_added"] == [] and audit[0]["claims_deleted"] == 0
    candidate = expand_role_wire(context, "writer", result, version=1, config_version=CONFIG)
    normalize_exact_text_parent_lineage(candidate, upstream)
    preserve_upstream_dispositions(candidate, upstream, lineage_identity_continuity=True)
    accepted = context.accept("writer", candidate, upstream=upstream, transitive_lineage=True,
        lineage_identity_continuity=True)
    context.verify_artifact(accepted)
    assert len(claims_in(accepted.payload())) == 13
    assert accepted.payload().financial_assumptions.financial_values == context.finance.expected_values()
    destination = context.export(accepted, tmp_path / "actual-v21-writer")
    assert (destination / "proposal.md").read_text(encoding="utf-8").count("\n\n## ") == 13


def test_old_config_unchanged_identical_repeat_shares_id_and_different_confidence_is_not_collision(actual):
    context, upstream, wire = actual
    old, audit = normalize_claim_id_collisions(context, wire, upstream,
        config_version=GEMINI_8192_LINEAGE_ID_CONFIG_VERSION)
    assert old == wire and audit == []
    wire.sections[1].claims[0] = wire.sections[0].claims[0].model_copy(deep=True)
    wire.sections[1].claims[0].c = "low"
    wire.sections[1].claims[0].cr = "no_evidence"
    result, audit = normalize(context, wire, upstream)
    assert result == wire and audit == []


def test_repeated_second_identity_keeps_one_new_id_and_avoids_all_reserved_ids(actual):
    context, upstream, wire = actual
    wire.sections[2].claims[0] = wire.sections[1].claims[0].model_copy(deep=True)
    wire.sections[3].claims[0].pi = "CUS01__02"
    result, audit = normalize(context, wire, upstream)
    assert result.sections[1].claims[0].i == result.sections[2].claims[0].i == "CUS01__03"
    assert len(audit[0]["occurrences"]) == 2


def test_unknown_declared_id_and_unrelated_explicit_parent_are_not_guessed(actual):
    context, upstream, wire = actual
    local = wire.model_copy(deep=True)
    local.sections[0].claims[0].i = local.sections[1].claims[0].i = "LOCAL01"
    with pytest.raises(ValueError, match="no unambiguous"):
        normalize(context, local, upstream)
    wire.sections[1].claims[0].pi = "MKT01"
    with pytest.raises(ValueError, match="lose declared upstream"):
        normalize(context, wire, upstream)


def test_explicit_original_parent_is_retained(actual):
    context, upstream, wire = actual
    wire.sections[1].claims[0].pi = "CUS01"
    result, audit = normalize(context, wire, upstream)
    assert result.sections[1].claims[0].pi == "CUS01"
    assert audit[0]["parent_basis"] == "existing_explicit_parent"


def test_contradictory_upstream_identity_and_cycles_still_reject(actual):
    context, upstream, wire = actual
    for mutate, message in [(lambda claim: setattr(claim, "claim_domain", "different domain"), "inconsistent"),
            (lambda claim: setattr(claim, "parent_claim_id", "CUS01"), "cycle|inconsistent")]:
        changed = []
        for artifact in upstream:
            payload = artifact.payload()
            if artifact.role == "strategy":
                for claim in claims_in(payload):
                    if claim.claim_id == "CUS01":
                        mutate(claim)
                artifact = replace(artifact, payload_json=payload.model_dump_json())
            changed.append(artifact)
        with pytest.raises(ValueError, match=message):
            normalize(context, wire, changed)


def test_split_cannot_drop_declared_upstream_sources(actual):
    context, upstream, wire = actual
    factual = compact_role_output(context, "research", upstream[0].payload(), config_version=CONFIG).market[0].claims[0]
    wire.sections[0].claims = [factual.model_copy(deep=True)]
    wire.sections[0].text = factual.t
    unsupported = factual.model_copy(deep=True)
    unsupported.t = "Unverified model wording: " + factual.t.split(" [E")[0] + "."
    unsupported.e, unsupported.s, unsupported.ss = [], "unsupported", "none"
    unsupported.c, unsupported.cr = "low", "no_evidence"
    wire.sections[1].claims, wire.sections[1].text = [unsupported], unsupported.t
    result, audit = normalize(context, wire, upstream[:1])
    assert result.sections[1].claims[0].e == [] and audit[0]["evidence_ids_added"] == []
    candidate = expand_role_wire(context, "writer", result, version=1, config_version=CONFIG)
    with pytest.raises(ValueError, match="lost upstream sources"):
        validate_lineage(upstream[0].payload(), candidate, transitive_lineage=True,
            upstream_claims=claims_in(upstream[0].payload()), lineage_identity_continuity=True)


def test_split_retains_critic_unresolved_obligations(actual):
    context, upstream, wire = actual
    changed = []
    for artifact in upstream:
        payload = artifact.payload()
        for claim in claims_in(payload):
            if claim.claim_id == "CUS01":
                claim.major_issue, claim.critic_status = True, "unresolved"
        changed.append(replace(artifact, payload_json=payload.model_dump_json()))
    result, _ = normalize(context, wire, changed)
    candidate = expand_role_wire(context, "writer", result, version=1, config_version=CONFIG)
    with pytest.raises(ValueError, match="major issue|semantic status"):
        context.validate(candidate, version=1, upstream=changed, transitive_lineage=True,
            lineage_identity_continuity=True)
    preserve_upstream_dispositions(candidate, changed, lineage_identity_continuity=True)
    split = next(c for c in claims_in(candidate) if c.claim_id == "CUS01__02")
    assert split.major_issue and split.critic_status == "unresolved"
    context.validate(candidate, version=1, upstream=changed, transitive_lineage=True,
        lineage_identity_continuity=True)


def test_v25_manifest_has_independent_adapter_and_inherits_prior_contract():
    current = protocol_manifest(CONFIG)
    prior = protocol_manifest(GEMINI_8192_LINEAGE_ID_CONFIG_VERSION)
    assert current["claim_id_collision_adapter"] == CLAIM_ID_COLLISION_ADAPTER_VERSION
    assert prior["claim_id_collision_adapter"] is None
    assert {k: v for k, v in current.items() if k not in ("config_version", "claim_id_collision_adapter")} == {
        k: v for k, v in prior.items() if k not in ("config_version", "claim_id_collision_adapter")}


@pytest.mark.parametrize("current,expected_calls", [(True, 6), (False, 5)])
def test_all_actual_v21_raws_through_bounded_runtime_and_b_workflow(tmp_path, current, expected_calls):
    from evaluation.s5_llm_only import run_config
    from workflow.review_graph import build_review_workflow
    from workflow.review_runtime import PhysicalResponse

    source = RUN / "smokes/ai_education-B/events.jsonl"
    untouched = source.read_bytes()
    rows = [json.loads(line) for line in untouched.decode("utf-8").splitlines()]
    outputs = {}
    for event in rows:
        if event["kind"] == "call" and event["payload"].get("raw_output"):
            outputs.setdefault(event["payload"]["task_role"], []).append(event["payload"]["raw_output"])
    context = ContractContext.from_case(RUN / "frozen_inputs", "ai_education",
        condition="B", execution_mode="formal_frozen")

    class PreservedRawFixtureProvider:
        provider = "gemini"
        model_exact_id = "gemini-2.5-flash"
        def __init__(self):
            self.roles = []
        def invoke(self, request):
            role = json.loads(request.prompt)["role"]
            self.roles.append(role)
            # This Critic is an explicit synthetic control-flow fixture, not a measured verdict.
            raw = json.dumps({"scores": [3] * 6, "status": "PASS", "issues": []}) if role == "final_critic" else outputs[role].pop(0)
            return PhysicalResponse(raw, {"synthetic": True,
                "fixture": "preserved_v21_raw_plus_synthetic_final_critic", "prompt": 10, "output": 5, "total": 15},
                10, 5, 15)

    config = run_config("B", "smoke")
    assert protocol_manifest(config.config_version)["claim_id_collision_adapter"] == CLAIM_ID_COLLISION_ADAPTER_VERSION
    if not current:
        config = config.model_copy(update={"config_version": GEMINI_8192_LINEAGE_ID_CONFIG_VERSION})
    provider = PreservedRawFixtureProvider()
    workflow = build_review_workflow(context, config=config, provider=provider,
        output_dir=tmp_path / f"bounded-replay-{expected_calls}")
    result = workflow.run()
    assert len(provider.roles) == workflow.client.snapshot()["request_count"] == expected_calls
    assert source.read_bytes() == untouched
    assert provider.roles[:2] == ["research", "research"]
    research = next(task for task in workflow.generator.tasks if task.role == "research")
    assert len(research.attempts) == 2 and not research.attempts[0].passed
    if current:
        assert result["status"] == "completed" and result["terminal_contract_passed"], result["error"]
        text = (workflow.journal.directory / "internal_export/proposal.md").read_text(encoding="utf-8")
        assert text.count("\n\n## ") == 13
        writer = next(task for task in workflow.generator.tasks if task.role == "writer")
        assert any("CUS01__02" in json.dumps(diff) for diff in writer.deterministic_diffs)
    else:
        assert result["status"] == "failed" and result["error"]["node"] == "writer.generate"
        writer = next(task for task in workflow.generator.tasks if task.role == "writer")
        assert writer.attempts[-1].error_type == "ClaimIdentityCollisionError"
