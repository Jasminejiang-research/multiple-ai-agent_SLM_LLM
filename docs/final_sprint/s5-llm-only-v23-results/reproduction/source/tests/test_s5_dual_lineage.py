"""Actual v22 Writer reused VAL01 for GAP01 text: retain both obligations."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from schemas.evidence import canonical_hash
from workflow.compact_protocol import (
    DUAL_DECLARED_LINEAGE_VERSION, GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION,
    GEMINI_8192_ID_COLLISION_CONFIG_VERSION, expand_role_wire,
    normalize_claim_id_collisions, normalize_exact_text_parent_lineage,
    preserve_upstream_dispositions, protocol_manifest,
)
from workflow.contract_context import ContractArtifact, ContractContext
from workflow.grounding import claims_in, lineage_ancestor_ids
from test_s5_claim_id_collision import repair


RUN = Path(__file__).resolve().parents[1] / "docs/final_sprint/s5-llm-only-v22"
CONFIG = GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION
FLAGS = dict(transitive_lineage=True, lineage_identity_continuity=True, dual_declared_lineage=True)


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
        normalize_exact_text_parent_lineage(candidate, upstream, dual_declared_lineage=True)
        preserve_upstream_dispositions(candidate, upstream, lineage_identity_continuity=True, dual_declared_lineage=True)
        accepted = context.accept(role, candidate, upstream=upstream, **FLAGS)
        assert canonical_hash(accepted.payload().model_dump(mode="json")) == canonical_hash(saved["payload"])
        upstream.append(artifact)
    wire, _ = normalize_claim_id_collisions(context, repair(raw["writer"], "writer", context), upstream,
        config_version=CONFIG)
    candidate = expand_role_wire(context, "writer", wire, version=1, config_version=CONFIG)
    yield context, tuple(upstream), candidate
    assert source.read_bytes() == untouched


def test_actual_complete_raw_chain_preserves_both_ids_and_only_adds_exact_parent(actual, tmp_path):
    context, upstream, writer = actual
    before = writer.model_dump(mode="json")
    assert normalize_exact_text_parent_lineage(writer, upstream) == []
    with pytest.raises(ValueError, match="unchanged claim text"):
        context.validate(writer, version=1, upstream=upstream, transitive_lineage=True,
            lineage_identity_continuity=True)
    changes = normalize_exact_text_parent_lineage(writer, upstream, dual_declared_lineage=True)
    expected = json.loads(json.dumps(before))
    expected["problem"]["key_claims"][0]["parent_claim_id"] = "GAP01"
    assert writer.model_dump(mode="json") == expected
    assert len(changes) == 1 and changes[0]["dual_declared_lineage"] == DUAL_DECLARED_LINEAGE_VERSION
    assert changes[0]["semantic_identity_inferred"] is False
    assert preserve_upstream_dispositions(writer, upstream, lineage_identity_continuity=True,
        dual_declared_lineage=True) == []
    accepted = context.accept("writer", writer, upstream=upstream, **FLAGS)
    context.verify_artifact(accepted)
    assert len(claims_in(accepted.payload())) == 13
    assert accepted.payload().financial_assumptions.financial_values == context.finance.expected_values()
    path = context.export(accepted, tmp_path / "actual-v22")
    assert (path / "proposal.md").read_text(encoding="utf-8").count("\n\n## ") == 13


def mutate(upstream, claim_id, operation):
    result = []
    for artifact in upstream:
        payload = artifact.payload()
        for claim in claims_in(payload):
            if claim.claim_id == claim_id:
                operation(claim)
        result.append(replace(artifact, payload_json=payload.model_dump_json()))
    return tuple(result)


@pytest.mark.parametrize("claim_id", ["VAL01", "GAP01"])
def test_both_declared_branches_unresolved_states_required_and_preserved(actual, claim_id):
    context, upstream, writer = actual
    upstream = mutate(upstream, claim_id, lambda c: (setattr(c, "major_issue", True),
        setattr(c, "critic_status", "unverified_after_revision")))
    normalize_exact_text_parent_lineage(writer, upstream, dual_declared_lineage=True)
    with pytest.raises(ValueError, match="major issue|semantic status"):
        context.validate(writer, version=1, upstream=upstream, **FLAGS)
    audit = preserve_upstream_dispositions(writer, upstream, lineage_identity_continuity=True,
        dual_declared_lineage=True)
    assert writer.problem.key_claims[0].major_issue
    assert writer.problem.key_claims[0].critic_status == "unverified_after_revision"
    assert any(change.get("dual_declared_lineage") == DUAL_DECLARED_LINEAGE_VERSION for change in audit)
    context.validate(writer, version=1, upstream=upstream, **FLAGS)


@pytest.mark.parametrize("claim_id", ["VAL01", "GAP01"])
def test_neither_declared_branches_sources_can_be_laundered(actual, claim_id):
    context, upstream, writer = actual
    source = next(c for c in claims_in(upstream[0].payload()) if c.source_anchors)
    def add_source(claim):
        claim.source_ids = source.source_ids.copy()
        claim.source_anchors = [anchor.model_copy(deep=True) for anchor in source.source_anchors]
    upstream = mutate(upstream, claim_id, add_source)
    normalize_exact_text_parent_lineage(writer, upstream, dual_declared_lineage=True)
    preserve_upstream_dispositions(writer, upstream, lineage_identity_continuity=True, dual_declared_lineage=True)
    assert writer.problem.key_claims[0].source_ids == []
    with pytest.raises(ValueError, match="lost upstream sources"):
        context.validate(writer, version=1, upstream=upstream, **FLAGS)


def test_disconnected_multiple_exact_text_candidates_not_selected(actual):
    context, upstream, writer = actual
    text = writer.problem.key_claims[0].claim_text
    upstream = mutate(upstream, "CUS01", lambda c: (setattr(c, "claim_text", text),
        setattr(c, "content_anchor", text)))
    # The normalizer itself must refuse ambiguous text matches; no parent is invented.
    assert normalize_exact_text_parent_lineage(writer, upstream, dual_declared_lineage=True) == []
    assert writer.problem.key_claims[0].parent_claim_id is None


def test_new_parent_and_explicit_candidate_cycle_rejected(actual):
    context, upstream, writer = actual
    upstream = mutate(upstream, "GAP01", lambda c: setattr(c, "parent_claim_id", "VAL01"))
    with pytest.raises(ValueError, match="cycle"):
        normalize_exact_text_parent_lineage(writer, upstream, dual_declared_lineage=True)
    writer.problem.key_claims[0].parent_claim_id = "GAP01"
    with pytest.raises(ValueError, match="cycle"):
        context.validate(writer, version=1, upstream=upstream, **FLAGS)


def test_writer_previous_revision_retains_both_lineage_obligations(actual):
    from schemas.review import METRICS
    from workflow.compact_protocol import expand_critic_wire, apply_patch_wire
    context, upstream, writer = actual
    normalize_exact_text_parent_lineage(writer, upstream, dual_declared_lineage=True)
    accepted = context.accept("writer", writer, upstream=upstream, **FLAGS)
    # Explicit synthetic Critic and patch; no assertion about a real model verdict.
    report = expand_critic_wire(context, accepted, "final", "writer.initial", {
        "scores": [2] * len(METRICS["final"]), "status": "FAIL", "issues": [{
            "i": "fixture001", "sev": "high", "criterion": METRICS["final"][0],
            "claims": ["VAL01"], "fields": ["sections.1.text"], "e": [],
            "fix": "clarify_scope", "note": "The unverified demand statement remains unresolved."}]},
        critic_patch_adapter=True)
    revised, diff = apply_patch_wire(context, accepted, report, {"claims": [{
        "issue": "fixture001", "i": "VAL01", "c": "low", "cr": "critic_unresolved"}]},
        critic_patch_adapter=True)
    accepted_v2 = context.accept("writer", revised, version=2, upstream=upstream,
        previous=accepted, unresolved_major=True, **FLAGS)
    context.verify_artifact(accepted_v2)
    assert accepted_v2.payload().problem.key_claims[0].parent_claim_id == "GAP01"
    assert accepted_v2.payload().problem.key_claims[0].critic_status == "unverified_after_revision"
    assert accepted_v2.unresolved_major and diff


def test_monotone_parent_completion_is_versioned_and_rejects_conflicts_or_cycles(actual):
    _, upstream, writer = actual
    root = next(c for c in claims_in(upstream[1].payload()) if c.claim_id == "VAL01")
    gap = next(c for c in claims_in(upstream[1].payload()) if c.claim_id == "GAP01")
    completed = root.model_copy(update={"parent_claim_id": "GAP01"})
    graph = [root, completed, gap]
    with pytest.raises(ValueError, match="inconsistent"):
        lineage_ancestor_ids("VAL01", graph)
    for ordered in (graph, list(reversed(graph))):
        assert lineage_ancestor_ids("VAL01", ordered, dual_declared_lineage=True) == ["VAL01", "GAP01"]
    with pytest.raises(ValueError, match="inconsistent"):
        lineage_ancestor_ids("VAL01", [*graph, root.model_copy(update={"parent_claim_id": "OTHER01"})],
            dual_declared_lineage=True)
    with pytest.raises(ValueError, match="inconsistent"):
        lineage_ancestor_ids("VAL01", [root, root.model_copy(update={"parent_claim_id": "UNKNOWN01"})],
            dual_declared_lineage=True)
    with pytest.raises(ValueError, match="cycle"):
        lineage_ancestor_ids("VAL01", [root, completed, gap.model_copy(update={"parent_claim_id": "VAL01"})],
            dual_declared_lineage=True)


def test_manifest_inherits_all_prior_contracts_and_versions_dual_obligations():
    current, prior = protocol_manifest(CONFIG), protocol_manifest(GEMINI_8192_ID_COLLISION_CONFIG_VERSION)
    assert current["dual_declared_lineage"] == DUAL_DECLARED_LINEAGE_VERSION
    assert prior["dual_declared_lineage"] is None
    assert {k: v for k, v in current.items() if k not in ("config_version", "dual_declared_lineage")} == {
        k: v for k, v in prior.items() if k not in ("config_version", "dual_declared_lineage")}


@pytest.mark.parametrize("current,expected_calls", [(True, 5), (False, 4)])
def test_actual_v22_raws_bounded_runtime_full_b_graph(tmp_path, current, expected_calls):
    from evaluation.s5_llm_only import run_config
    from workflow.review_graph import build_review_workflow
    from workflow.review_runtime import PhysicalResponse

    source = RUN / "smokes/ai_education-B/events.jsonl"
    untouched = source.read_bytes()
    rows = [json.loads(line) for line in untouched.decode("utf-8").splitlines()]
    raw = {event["payload"]["task_role"]: event["payload"]["raw_output"] for event in rows
        if event["kind"] == "call" and event["payload"].get("raw_output")}
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
            # Explicit synthetic fixture, never represented as a measured Critic verdict.
            output = json.dumps({"scores": [3] * 6, "status": "PASS", "issues": []}) if role == "final_critic" else raw[role]
            return PhysicalResponse(output, {"synthetic": True,
                "fixture": "preserved_v22_raw_plus_synthetic_final_critic", "prompt": 10, "output": 5, "total": 15},
                10, 5, 15)
    config = run_config("B", "smoke")
    assert config.config_version == CONFIG
    if not current:
        config = config.model_copy(update={"config_version": GEMINI_8192_ID_COLLISION_CONFIG_VERSION})
    provider = PreservedRawFixtureProvider()
    workflow = build_review_workflow(context, config=config, provider=provider,
        output_dir=tmp_path / f"bounded-v22-replay-{expected_calls}")
    result = workflow.run()
    assert len(provider.roles) == workflow.client.snapshot()["request_count"] == expected_calls
    assert source.read_bytes() == untouched
    if current:
        assert result["status"] == "completed" and result["terminal_contract_passed"], result["error"]
        assert (workflow.journal.directory / "internal_export/proposal.md").read_text(encoding="utf-8").count("\n\n## ") == 13
        writer = next(task for task in workflow.generator.tasks if task.role == "writer")
        assert any(DUAL_DECLARED_LINEAGE_VERSION in json.dumps(diff) for diff in writer.deterministic_diffs)
    else:
        assert result["status"] == "failed" and result["error"]["node"] == "writer.generate"
        writer = next(task for task in workflow.generator.tasks if task.role == "writer")
        assert writer.attempts[-1].error == "unchanged claim text requires its upstream ID or parent_claim_id"
