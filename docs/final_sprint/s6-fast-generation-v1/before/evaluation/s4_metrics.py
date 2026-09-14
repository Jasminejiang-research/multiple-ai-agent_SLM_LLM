"""Pure offline event reduction. Counts include failures; missing is never zero."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from evaluation.s4_io import file_hash, read_journal, read_json

ROLES = ("single", "research", "strategy", "finance", "writer", "research_critic",
         "strategy_critic", "finance_critic", "final_critic", "Revision", "Supervisor")


def ratio(numerator, denominator, *, state=None, reason=None):
    if state:
        return dict(value=None, numerator=numerator, denominator=denominator, state=state, reason=reason)
    if denominator == 0:
        return dict(value=None, numerator=numerator, denominator=0, state="not_applicable", reason="zero_denominator")
    return dict(value=numerator/denominator, numerator=numerator, denominator=denominator, state="observed", reason=None)


def resource_role(call):
    if call.get("task_purpose") == "revision" or call.get("role") == "Revision":
        return "Revision"
    return call.get("task_role") or call.get("role") or "unknown"


def token_counts(calls):
    result = dict(request_count=len(calls), transport_retry_count=sum(bool(c.get("transport_retry_of")) for c in calls),
        structure_repair_count=sum(c.get("purpose") == "structure_repair" for c in calls),
        semantic_revision_request_count=sum(c.get("task_purpose") == "revision" for c in calls))
    missing = []
    for field in ("prompt_tokens", "output_tokens", "total_tokens"):
        values = [c.get(field) for c in calls]
        valid = [v for v in values if type(v) is int and v >= 0]
        result[field+"_known"] = sum(valid)
        result[field] = sum(valid) if len(valid) == len(values) else None
        if len(valid) != len(values):
            missing.append(field)
    thinking, thinking_missing = 0, 0
    for call in calls:
        raw = call.get("usage_raw") or {}
        if call.get("provider") == "gemini":
            value = raw.get("thoughts_token_count")
            if type(value) is int and value >= 0:
                thinking += value
            else:
                thinking_missing += 1
    result.update(visible_output_tokens=result["output_tokens"], thinking_tokens_known=thinking,
        thinking_tokens=None if thinking_missing else thinking,
        thinking_status="missing" if thinking_missing else "observed" if any(c.get("provider") == "gemini" for c in calls) else "not_applicable",
        usage_incomplete=bool(missing), usage_missing_fields=missing,
        usage_missing_calls=sum(any(c.get(f) is None for f in ("prompt_tokens","output_tokens","total_tokens")) for c in calls),
        total_token_basis="provider total (includes returned thinking); never add thinking to total again")
    return result


def reduce_run(directory, *, condition):
    directory = Path(directory)
    events, torn = read_journal(directory/"events.jsonl")
    calls, tasks, handoffs, artifacts = {}, {}, {}, {}
    result, config, branches, first_valid = None, {}, {}, None
    samples, routes, nodes, gates = [], [], [], {}
    resource_failure = None
    for event in events:
        body, kind = event["payload"], event["kind"]
        if kind == "call":
            key = body["attempt_id"]
            previous = calls.get(key)
            if previous and previous.get("status") != "dispatching" and previous != body:
                raise ValueError("conflicting terminal attempt records")
            calls[key] = body
        elif kind == "logical_task":
            tasks[body["logical_task_id"]] = body
        elif kind == "handoff":
            handoffs[body["handoff_id"]] = body
        elif kind == "artifact":
            artifacts[body["artifact_ref"]["artifact_id"]] = body
        elif kind == "run_result":
            if result is not None and result != body:
                raise ValueError("multiple inconsistent run results")
            result = body
        elif kind == "run":
            config = body.get("config", config)
        elif kind == "branch_inventory":
            branches = body
        elif kind == "complete_plan_contract" and body.get("passed"):
            elapsed = body.get("elapsed_seconds")
            if isinstance(elapsed,(int,float)):
                first_valid = elapsed if first_valid is None else min(elapsed,first_valid)
        elif kind == "telemetry":
            samples.append(body)
        elif kind == "route":
            routes.append(body)
        elif kind == "node":
            nodes.append(body)
        elif kind == "gate":
            gates[body["role"]] = body
        elif kind == "resource_stop":
            resource_failure=body.get("reason","resource_gate_failed")
        elif kind == "telemetry_summary" and body.get("status")=="failed" and config.get("provider")=="local":
            resource_failure=body.get("reason","resource_telemetry_failed")
    # result.json is only a projection. Durable events are the recovery authority.
    if (directory/"result.json").exists():
        projected = read_json(directory/"result.json")
        if result and projected != result:
            raise ValueError("result projection differs from durable journal")
    call_list = list(calls.values())
    unclosed = [c["attempt_id"] for c in call_list if c.get("status") in ("dispatching", "interrupted_unknown")]
    call_tasks = defaultdict(list)
    for call in call_list:
        call_tasks[call["logical_task_id"]].append(call)
    known_passes, missing_tasks = 0, []
    logical_rows = []
    for task_id in sorted(set(tasks)|set(call_tasks)):
        task, attempts = tasks.get(task_id), sorted(call_tasks[task_id],key=lambda c:c.get("attempt_index",1))
        if task is None:
            passed, state = None, "missing"
        elif not task.get("attempts"):
            # Trigger logged before a timeout/crash or before reserving a call.
            passed, state = False, "observed"
        else:
            passed = task.get("first_output_passed") is True
            if attempts and attempts[0].get("status") != "succeeded":
                passed = False
            state = "observed"
        if passed is None:
            missing_tasks.append(task_id)
        known_passes += passed is True
        role = resource_role(attempts[0]) if attempts else ("Revision" if ".v2" in task_id else (task or {}).get("role","unknown"))
        logical_rows.append(dict(logical_task_id=task_id,role=role,first_output_passed=passed,state=state,
            actual_attempt_count=len(attempts),attempt_ids=[a["attempt_id"] for a in attempts]))
    first_rate = ratio(known_passes,len(logical_rows),state="missing" if missing_tasks else None,
        reason="logical task collection missing" if missing_tasks else None)
    expected = [h for h in handoffs.values() if h.get("expected")]
    # S2 calls unexecuted required edges 'missing', but a durable failure reason
    # proves an unsuccessful handoff (not missing collection). Preserve raw status.
    for handoff in handoffs.values():
        handoff["metric_status"] = "failed" if handoff.get("status") == "missing" and handoff.get("failure_reason") in (
            "failed","timeout","cancelled","budget_exhausted") else handoff.get("status")
    handoff_missing = [h["handoff_id"] for h in expected if h.get("metric_status") in ("missing","pending")]
    successes = 0
    for handoff in expected:
        ref = handoff.get("received_artifact_ref") or {}
        correct = (ref.get("artifact_id"),ref.get("artifact_version"),ref.get("sha256")) == (
            handoff.get("required_artifact_id"),handoff.get("required_artifact_version"),handoff.get("required_artifact_hash"))
        successes += handoff.get("status") == "succeeded" and handoff.get("within_budget") is True and correct
    handoff_rate = ratio(successes,len(expected),state="not_applicable" if condition == "A" else (
        "missing" if not expected or handoff_missing else None), reason="single agent" if condition == "A" else (
        "expected handoff inventory/completion log missing" if not expected or handoff_missing else None))
    counts = token_counts(call_list)
    review_calls = [c for c in call_list if resource_role(c).lower().endswith("critic") or resource_role(c).lower() == "supervisor"]
    review_tokens = token_counts(review_calls)["total_tokens"]
    share = ratio(review_tokens,counts["total_tokens"],state="not_applicable" if condition == "A" else (
        "missing" if counts["total_tokens"] is None or review_tokens is None else None),
        reason="single agent" if condition == "A" else "provider usage incomplete" if counts["usage_incomplete"] else None)
    role_rows = []
    for role in dict.fromkeys((*ROLES,*(resource_role(c) for c in call_list),*(t["role"] for t in logical_rows))):
        rcalls = [c for c in call_list if resource_role(c) == role]
        rtasks = [t for t in logical_rows if t["role"] == role]
        role_rows.append(dict(role=role,applicability="applicable" if rcalls or rtasks else "not_applicable",
            first_contract=ratio(sum(t["first_output_passed"] is True for t in rtasks),len(rtasks),
                state="missing" if any(t["state"] == "missing" for t in rtasks) else None),**token_counts(rcalls)))
    peaks = {}
    for name,keys,fn in (
        ("peak_ram_bytes",("ram_total_bytes","ram_available_bytes"),lambda s:s["ram_total_bytes"]-s["ram_available_bytes"]),
        ("peak_vram_bytes",("gpu_used_bytes",),lambda s:s["gpu_used_bytes"]),
        ("peak_pagefile_bytes",("pagefile_used_bytes",),lambda s:s["pagefile_used_bytes"])):
        values = [fn(s) for s in samples if all(s.get(k) is not None for k in keys)]
        peaks[name] = max(values) if values else None
        peaks[name+"_state"] = "observed" if values and len(values)==len(samples) and not torn else "missing" if not values else "partial"
    completed = bool(result and result.get("status") == "completed" and result.get("terminal_contract_passed") and not resource_failure)
    if result and first_valid is None:
        first_valid = result.get("first_valid_plan_seconds")
    return dict(condition=condition,result=result,config=config,events=events,attempts=call_list,
        artifacts=artifacts,logical_tasks=logical_rows,roles=role_rows,handoffs=list(handoffs.values()),
        routes=routes,nodes=nodes,gates=list(gates.values()),branches=branches,
        unresolved_branches=[k for k,v in branches.items() if v == "unknown"],
        first_contract=first_rate,handoff=handoff_rate,review_token_share=share,**counts,**peaks,
        completed=completed,resource_failure=resource_failure,first_valid_plan_seconds=first_valid if completed else None,
        first_valid_plan_state="observed" if completed and first_valid is not None else "missing" if completed else "not_completed",
        observed_first_complete_contract_seconds=first_valid,
        telemetry_samples=len(samples),unclosed_attempts=unclosed,journal_truncated=torn,
        event_sha256=file_hash(directory/"events.jsonl") if (directory/"events.jsonl").exists() else None)
