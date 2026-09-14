"""An admitted structure repair preserves its failed first physical attempt."""
import json
from pathlib import Path

import pytest

from evaluation.s2_fixtures import SyntheticProvider
from evaluation.s5_llm_only import run_config
from workflow.compact_protocol import (
    GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION, GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION,
    INSTRUCTION_LIMIT, REPAIR_INSTRUCTION_VERSION, ROLE_INSTRUCTIONS, SHORT_REPAIR_INSTRUCTION,
    instruction_for, protocol_manifest,
)
from workflow.contract_context import ContractContext
from workflow.review_graph import build_review_workflow
from workflow.review_runtime import PhysicalResponse


ROOT = Path(__file__).resolve().parents[1] / "docs/final_sprint/s0-v1"
CONFIG = GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION


@pytest.mark.parametrize("role", list(ROLE_INSTRUCTIONS))
def test_every_role_normal_and_repair_instruction_respects_original_hard_gate(role):
    ordinary = instruction_for(role, config_version=CONFIG)
    repaired = instruction_for(role, repair=True, config_version=CONFIG)
    assert ordinary == instruction_for(role)
    assert repaired == ordinary + " " + SHORT_REPAIR_INSTRUCTION
    assert len(ordinary) <= INSTRUCTION_LIMIT and len(repaired) <= INSTRUCTION_LIMIT
    with pytest.raises(ValueError, match="instruction limit exceeded"):
        instruction_for(role, repair=True, config_version=GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION)


def test_manifest_seals_all_repair_instruction_lengths():
    manifest = protocol_manifest(CONFIG)
    assert manifest["repair_instruction_version"] == REPAIR_INSTRUCTION_VERSION
    assert set(manifest["repair_instructions"]) == set(ROLE_INSTRUCTIONS)
    assert max(row["chars"] for row in manifest["repair_instructions"].values()) == 496
    assert all(row["chars"] <= 500 for row in manifest["repair_instructions"].values())
    assert protocol_manifest(GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION)["repair_instructions"] is None


class OfflineGeminiFixture(SyntheticProvider):
    provider = "gemini"
    model_exact_id = "gemini-2.5-flash"


@pytest.mark.parametrize("config_version,expected_calls", [(CONFIG, 2),
    (GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION, 1)])
def test_invalid_then_correct_output_enters_one_bounded_repair_without_erasing_first_failure(
        tmp_path, config_version, expected_calls):
    context = ContractContext.from_case(ROOT, "ai_education", condition="A")
    invalid = json.dumps({"title": "Invalid offline fixture", "sections": []})
    def first_invalid(request, number):
        if number == 1:
            return PhysicalResponse(invalid, {"synthetic": True, "prompt": 10, "output": 5, "total": 15}, 10, 5, 15)
        return None
    provider = OfflineGeminiFixture(context, before=first_invalid)
    config = run_config("A", "smoke").model_copy(update={"config_version": config_version})
    workflow = build_review_workflow(context, config=config, provider=provider,
        output_dir=tmp_path / f"repair-{expected_calls}")
    result = workflow.run()
    assert len(provider.calls) == expected_calls
    assert workflow.client.snapshot()["request_count"] == expected_calls
    task = workflow.generator.tasks[0]
    assert task.attempts[0].passed is False
    calls = [event["payload"] for event in workflow.journal.events if event["kind"] == "call"
        and event["payload"]["status"] != "dispatching"]
    assert calls[0]["status"] == "invalid_output" and calls[0]["raw_output"] == invalid
    assert all(call["usage_raw"]["synthetic"] for call in calls)
    if config_version == CONFIG:
        assert result["status"] == "completed" and result["terminal_contract_passed"]
        assert len(task.attempts) == 2 and task.attempts[1].passed is True
        assert task.attempts[1].purpose == "structure_repair"
        assert calls[1]["status"] == "succeeded"
        assert task.first_output_passed is False
        assert workflow.client.snapshot()["structure_repair_request_count"] == 1
        assert len(provider.calls[1].system_instruction) <= 500
        assert (workflow.journal.directory / "internal_export/proposal.md").is_file()
    else:
        assert result["status"] == "failed" and not result["terminal_contract_passed"]
        assert len(task.attempts) == 1
        assert workflow.client.snapshot()["structure_repair_request_count"] == 0
