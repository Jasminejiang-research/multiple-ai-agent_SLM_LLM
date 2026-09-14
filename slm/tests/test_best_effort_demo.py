"""Offline controls for the independent non-formal best-effort product mode."""
from contextlib import nullcontext
import json
from pathlib import Path

from slm.best_effort_demo import (
    BestEffortDemo, BestEffortDemoConfig, DemoCritic, DemoText,
    MISSING_TEXT, MODE, QUALITY_LABEL, salvage_text,
)
from workflow.contract_context import ContractContext
from workflow.review_runtime import PhysicalResponse


ROOT = Path(__file__).resolve().parents[2]


def resource_sample():
    return dict(ram_total_bytes=16 * 1024**3, ram_available_bytes=8 * 1024**3,
        pagefile_used_bytes=0, gpu_used_bytes=0, gpu_total_bytes=2 * 1024**3,
        loaded_models=[{"context_length": 32768, "size_vram": 0}], missing={})


class FakeOwner:
    def __init__(self, *args, **kwargs):
        self.proof = None
    def validate(self):
        return None
    def stop(self):
        self.proof = {"status": "owned_process_tree_terminated", "synthetic": True,
            "lease_released": False}
        return self.proof


class DemoProvider:
    provider = "local"

    def __init__(self, config, *, model_digest, bad_critics=False, truncate_writer=False,
                 timeout_role=None):
        self.model_exact_id = f"{config.model_alias}@{model_digest}"
        self.bad_critics = bad_critics
        self.truncate_writer = truncate_writer
        self.timeout_role = timeout_role
        self.calls = []
        self.last_raw = None
        self.last_diagnostic = None

    def invoke(self, request):
        self.calls.append(request)
        prompt = request.prompt
        role = next(role for role in (
            "research_critic", "strategy_critic", "finance_critic", "final_critic",
            "research", "strategy", "finance", "writer") if prompt.startswith(f"ROLE {role}."))
        if role == self.timeout_role:
            self.last_raw = {"model": "granite-h-micro-32k", "done": False,
                "message": {"content": ""}}
            self.last_diagnostic = {"response": self.last_raw, "requested_gpu_layers": 0}
            raise TimeoutError("synthetic bounded timeout")
        finish = "stop"
        if request.schema is DemoCritic:
            raw = "{" if self.bad_critics else json.dumps({"score": 1,
                "issues": "Unsupported claim and missing validation."})
        elif role == "writer":
            if self.truncate_writer:
                raw = ('{"text":"[SECTION: Executive Summary] Partial demo [EDU-01]. '
                    '[SECTION: Problem] Evidence remains limited')
                finish = "length"
            else:
                text = " ".join(f"[SECTION: {title}] Short demo statement [EDU-01]."
                    for title in __import__("schemas.workflow", fromlist=["PROPOSAL_SECTION_TITLES"]).PROPOSAL_SECTION_TITLES)
                raw = json.dumps({"text": text})
        else:
            raw = json.dumps({"text": f"{role} short statement [EDU-01]. Unsupported idea: assumption/unsupported."})
        self.last_raw = {"model": "granite-h-micro-32k", "done": True,
            "done_reason": finish, "message": {"content": raw},
            "prompt_eval_count": 20, "eval_count": 10}
        self.last_diagnostic = {"response": self.last_raw, "requested_gpu_layers": 0}
        return PhysicalResponse(raw, {"synthetic": True}, 20, 10, 30, finish)


def make_demo(tmp_path, *, bad_critics=False, truncate_writer=False, max_requests=10,
              timeout_role=None):
    config = BestEffortDemoConfig.model_validate_json(
        (ROOT / "slm/configs/granite_best_effort_demo_v1.json").read_text())
    if max_requests != 10:
        config = config.model_copy(update={"max_requests": max_requests})
    context = ContractContext.from_case(ROOT / "docs/final_sprint/s0-v1",
        "ai_education", condition="D")
    providers = []
    def factory(config, *, model_digest):
        provider = DemoProvider(config, model_digest=model_digest,
            bad_critics=bad_critics, truncate_writer=truncate_writer,
            timeout_role=timeout_role)
        providers.append(provider)
        return provider
    demo = BestEffortDemo(config=config, context=context, output_dir=tmp_path / "run",
        owner_path="unused", probe=resource_sample,
        metadata={"model_digest": "test-digest", "loaded_models": []},
        provider_factory=factory, owner_factory=FakeOwner,
        awake_factory=lambda **kwargs: nullcontext())
    demo.lease_dir = tmp_path / "leases"
    return demo, providers[0]


