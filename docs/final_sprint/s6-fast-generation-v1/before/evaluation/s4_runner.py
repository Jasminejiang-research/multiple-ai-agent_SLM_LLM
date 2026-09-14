"""Eight immutable slots, durable dispatch claims and fail-closed S5 admission.

dry-run/status/reconcile are offline. Only execute with a complete, matching
freeze record can construct a real provider. Reconciliation never reruns a slot.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import random
from uuid import uuid4

from evaluation.s4_io import (append_event, contained, file_hash, read_journal,
                              read_json, write_csv, write_json)
from schemas.evidence import canonical_hash
from workflow.contract_context import ContractContext
from workflow.review_config import ReviewRunConfig

ROOT = Path(__file__).resolve().parents[1]
CASE_IDS = ("ai_education", "intelligent_ring")
COMMON_FIELDS = ("max_requests", "max_total_tokens", "max_output_tokens", "max_prompt_chars",
                 "node_seconds", "run_seconds", "request_seconds", "transport_retries",
                 "temperature", "context_tokens")
TERMINAL = {"succeeded", "failed", "cancelled", "interrupted_unknown"}
AUTHORITY_ROOT = Path("C:/Users/JasmineJiang/Desktop/s4/hu-3.Intelligent System/@final presentation")
AUTHORITY_NAMES = ("sprint_plan_.md","@ai_agent_evaluation_metrics_spec.md","@multiple_ai_agent_optimization.md")


def code_inventory(root=ROOT):
    root = Path(root)
    files = [root / "app.py", root / "requirements.txt"]
    for folder in ("agents", "evaluation", "prompts", "rag", "schemas", "slm", "storage", "tools", "workflow"):
        files.extend(p for p in (root/folder).rglob("*") if p.is_file() and
            "__pycache__" not in p.parts and ".pytest_cache" not in p.parts and
            "tests" not in p.relative_to(root/folder).parts and p.suffix in (".py", ".md", ".ps1", ".json"))
    return {p.relative_to(root).as_posix(): file_hash(p) for p in sorted(set(files))}


def runtime_inventory():
    import importlib.metadata
    import platform
    return dict(python=platform.python_version(),packages={name:importlib.metadata.version(name) for name in
        ("google-genai","langgraph","pydantic","sqlalchemy","streamlit","requests","tokenizers")})


def create_experiment(directory, *, case_root=ROOT/"docs/final_sprint/s0-v1", seed=20260906,
                      synthetic=False):
    directory, case_root = Path(directory), Path(case_root).resolve()
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    protocol = read_json(case_root/"protocol.json")
    if tuple(protocol["case_ids"]) != CASE_IDS or protocol["planned_runs"] != 8:
        raise ValueError("two fixed cases and eight slots required")
    rng = random.Random(seed)
    rows = []
    for case_id in CASE_IDS:
        ctx = ContractContext.from_case(case_root, case_id, condition="A")
        order = list("ABCD")
        rng.shuffle(order)
        for condition in order:
            rows.append(dict(planned_id=f"{case_id}-{condition}", case_id=case_id,
                condition=condition, order=len(rows)+1, packet_sha256=ctx.packet_sha256,
                brief_sha256=ctx.brief_sha256, canonical=not synthetic))
    directory.mkdir(parents=True, exist_ok=False)
    plan = dict(version="eight-slot-s4-v1", experiment_id=uuid4().hex, randomization_seed=seed,
        kind="synthetic_rehearsal" if synthetic else "formal_plan", case_root=str(case_root),
        protocol_sha256=file_hash(case_root/"protocol.json"), rows=rows)
    write_json(directory/"plan.json", plan)
    write_json(directory/"freeze.json", dict(status="pending", plan_sha256=canonical_hash(plan),
        approvals=dict(cases="pending", common_budget="deferred", D_preflight="deferred",
            gemini_quota_and_spend="pending", S1="passed", S2="passed", S4="pending",
            formal_execution="not_authorized_in_S4"),
        approval_records={}, configs={}, code_inventory={}, evidence_files={}, preflight_reports={},
        authority_files={str(AUTHORITY_ROOT/name):file_hash(AUTHORITY_ROOT/name) for name in AUTHORITY_NAMES},
        total_request_limit=None, total_token_limit=None, runtime_versions={},model_metadata={}))
    write_csv(directory/"manifest.csv", status(directory)["rows"])
    return plan


def load_plan(directory):
    plan = read_json(Path(directory)/"plan.json")
    rows = plan["rows"]
    if len(rows) != 8 or {(r["case_id"],r["condition"]) for r in rows} != {(c,a) for c in CASE_IDS for a in "ABCD"}:
        raise ValueError("manifest must contain exactly two cases x A-D")
    if len({r["planned_id"] for r in rows}) != 8 or [r["order"] for r in rows] != list(range(1,9)):
        raise ValueError("invalid planned IDs/order")
    rng = random.Random(plan["randomization_seed"])
    expected = []
    for case in CASE_IDS:
        order = list("ABCD")
        rng.shuffle(order)
        expected.extend((case, arm) for arm in order)
    if expected != [(r["case_id"],r["condition"]) for r in rows]:
        raise ValueError("case block randomization changed")
    return plan


def _result_state(result, resource_failure=None):
    execution = "succeeded" if result.get("status") == "completed" and result.get("terminal_contract_passed") else (
        "cancelled" if result.get("status") == "cancelled" else "failed")
    if resource_failure:
        execution="failed"
    return dict(execution=execution, terminal_contract=result.get("terminal_contract_state",
        "passed" if result.get("terminal_contract_passed") else "not_checked"),
        scorable_output="available" if result.get("scorable_artifact_ref") else "not_available",
        needs_human_review=bool(result.get("needs_human_review")),
        failure_reason=resource_failure or (result.get("error") or {}).get("error_type"), workflow_status=result.get("status"))


def status(directory):
    directory = Path(directory)
    plan = load_plan(directory)
    rows = {r["planned_id"]: dict(**r, execution="not_run", terminal_contract="not_checked",
        scorable_output="not_available", needs_human_review=False, run_id=None, run_path=None,
        failure_reason=None, workflow_status=None) for r in plan["rows"]}
    events, torn = read_journal(directory/"schedule.jsonl")
    for event in events:
        if event.get("planned_id") not in rows:
            if event.get("kind") in ("stop", "recovery"):
                continue
            raise ValueError("schedule event does not belong to a planned slot")
        row = rows[event["planned_id"]]
        if event["kind"] == "claim":
            if row["execution"] != "not_run":
                raise ValueError("duplicate dispatch claim; preserve audit")
            row.update(execution="running", run_id=event["run_id"], run_path=event["run_path"])
        elif event["kind"] in ("result", "reconcile"):
            if row["execution"] != "running":
                raise ValueError("terminal slot cannot be overwritten")
            row.update(event["state"])
        elif event["kind"] == "resolve_unknown":
            if row["execution"] != "interrupted_unknown":
                raise ValueError("only unknown outcomes can be resolved; no reruns")
            row.update(execution="failed", needs_human_review=True, failure_reason=event["note"])
    return dict(experiment_id=plan["experiment_id"], kind=plan["kind"], rows=list(rows.values()),
        journal_truncated=torn, lock_present=(directory/"runner.lock").exists(),
        formal_runs_started=sum(r["execution"] != "not_run" for r in rows.values()) if plan["kind"] == "formal_plan" else 0)


@contextmanager
def runner_lock(directory):
    path = Path(directory)/"runner.lock"
    write_json(path, dict(pid=os.getpid(), token=uuid4().hex))
    try:
        yield
    finally:
        path.unlink()


def reconcile(directory, *, recover_dead_lock=False):
    directory = Path(directory)
    lock = directory/"runner.lock"
    if lock.exists():
        if not recover_dead_lock:
            raise ValueError("runner lock exists; explicit dead-process recovery required")
        pid = read_json(lock)["pid"]
        # Windows os.kill(pid, 0) is not a portable process liveness check.
        if process_exists(pid):
            raise ValueError("runner process still exists; cannot recover its lock")
        lock.rename(directory/f"runner.dead.{uuid4().hex}.json")
    with runner_lock(directory):
        snapshot = status(directory)
        if snapshot["journal_truncated"]:
            # Archive exact original bytes; replay only durable complete records.
            path = directory/"schedule.jsonl"
            events, _ = read_journal(path)
            path.rename(directory/f"schedule.torn.{uuid4().hex}.jsonl")
            for event in events:
                # Preserve original IDs/timestamps in recovered projection.
                append_event(path, event)
        from evaluation.s4_metrics import reduce_run
        for row in snapshot["rows"]:
            if row["execution"] != "running":
                continue
            run_dir = contained(directory, row["run_path"])
            reduced = reduce_run(run_dir, condition=row["condition"])
            result = reduced["result"]
            if result and not reduced["unclosed_attempts"]:
                state = _result_state(result,reduced["resource_failure"])
            else:
                state = dict(execution="interrupted_unknown", terminal_contract="not_checked",
                    scorable_output="pending_review", needs_human_review=True,
                    failure_reason="interrupted dispatch; never retry this canonical slot")
            append_event(directory/"schedule.jsonl", dict(kind="reconcile", planned_id=row["planned_id"], state=state))
        write_csv(directory/"manifest.csv", status(directory)["rows"])
    return status(directory)


def process_exists(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError("invalid recorded process identity")
    if os.name != "nt":
        try:
            os.kill(pid,0)
            return True
        except ProcessLookupError:
            return False
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD)
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes=(wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD))
    kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:
        if ctypes.get_last_error()==87:
            return False
        raise ValueError("process liveness unavailable; preserve runner lock")
    try:
        code=wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):
            raise ValueError("process liveness unavailable; preserve runner lock")
        return code.value==259
    finally:
        kernel.CloseHandle(handle)


def resolve_unknown(directory, planned_id, note):
    if not note or len(note.strip()) < 12:
        raise ValueError("a concrete reconciliation note is required")
    with runner_lock(directory):
        row = next(r for r in status(directory)["rows"] if r["planned_id"] == planned_id)
        if row["execution"] != "interrupted_unknown":
            raise ValueError("slot is not unknown")
        append_event(Path(directory)/"schedule.jsonl", dict(kind="resolve_unknown", planned_id=planned_id, note=note))
        write_csv(Path(directory)/"manifest.csv", status(directory)["rows"])


def check_freeze(directory, *, root=ROOT):
    directory = Path(directory)
    plan, freeze = load_plan(directory), read_json(directory/"freeze.json")
    errors = []
    if plan["kind"] != "formal_plan" or freeze.get("status") != "frozen":
        errors.append("formal freeze pending (S4 is engineering/offline only)")
    if freeze.get("plan_sha256") != canonical_hash(plan):
        errors.append("plan hash changed")
    for key in ("cases", "common_budget", "D_preflight", "gemini_quota_and_spend", "S1", "S2", "S4", "formal_execution"):
        accepted = ("passed","approved") if key in ("S1","S2","S4") else ("approved",)
        if freeze.get("approvals", {}).get(key) not in accepted or not freeze.get("approval_records", {}).get(key):
            errors.append(f"approval/evidence pending: {key}")
    authorities = freeze.get("authority_files",{})
    if set(authorities) != {str(AUTHORITY_ROOT/name) for name in AUTHORITY_NAMES}:
        errors.append("authoritative design/plan inventory missing")
    for path,digest in authorities.items():
        if not Path(path).is_file() or file_hash(path) != digest:
            errors.append("authoritative design/plan changed")
    if not freeze.get("code_inventory") or freeze["code_inventory"] != code_inventory(root):
        errors.append("actual code/prompt/config working-tree snapshot not frozen or changed")
    if freeze.get("runtime_versions") != runtime_inventory():
        errors.append("Python/provider/framework runtime versions not frozen or changed")
    case_root = Path(plan["case_root"])
    if file_hash(case_root/"protocol.json") != plan["protocol_sha256"]:
        errors.append("protocol hash changed")
    for row in plan["rows"]:
        try:
            ctx = ContractContext.from_case(case_root, row["case_id"], condition=row["condition"], execution_mode="formal_frozen")
            if (ctx.packet_sha256,ctx.brief_sha256) != (row["packet_sha256"],row["brief_sha256"]):
                errors.append("frozen input hash changed")
        except (ValueError, OSError) as exc:
            errors.append(f"{row['case_id']}: {exc}")
    expected_evidence = {p.relative_to(case_root).as_posix(): file_hash(p) for p in sorted((case_root/"cases").rglob("*")) if p.is_file()}
    if freeze.get("evidence_files") != expected_evidence:
        errors.append("complete input/snapshot inventory not frozen or changed")
    configs = {}
    try:
        configs = {arm: ReviewRunConfig.model_validate(freeze["configs"][arm]) for arm in "ABCD"}
        common = {k:getattr(configs["A"],k) for k in COMMON_FIELDS}
        for arm, cfg in configs.items():
            if cfg.condition != arm or cfg.run_kind != "formal":
                errors.append("config condition/run kind mismatch")
            if {k:getattr(cfg,k) for k in COMMON_FIELDS} != common:
                errors.append("A-D public budgets must match")
            if arm != "D" and (cfg.provider != "gemini" or cfg.model_exact_id != "gemini-2.5-flash"):
                errors.append("A-C must use Gemini 2.5 Flash")
            if arm == "D" and (cfg.provider != "local" or not cfg.model_exact_id.startswith("granite-h-micro-32k@")):
                errors.append("D must use verified H Micro digest")
    except (KeyError, ValueError, TypeError):
        errors.append("complete explicit A-D configs pending")
    for key in ("total_request_limit", "total_token_limit"):
        if type(freeze.get(key)) is not int or freeze[key] <= 0:
            errors.append(f"approved experiment stop limit pending: {key}")
    # S3's real complete preflight record must match exactly, not a warmup/ProbeAck.
    try:
        report_ref = freeze["preflight_reports"]["D"]
        report_path = Path(report_ref["path"])
        report = read_json(report_path)
        if file_hash(report_path) != report_ref["sha256"] or report["status"] != "go" or report["requested_phase"] != "all":
            raise ValueError("D full preflight not passed")
        if any(report["phases"][phase]["status"] != "passed" for phase in ("warmup", "context", "components", "smoke")):
            raise ValueError("D phase missing/failed")
        from slm.granite_config import GraniteConfig
        local = GraniteConfig.model_validate(report["config"])
        if local.review_config("formal", model_digest=report["metadata"]["model_digest"]) != configs["D"]:
            raise ValueError("D preflight differs from frozen budget/model")
        if report["resources"]["status"] != "passed" or report["model_calls"] <= 0:
            raise ValueError("D real telemetry missing")
        smoke = report["phases"]["smoke"]["result"]
        if smoke.get("mock_only") is not False or smoke.get("condition") != "D" or smoke.get("terminal_contract_passed") is not True:
            raise ValueError("D smoke is not a real complete final proposal")
    except (KeyError, ValueError, TypeError, OSError):
        errors.append("complete D real preflight and matching common config pending")
    for arm in "ABC":
        try:
            ref=freeze["preflight_reports"][arm]
            path=Path(ref["path"])
            from evaluation.s4_metrics import reduce_run
            evidence=reduce_run(path.parent,condition=arm)
            cfg=ReviewRunConfig.model_validate(evidence["config"])
            if file_hash(path)!=ref["sha256"] or not evidence["completed"] or cfg.run_kind != "smoke" or cfg.condition!=arm or cfg.provider!="gemini":
                raise ValueError("non-formal Gemini smoke missing")
            actual=cfg.model_dump(mode="json")
            actual["run_kind"]="formal"
            if actual!=configs[arm].model_dump(mode="json") or not evidence["attempts"] or (evidence["result"] or {}).get("mock_only") is not False:
                raise ValueError("Gemini smoke config/model mismatch")
        except (KeyError,ValueError,TypeError,OSError):
            errors.append(f"{arm} real smoke with matching common config pending")
    return dict(ready=not errors, blockers=list(dict.fromkeys(errors)))


@dataclass(frozen=True)
class FormalPermit:
    directory: Path
    planned_id: str
    run_id: str

    def validate(self, context, config, run_id, planned_id):
        gates = check_freeze(self.directory)
        if not gates["ready"]:
            raise ValueError("formal freeze gates not satisfied")
        row = next(r for r in status(self.directory)["rows"] if r["planned_id"] == self.planned_id)
        if (run_id, planned_id, row["execution"]) != (self.run_id, self.planned_id, "running"):
            raise ValueError("formal slot is not claimed by this run")
        if not (self.directory/"runner.lock").exists() or context.execution_mode != "formal_frozen":
            raise ValueError("formal runner lock/frozen context required")
        if row["run_id"] != run_id or row["condition"] != config.condition or row["case_id"] != context.case_id:
            raise ValueError("formal run identity mismatch")
        if config.model_dump(mode="json") != read_json(self.directory/"freeze.json")["configs"][config.condition]:
            raise ValueError("config not frozen")


def execute(directory, *, synthetic=False, max_runs=8, executor=None):
    """Continue untouched slots only. Each slot is claimed durably before setup/calls."""
    directory = Path(directory)
    plan = load_plan(directory)
    if synthetic != (plan["kind"] == "synthetic_rehearsal"):
        raise ValueError("synthetic and formal slots cannot mix")
    if not synthetic:
        gates = check_freeze(directory)
        if not gates["ready"]:
            raise ValueError("; ".join(gates["blockers"]))
    if type(max_runs) is not int or not 1 <= max_runs <= 8:
        raise ValueError("max-runs must be 1..8")
    with runner_lock(directory):
        snapshot = status(directory)
        if snapshot["journal_truncated"] or any(r["execution"] in ("running", "interrupted_unknown") for r in snapshot["rows"]):
            raise ValueError("reconciliation required before continuing; unknown slots cannot be rerun")
        started = 0
        for row in snapshot["rows"]:
            if row["execution"] != "not_run" or started >= max_runs:
                continue
            if not synthetic:
                gates = check_freeze(directory)
                if not gates["ready"]:
                    raise ValueError("frozen state changed before dispatch")
                from evaluation.s4_metrics import reduce_run
                prior = [reduce_run(contained(directory,r["run_path"]), condition=r["condition"]) for r in status(directory)["rows"] if r["run_path"]]
                freeze = read_json(directory/"freeze.json")
                cfg = freeze["configs"][row["condition"]]
                if any(p["usage_incomplete"] for p in prior) or sum(p["request_count"] for p in prior)+cfg["max_requests"] > freeze["total_request_limit"] or sum(p["total_tokens"] or 0 for p in prior)+cfg["max_total_tokens"] > freeze["total_token_limit"]:
                    append_event(directory/"schedule.jsonl", dict(kind="stop", reason="experiment budget reservation/missing usage"))
                    break
            run_id = uuid4().hex
            run_path = f"runs/{row['planned_id']}/{run_id}"
            append_event(directory/"schedule.jsonl", dict(kind="claim", planned_id=row["planned_id"], run_id=run_id, run_path=run_path))
            started += 1
            write_csv(directory/"manifest.csv", status(directory)["rows"])
            # Exceptions not already persisted by the workflow leave an unknown slot.
            # This deliberately preserves uncertainty rather than risking another call.
            action = executor or (synthetic_executor if synthetic else real_executor)
            result = action(plan, row, run_id, contained(directory,run_path),
                None if synthetic else FormalPermit(directory,row["planned_id"],run_id))
            from evaluation.s4_metrics import reduce_run
            reduced=reduce_run(contained(directory,run_path),condition=row["condition"])
            state = _result_state(result,reduced["resource_failure"])
            append_event(directory/"schedule.jsonl", dict(kind="result", planned_id=row["planned_id"], state=state))
            write_csv(directory/"manifest.csv", status(directory)["rows"])
            if result.get("status") in ("timeout", "cancelled", "budget_exhausted") or reduced["resource_failure"]:
                append_event(directory/"schedule.jsonl", dict(kind="stop", reason=result["status"]))
                break
    return status(directory)


def synthetic_executor(plan, row, run_id, run_dir, permit):
    from evaluation.s2_fixtures import SyntheticProvider
    from evaluation.s4_resources import RunTelemetry, synthetic_probe
    from workflow.review_graph import build_review_workflow
    context = ContractContext.from_case(Path(plan["case_root"]), row["case_id"], condition=row["condition"])
    # Existing S2 fixture allowances, explicitly not proposed public experiment budgets.
    config = ReviewRunConfig(condition=row["condition"], run_kind="debug", provider="mock",
        model_exact_id=SyntheticProvider.model_exact_id, model_config_version="s4-synthetic-only",
        max_requests=64, max_total_tokens=20_000_000, max_output_tokens=1024,
        max_prompt_chars=1_000_000, request_seconds=10)
    provider = SyntheticProvider(context, fail_roles=config.reviewed_roles if row["case_id"] == "intelligent_ring" else (), severity="critical")
    workflow = build_review_workflow(context, config=config, provider=provider, output_dir=run_dir,
        run_id=run_id, planned_id=row["planned_id"])
    with RunTelemetry(workflow.journal, workflow.client.cancel, probe=synthetic_probe):
        return workflow.run()


def real_executor(plan, row, run_id, run_dir, permit):
    """Lazy real adapters. This is unreachable from dry-run/export/rehearsal."""
    from threading import Event
    from evaluation.s4_resources import RunTelemetry
    from workflow.review_graph import build_review_workflow
    config = ReviewRunConfig.model_validate(read_json(permit.directory/"freeze.json")["configs"][row["condition"]])
    context = ContractContext.from_case(Path(plan["case_root"]),row["case_id"],condition=row["condition"],execution_mode="formal_frozen")
    cancel, owner, local_lease = Event(), None, None
    if row["condition"] == "D":
        import shutil
        from slm.granite_provider import GranitePhysicalProvider, inspect_ollama
        from slm.granite_config import GraniteConfig
        from slm.owned_ollama import OwnedOllama
        from slm.resource_monitor import hidden_run
        from workflow.review_runtime import LocalRequestLease
        freeze = read_json(permit.directory/"freeze.json")
        preflight = read_json(freeze["preflight_reports"]["D"]["path"])
        local = GraniteConfig.model_validate(preflight["config"])
        server_dir = run_dir.parent/(run_id+"-server")
        from workflow.review_events import EventJournal
        setup_journal=EventJournal(run_dir.parent/(run_id+"-setup"),run_id)
        try:
            hidden_run([shutil.which("pwsh") or "powershell", "-NoProfile", "-File", str(ROOT/"slm/start_granite.ps1"),
                "-OutputDirectory", str(server_dir)], timeout=45)
        except BaseException:
            if (server_dir/"server_owner.json").exists():
                OwnedOllama(server_dir/"server_owner.json",journal=setup_journal,endpoint=local.endpoint).stop()
            raise
        owner=OwnedOllama(server_dir/"server_owner.json",journal=setup_journal,endpoint=local.endpoint)
        provider = GranitePhysicalProvider(local, model_digest=preflight["metadata"]["model_digest"])
        local_lease = LocalRequestLease(ROOT/"data/granite_endpoint_leases", local.endpoint)
    else:
        from dotenv import load_dotenv
        from workflow.review_providers import GeminiPhysicalProvider
        load_dotenv(ROOT/".env")
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError("Gemini API credential missing")
        provider = GeminiPhysicalProvider(api_key=key)
    try:
        workflow = build_review_workflow(context, config=config, provider=provider, output_dir=run_dir,
            run_id=run_id, planned_id=row["planned_id"], local_lease=local_lease, cancel=cancel, formal_permit=permit)
        if row["condition"] == "D":
            owner.journal=workflow.journal
            owner.validate()
            metadata = inspect_ollama(local)
            if metadata != preflight["metadata"]:
                # Some metadata is dynamic; exact runtime/model identity is what is frozen.
                for key in ("model_digest", "ollama_version", "quantization"):
                    if metadata.get(key) != preflight["metadata"].get(key):
                        raise ValueError("Granite model/runtime differs from preflight")
            workflow.journal.emit("model_metadata", metadata)
        with RunTelemetry(workflow.journal, cancel, enforce_gate=row["condition"] == "D", abort=owner.stop if owner else None):
            return workflow.run()
    finally:
        if owner:
            owner.stop()
