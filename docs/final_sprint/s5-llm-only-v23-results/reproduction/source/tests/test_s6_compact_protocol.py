"""S6 compact protocol acceptance tests; all provider activity is synthetic."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from evaluation.s2_fixtures import SyntheticProvider, synthetic_artifact, synthetic_report
from schemas.compact_wire import CriticWire, PatchWire, ROLE_WIRES, ResearchWire, WIRE_VERSION
from schemas.evidence import canonical_hash
from schemas.review import ComponentCritiqueReport, METRICS
from workflow.compact_protocol import (
    CONFIG_VERSION, INSTRUCTION_LIMIT, ROLE_INPUT_TOKENS, apply_patch_wire,
    compact_role_output, expand_role_wire, instruction_for, mechanical_repair_json,
    protocol_manifest,
)
from workflow.contract_context import ContractContext, ROLE_SCHEMAS
from workflow.contract_generation import ContractGenerator
from workflow.review_config import ReviewRunConfig
from workflow.review_events import replay_events
from workflow.review_graph import build_review_workflow


ROOT = Path(__file__).resolve().parents[1] / "docs/final_sprint/s0-v1"


def compact_run(tmp_path, *, case_id="ai_education", condition="C", fail_roles=(), severity="high"):
    context = ContractContext.from_case(ROOT, case_id, condition=condition)
    provider = SyntheticProvider(context, fail_roles=fail_roles, severity=severity)
    config = ReviewRunConfig(condition=condition, run_kind="debug", provider="mock",
        model_exact_id=provider.model_exact_id, model_config_version="synthetic-s6-v1",
        max_requests=32, max_total_tokens=1_000_000, max_output_tokens=1800,
        max_prompt_chars=26_000, request_seconds=10, run_seconds=3600,
        protocol_version=WIRE_VERSION, config_version=CONFIG_VERSION)
    workflow = build_review_workflow(context, config=config, provider=provider,
        output_dir=tmp_path / f"{case_id}-{condition}")
    return context, provider, workflow, workflow.run()


@pytest.mark.parametrize("case_id,expected", [("ai_education", 21), ("intelligent_ring", 27)])
def test_case_specific_finance_rows_are_frozen(case_id, expected):
    context = ContractContext.from_case(ROOT, case_id, condition="C")
    assert len(context.finance.expected_values()) == expected
    assert len({row.value_id for row in context.finance.expected_values()}) == expected


def test_instruction_and_wire_schema_snapshots():
    manifest = protocol_manifest()
    assert all(len(instruction_for(role)) <= INSTRUCTION_LIMIT for role in manifest["instructions"])
    assert {name: item["utf8_bytes"] for name, item in manifest["wire_schemas"].items()} == {
        "research": 2934, "strategy": 3014, "finance": 3169,
        "single": 2630, "writer": 2630, "critic": 1134, "patch": 1920,
    }
    assert all(item["utf8_bytes"] <= 4000 for item in manifest["wire_schemas"].values())


@pytest.mark.parametrize("case_id", ["ai_education", "intelligent_ring"])
def test_dto_canonical_roundtrip_and_fixed_sections(case_id):
    condition = "A" if case_id == "ai_education" else "C"
    context = ContractContext.from_case(ROOT, case_id, condition=condition)
    roles = ("single",) if condition == "A" else ("research", "strategy", "finance", "writer")
    for role in roles:
        canonical = ROLE_SCHEMAS[role].model_validate(
            synthetic_artifact(context, role, version=1, inputs={}))
        wire = compact_role_output(context, role, canonical)
        restored = expand_role_wire(context, role, wire, version=1)
        assert canonical_hash(restored.model_dump(mode="json")) == canonical_hash(
            canonical.model_dump(mode="json"))
        if role in ("single", "writer"):
            assert len(wire.sections) == 13
        if role == "finance":
            assert restored.financial_values == context.finance.expected_values()


def test_short_evidence_and_finance_ids_are_closed():
    context = ContractContext.from_case(ROOT, "ai_education", condition="C")
    canonical = ROLE_SCHEMAS["research"].model_validate(
        synthetic_artifact(context, "research", version=1, inputs={}))
    bad = compact_role_output(context, "research", canonical).model_dump(mode="json")
    bad["market"][0]["claims"][0]["e"] = ["E99"]
    with pytest.raises(ValueError, match="unknown compact evidence"):
        expand_role_wire(context, "research", bad, version=1)

    finance = ROLE_SCHEMAS["finance"].model_validate(
        synthetic_artifact(context, "finance", version=1, inputs={}))
    bad = compact_role_output(context, "finance", finance).model_dump(mode="json")
    bad["revenue"][0]["f"] = ["unknown.value"]
    with pytest.raises(ValueError, match="unknown financial"):
        expand_role_wire(context, "finance", bad, version=1)


def test_mechanical_repair_is_bounded_and_auditable():
    raw = 'prefix {"scores":[3,3,3,3],"status":"pass","issues":[],"extra":1} suffix'
    candidate, changes = mechanical_repair_json(raw, CriticWire)
    assert candidate.status == "PASS"
    assert {item["op"] for item in changes} == {
        "extract_unique_json", "normalize_enum", "remove_extra"}
    with pytest.raises(json.JSONDecodeError):
        mechanical_repair_json('{"scores":[3,3,3,3],"status":"PASS","issues":[]} '
            '{"scores":[3,3,3,3],"status":"PASS","issues":[]}', CriticWire)


def test_patch_cannot_exceed_critic_targets_or_repeat_revision():
    context = ContractContext.from_case(ROOT, "ai_education", condition="C")
    canonical = ROLE_SCHEMAS["research"].model_validate(
        synthetic_artifact(context, "research", version=1, inputs={}))
    previous = context.accept("research", canonical)
    report_data = synthetic_report("research", severity="high")
    report_data["issues"][0].update(target_fields=["market_trends.0.finding"],
        fix_code="retain_limit")
    report = ComponentCritiqueReport.model_validate(report_data)
    bad_patch = {"claims": [], "fields": [{"issue": "research.issue1",
        "path": "customer_notes.0.finding", "value": "A long but unauthorized replacement."}]}
    with pytest.raises(ValueError, match="exceeds Critic-authorized targets"):
        apply_patch_wire(context, previous, report, bad_patch)

    generator = ContractGenerator(object(), protocol=WIRE_VERSION)
    with pytest.raises(ValueError, match="only one same-role semantic patch"):
        generator.generate_compact(context, "research", previous=replace(previous, version=2),
            version=2, revision_feedback=report)


def test_compact_pass_paths_and_c_d_hash_equivalence(tmp_path):
    runs = {}
    for condition in ("C", "D"):
        _, provider, workflow, result = compact_run(tmp_path, condition=condition)
        assert result["status"] == "completed" and len(provider.calls) == 8
        assert result["mvp30_state"] == result["valid_plan60_state"] == "reached"
        attempts = replay_events(workflow.journal.path)["attempts"]
        assert all(item["instruction_chars"] <= INSTRUCTION_LIMIT for item in attempts)
        assert all(item["role_input_target_estimate_passed"] for item in attempts)
        assert all(item["estimated_input_tokens"] <= ROLE_INPUT_TOKENS[
            "revision" if item["task_purpose"] == "revision" else item["task_role"]]
            for item in attempts)
        runs[condition] = {task.logical_task_id: (task.role_view_sha256,
            task.normalized_prompt_sha256, task.schema_sha256) for task in workflow.generator.tasks}
    assert runs["C"] == runs["D"]


def test_each_high_issue_revises_once_without_second_critic(tmp_path):
    _, provider, workflow, result = compact_run(tmp_path, fail_roles=METRICS)
    assert result["status"] == "completed" and len(provider.calls) == 12
    assert result["branches"] == {role: "revise_once" for role in METRICS}
    assert all(ref["artifact_version"] == 2 for ref in result["effective_artifacts"].values())
    assert all(issue["status"] == "unverified_after_revision" for issue in result["issues"])
    tasks = [task.logical_task_id for task in workflow.generator.tasks]
    assert sum(".critic." in task for task in tasks) == 4
    assert sum("revision.v2" in task for task in tasks) == 4
    assert all(any(diff["kind"] == "semantic_patch" for diff in task.deterministic_diffs)
        for task in workflow.generator.tasks if "revision.v2" in task.logical_task_id)


@pytest.mark.parametrize("severity", ["low", "medium"])
def test_low_and_medium_issues_are_retained_without_revision(tmp_path, severity):
    _, _, _, result = compact_run(tmp_path, fail_roles=["research"], severity=severity)
    assert result["status"] == "completed"
    assert result["branches"]["research"] == "skip_revision"
    assert any(issue["severity"] == severity for issue in result["issues"])
    assert result["effective_artifacts"]["research"]["artifact_version"] == 1


def test_compact_config_does_not_silently_migrate_legacy():
    data = dict(condition="C", run_kind="debug", provider="mock", model_exact_id="x",
        model_config_version="x", max_requests=1, max_total_tokens=1,
        max_output_tokens=1800, max_prompt_chars=26_000, request_seconds=1,
        run_seconds=3600, protocol_version=WIRE_VERSION)
    with pytest.raises(ValueError, match="config version"):
        ReviewRunConfig(**data)
    legacy = ReviewRunConfig(**{**data, "protocol_version": "body-then-grounding-v1",
        "run_seconds": 5400, "max_output_tokens": 1024})
    assert legacy.config_version == "review-run-v1-s2"