def test_config_is_independent_and_cannot_expand_authorized_limits():
    raw = json.loads((ROOT / "slm/configs/granite_best_effort_demo_v1.json").read_text())
    config = BestEffortDemoConfig.model_validate(raw)
    assert config.mode == MODE and "condition" not in config.model_dump()
    for change in ({"gpu_layers": 1}, {"max_requests": 11},
                   {"max_total_tokens": 80001}, {"run_seconds": 1801}):
        import pytest
        with pytest.raises(ValueError):
            BestEffortDemoConfig.model_validate({**raw, **change})


def test_all_roles_and_critics_run_but_scores_do_not_gate_export(tmp_path):
    demo, provider = make_demo(tmp_path, bad_critics=True)
    result = demo.run()
    assert result["status"] == "completed_best_effort_demo"
    assert result["formal_condition"] is None and not result["formal_eligible"]
    assert not result["c_minus_d_comparison_eligible"] and result["formal_runs_started"] == 0
    assert len(provider.calls) == result["model_calls"] == 8
    assert len(result["critic_results"]) == 4
    assert all(row["status"] == "failed_saved" and row["score"] is None
        and row["advisory_only"] and not row["blocks_generation"]
        for row in result["critic_results"])
    assert Path(result["artifact"]["markdown_path"]).exists()


def test_truncated_writer_is_saved_and_fixed_13_section_plan_is_assembled(tmp_path):
    demo, _ = make_demo(tmp_path, truncate_writer=True)
    result = demo.run()
    plan = Path(result["artifact"]["markdown_path"]).read_text(encoding="utf-8")
    assert QUALITY_LABEL in plan and "不得作为正式实验结果" in plan
    assert plan.count("\n## ") == 13 and result["artifact"]["section_count"] == 13
    assert MISSING_TEXT in plan and "Partial demo [EDU-01]" in plan
    assert result["artifact"]["deterministic_finance_count"] == 21
    writer = next(row for row in result["role_steps"] if row["role"] == "writer")
    assert writer["status"] == "truncated_saved"
    assert Path(writer["raw"]["text_path"]).read_text(encoding="utf-8").startswith('{"text"')


def test_budget_stop_still_exports_without_extra_calls(tmp_path):
    demo, provider = make_demo(tmp_path, max_requests=2)
    result = demo.run()
    assert result["status"] == "partial_best_effort_demo"
    assert result["model_calls"] == len(provider.calls) == 2
    assert result["budget"]["request_count"] == 2
    assert result["artifact"]["section_count"] == 13
    assert Path(result["artifact"]["markdown_path"]).exists()


def test_timeout_is_recorded_and_deterministic_export_continues_without_overlap(tmp_path):
    demo, provider = make_demo(tmp_path, timeout_role="research_critic")
    result = demo.run()
    plan = Path(result["artifact"]["markdown_path"])
    critic = result["critic_results"][0]
    assert result["status"] == "partial_best_effort_demo"
    assert result["hard_stop_reason"] == "TimeoutError"
    assert len(provider.calls) == result["model_calls"] == 2
    assert critic["role"] == "research_critic" and critic["status"] == "failed_saved"
    assert critic["error_type"] == "TimeoutError" and not critic["blocks_generation"]
    assert all(row["status"] == "not_run_hard_stop" for row in result["role_steps"][2:])
    assert plan.exists() and plan.read_text(encoding="utf-8").count("\n## ") == 13
    assert MISSING_TEXT in plan.read_text(encoding="utf-8")


def test_salvage_recovers_only_present_truncated_json_text():
    raw = '{"text":"present line\\nsecond present line'
    assert salvage_text(raw) == "present line\nsecond present line"
    assert salvage_text('{"other":') == ""
