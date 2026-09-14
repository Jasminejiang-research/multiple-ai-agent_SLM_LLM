"""Actual v20 Writer may retain an original ID also copied by later roles."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from schemas.evidence import canonical_hash
from workflow.compact_protocol import (
    GEMINI_8192_LINEAGE_ID_CONFIG_VERSION, LINEAGE_IDENTITY_CONTINUITY_VERSION,
    evidence_catalog, expand_role_wire, mechanical_repair_json, normalize_exact_text_parent_lineage,
    preserve_upstream_dispositions, protocol_manifest, role_wire_schema,
)
from workflow.contract_context import ContractArtifact, ContractContext
from workflow.grounding import claims_in


ROOT = Path(__file__).resolve().parents[1]
CONFIG = GEMINI_8192_LINEAGE_ID_CONFIG_VERSION


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
def replay():
    run = ROOT / "docs/final_sprint/s5-llm-only-v20"
    path = run / "smokes/ai_education-B/events.jsonl"
    untouched = path.read_bytes()
    rows = [json.loads(line) for line in untouched.decode("utf-8").splitlines()]
    raw = {event["payload"]["task_role"]: event["payload"]["raw_output"] for event in rows
        if event["kind"] == "call" and event["payload"].get("raw_output")}
    context = ContractContext.from_case(run / "frozen_inputs", "ai_education",
        condition="B", execution_mode="formal_frozen")
    upstream = []
    for role in ("research", "strategy", "finance"):
        saved = next(event["payload"]["artifact"] for event in rows if event["kind"] == "artifact"
            and event["payload"]["artifact_ref"]["artifact_id"] == f"{role}.effective")
        actual = ContractArtifact(role=role, version=saved["artifact_version"], case_id=saved["case_id"],
            packet_sha256=saved["packet_sha256"], brief_sha256=saved["brief_sha256"],
            payload_json=json.dumps(saved["payload"]), changes_json=json.dumps(saved["confidence_changes"]),
            pruned=saved["pruned"], unresolved_major=saved["unresolved_major"], contract_version=saved["contract_version"])
        context.verify_artifact(actual)
        assert actual.sha256 == canonical_hash(saved)
        candidate = expand_role_wire(context, role, repair(raw[role], role, context), version=1, config_version=CONFIG)
        normalize_exact_text_parent_lineage(candidate, upstream)
        preserve_upstream_dispositions(candidate, upstream, lineage_identity_continuity=True)
        accepted = context.accept(role, candidate, upstream=upstream, transitive_lineage=True,
            lineage_identity_continuity=True)
        assert canonical_hash(accepted.payload().model_dump(mode="json")) == canonical_hash(saved["payload"])
        upstream.append(actual)
    writer = expand_role_wire(context, "writer", repair(raw["writer"], "writer", context),
        version=1, config_version=CONFIG)
    normalize_exact_text_parent_lineage(writer, upstream)
    yield context, tuple(upstream), writer
    assert path.read_bytes() == untouched


def test_actual_full_chain_accepts_preserved_ancestor_ids_and_exports_thirteen_sections(replay, tmp_path):
    context, upstream, writer = replay
    before = {c.claim_id: (c.parent_claim_id, c.claim_text, c.source_ids.copy(),
        [a.model_dump(mode="json") for a in c.source_anchors]) for c in claims_in(writer)}
    with pytest.raises(ValueError, match="unchanged claim text"):
        context.validate(writer, version=1, upstream=upstream, transitive_lineage=True)
    preserve_upstream_dispositions(writer, upstream, lineage_identity_continuity=True)
    context.validate(writer, version=1, upstream=upstream, transitive_lineage=True,
        lineage_identity_continuity=True)
    accepted = context.accept("writer", writer, upstream=upstream, transitive_lineage=True,
        lineage_identity_continuity=True)
    context.verify_artifact(accepted)
    assert {c.claim_id: (c.parent_claim_id, c.claim_text, c.source_ids.copy(),
        [a.model_dump(mode="json") for a in c.source_anchors]) for c in claims_in(writer)} == before
    assert before["MOD01"][0] is None and before["GTM01"][0] is None
    assert accepted.payload().financial_assumptions.financial_values == context.finance.expected_values()
    destination = context.export(accepted, tmp_path / "actual-v20-writer-replay")
    assert (destination / "proposal.md").read_text(encoding="utf-8").count("\n\n## ") == 13


def mutate(upstream, role, claim_id, change):
    result = []
    for artifact in upstream:
        if artifact.role == role:
            payload = artifact.payload()
            for claim in claims_in(payload):
                if claim.claim_id == claim_id:
                    change(claim)
            artifact = replace(artifact, payload_json=payload.model_dump_json())
        result.append(artifact)
    return tuple(result)


def test_unconnected_same_text_descendant_still_rejects(replay):
    context, upstream, writer = replay
    upstream = mutate(upstream, "finance", "GAP02", lambda c: setattr(c, "parent_claim_id", None))
    with pytest.raises(ValueError, match="unchanged claim text"):
        context.validate(writer, version=1, upstream=upstream, transitive_lineage=True,
            lineage_identity_continuity=True)


def test_recorded_identity_cycle_still_rejects(replay):
    context, upstream, writer = replay
    upstream = mutate(upstream, "strategy", "MOD01", lambda c: setattr(c, "parent_claim_id", "GAP02"))
    with pytest.raises(ValueError, match="cycle"):
        context.validate(writer, version=1, upstream=upstream, transitive_lineage=True,
            lineage_identity_continuity=True)


def test_descendant_evidence_cannot_be_lost_or_fabricated_by_state_adapter(replay):
    context, upstream, writer = replay
    source = next(c for c in claims_in(upstream[0].payload()) if c.source_anchors)
    def add_existing_source(claim):
        claim.source_ids = source.source_ids.copy()
        claim.source_anchors = [a.model_copy(deep=True) for a in source.source_anchors]
    upstream = mutate(upstream, "finance", "GAP02", add_existing_source)
    preserve_upstream_dispositions(writer, upstream, lineage_identity_continuity=True)
    assert next(c for c in claims_in(writer) if c.claim_id == "MOD01").source_ids == []
    with pytest.raises(ValueError, match="lost upstream sources"):
        context.validate(writer, version=1, upstream=upstream, transitive_lineage=True,
            lineage_identity_continuity=True)


@pytest.mark.parametrize("field,value,error", [("major_issue", True, "major issue"),
    ("conflict", True, "conflict"), ("critic_status", "unverified_after_revision", "semantic status")])
def test_descendant_unresolved_state_is_required_and_conservatively_propagated(replay, field, value, error):
    context, upstream, writer = replay
    upstream = mutate(upstream, "finance", "GAP02", lambda c: setattr(c, field, value))
    with pytest.raises(ValueError, match=error):
        context.validate(writer, version=1, upstream=upstream, transitive_lineage=True,
            lineage_identity_continuity=True)
    changes = preserve_upstream_dispositions(writer, upstream, lineage_identity_continuity=True)
    assert getattr(next(c for c in claims_in(writer) if c.claim_id == "MOD01"), field) == value
    assert any(change.get("lineage_identity_continuity") == LINEAGE_IDENTITY_CONTINUITY_VERSION for change in changes)
    context.validate(writer, version=1, upstream=upstream, transitive_lineage=True,
        lineage_identity_continuity=True)


def test_v24_manifest_inherits_short_repair_admission_and_marks_identity_rule():
    manifest = protocol_manifest(CONFIG)
    assert manifest["lineage_identity_continuity"] == LINEAGE_IDENTITY_CONTINUITY_VERSION
    assert max(item["chars"] for item in manifest["repair_instructions"].values()) <= 500


@pytest.mark.parametrize("use_current,expected_calls", [(True, 5), (False, 4)])
def test_actual_v20_raws_cross_current_bounded_runtime_and_b_graph(tmp_path, use_current, expected_calls):
    from evaluation.s5_llm_only import run_config
    from workflow.compact_protocol import GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION
    from workflow.review_graph import build_review_workflow
    from workflow.review_runtime import PhysicalResponse

    run = ROOT / "docs/final_sprint/s5-llm-only-v20"
    source = run / "smokes/ai_education-B/events.jsonl"
    original_bytes = source.read_bytes()
    rows = [json.loads(line) for line in original_bytes.decode("utf-8").splitlines()]
    raw = {event["payload"]["task_role"]: event["payload"]["raw_output"] for event in rows
        if event["kind"] == "call" and event["payload"].get("raw_output")}
    context = ContractContext.from_case(run / "frozen_inputs", "ai_education",
        condition="B", execution_mode="formal_frozen")

    class PreservedRawFixtureProvider:
        provider = "gemini"
        model_exact_id = "gemini-2.5-flash"

        def __init__(self):
            self.roles = []

        def invoke(self, request):
            role = json.loads(request.prompt)["role"]
            self.roles.append(role)
            if role == "final_critic":
                # Explicit synthetic control-flow fixture, never a measured model verdict.
                output = json.dumps({"scores": [3] * 6, "status": "PASS", "issues": []})
            else:
                output = raw[role]
            return PhysicalResponse(output, {"synthetic": True,
                "fixture": "preserved_v20_raw_plus_synthetic_final_critic", "prompt": 10, "output": 5, "total": 15},
                10, 5, 15)

    config = run_config("B", "smoke")
    if use_current:
        assert protocol_manifest(config.config_version)["lineage_identity_continuity"] == LINEAGE_IDENTITY_CONTINUITY_VERSION
    else:
        config = config.model_copy(update={"config_version": GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION})
    provider = PreservedRawFixtureProvider()
    workflow = build_review_workflow(context, config=config, provider=provider,
        output_dir=tmp_path / f"bounded-replay-{expected_calls}")
    result = workflow.run()
    assert len(provider.roles) == expected_calls
    assert workflow.client.snapshot()["request_count"] == expected_calls
    calls = [event["payload"] for event in workflow.journal.events if event["kind"] == "call"
        and event["payload"]["status"] != "dispatching"]
    assert all(call["usage_raw"]["synthetic"] for call in calls)
    assert source.read_bytes() == original_bytes
    if use_current:
        assert provider.roles == ["research", "strategy", "finance", "writer", "final_critic"]
        assert result["status"] == "completed" and result["terminal_contract_passed"], result["error"]
        text = (workflow.journal.directory / "internal_export/proposal.md").read_text(encoding="utf-8")
        assert text.count("\n\n## ") == 13
        assert "final_critic" not in raw
    else:
        assert result["status"] == "failed" and result["error"]["node"] == "writer.generate"
        writer_task = next(task for task in workflow.generator.tasks if task.role == "writer")
        assert writer_task.attempts[-1].error == "unchanged claim text requires its upstream ID or parent_claim_id"
