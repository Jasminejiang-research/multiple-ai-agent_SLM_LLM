"""S4 offline integration and adversarial recovery; no real model calls."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from evaluation.s4 import main
from evaluation.s4_io import append_event,read_json,read_csv,write_csv,write_json
from evaluation.s4_runner import create_experiment,execute,status,reconcile,check_freeze,resolve_unknown
from evaluation.s4_metrics import reduce_run,token_counts,ratio
from evaluation.s4_statistics import academic_score,paired,condition_summary
from evaluation.s4_blind import build_blind_pack,import_human,claim_metrics,candidate_claims,scrub_text,release_gold
from evaluation.s4_export import export_experiment
from workflow.review_events import EventJournal
from tests.test_s2_review import setup_run


@pytest.fixture(scope="module")
def rehearsal(tmp_path_factory):
    path=tmp_path_factory.mktemp("s4")/"rehearsal"
    create_experiment(path,synthetic=True)
    execute(path,synthetic=True)
    return path


def test_dry_run_exact_slots_no_calls_and_guard(tmp_path,monkeypatch):
    def forbidden(*a,**kw):raise AssertionError("real model construction")
    monkeypatch.setattr("workflow.review_providers.GeminiPhysicalProvider",forbidden)
    path=tmp_path/"dry"
    plan=create_experiment(path)
    assert len(plan["rows"])==8
    assert {r["case_id"] for r in plan["rows"]}=={"ai_education","intelligent_ring"}
    assert all(r["execution"]=="not_run" for r in status(path)["rows"])
    assert status(path)["formal_runs_started"]==0
    assert not check_freeze(path)["ready"]
    with pytest.raises(ValueError,match="freeze"):
        execute(path)
    assert not (path/"schedule.jsonl").exists()
    other=create_experiment(tmp_path/"dry2")
    assert plan["rows"]==other["rows"]
    with pytest.raises(FileExistsError):create_experiment(path)


def test_rehearsal_pass_revision_routes_and_no_rerun(rehearsal):
    before=(rehearsal/"schedule.jsonl").read_bytes()
    output=execute(rehearsal,synthetic=True)
    assert output["formal_runs_started"]==0
    assert sum(r["execution"]=="succeeded" for r in output["rows"])==8
    assert (rehearsal/"schedule.jsonl").read_bytes()==before
    assert sum(r["needs_human_review"] for r in output["rows"])==3
    for row in output["rows"]:
        m=reduce_run(rehearsal/row["run_path"],condition=row["condition"])
        assert m["first_contract"]["value"]==1
        assert m["handoff"]["state"]==("not_applicable" if row["condition"]=="A" else "observed")
        if row["condition"] != "A":assert m["handoff"]["value"]==1
        assert m["total_tokens"]==m["request_count"]*15
        assert m["peak_vram_bytes"]==0
        assert m["first_valid_plan_seconds"]>=0
        assert next(r for r in m["roles"] if r["role"]=="Supervisor")["applicability"]=="not_applicable"
        if row["case_id"]=="intelligent_ring" and row["condition"]!="A":
            assert all(g["revision_count"]==1 for g in m["gates"])
            assert m["semantic_revision_request_count"]>0


def test_interrupted_dispatch_never_retried(tmp_path):
    path=tmp_path/"interrupted"
    create_experiment(path,synthetic=True)
    calls=[]
    def interrupted(plan,row,run_id,run_dir,permit):
        calls.append(run_id)
        raise RuntimeError("uncertain dispatched call")
    with pytest.raises(RuntimeError):execute(path,synthetic=True,executor=interrupted)
    assert status(path)["rows"][0]["execution"]=="running"
    result=reconcile(path)
    assert result["rows"][0]["execution"]=="interrupted_unknown"
    with pytest.raises(ValueError,match="reconciliation"):
        execute(path,synthetic=True,executor=interrupted)
    resolve_unknown(path,result["rows"][0]["planned_id"],"Operator confirmed server stopped; failed canonical run remains failed.")
    assert status(path)["rows"][0]["execution"]=="failed"
    assert len(calls)==1


def test_reconcile_durable_result_without_replaying(tmp_path):
    from evaluation.s4_runner import synthetic_executor
    path=tmp_path/"crash_after_result"
    create_experiment(path,synthetic=True)
    def crash(*args):
        synthetic_executor(*args)
        raise RuntimeError("crash before manifest projection")
    with pytest.raises(RuntimeError):execute(path,synthetic=True,executor=crash)
    assert reconcile(path)["rows"][0]["execution"]=="succeeded"
    execute(path,synthetic=True,max_runs=1)
    assert sum(r["execution"]=="succeeded" for r in status(path)["rows"])==2


def test_torn_schedule_archived_and_active_lock_not_removed(tmp_path):
    path=tmp_path/"torn"
    create_experiment(path,synthetic=True)
    original=append_event(path/"schedule.jsonl",dict(kind="stop",reason="synthetic test checkpoint"))
    with (path/"schedule.jsonl").open("a") as stream:stream.write('{"event_id":')
    assert reconcile(path)["journal_truncated"] is False
    assert len(list(path.glob("schedule.torn.*.jsonl")))==1
    assert json.loads((path/"schedule.jsonl").read_text().splitlines()[0])==original
    import os
    write_json(path/"runner.lock",dict(pid=os.getpid()))
    with pytest.raises(ValueError,match="still exists"):
        reconcile(path,recover_dead_lock=True)
    assert (path/"runner.lock").exists()


def test_usage_thinking_is_not_double_counted():
    calls=[dict(provider="gemini",prompt_tokens=10,output_tokens=5,total_tokens=22,
        usage_raw={"prompt_token_count":10,"candidates_token_count":5,"thoughts_token_count":7,"total_token_count":22})]
    m=token_counts(calls)
    assert (m["total_tokens"],m["visible_output_tokens"],m["thinking_tokens"])==(22,5,7)
    calls.append(dict(provider="gemini",prompt_tokens=None,output_tokens=None,total_tokens=None,usage_missing_reason="API failure"))
    m=token_counts(calls)
    assert m["request_count"]==2 and m["total_tokens"] is None and m["total_tokens_known"]==22
    assert m["thinking_tokens"] is None
    assert ratio(0,0)["state"]=="not_applicable"


def test_failure_preserves_denominators_and_no_success_time(tmp_path):
    workflow,provider=setup_run(tmp_path,overrides={"max_requests":1})
    result=workflow.run()
    m=reduce_run(workflow.journal.directory,condition="C")
    assert result["status"]=="budget_exhausted"
    assert m["request_count"]==1
    assert m["first_contract"]["denominator"]==1  # One unfinished two-stage Research; Critic never triggered.
    assert m["first_contract"]["value"]==0  # Body alone is not the first full Research submission.
    assert m["handoff"]["value"]<1
    assert m["handoff"]["denominator"]>1
    assert m["first_valid_plan_seconds"] is None
    assert m["peak_ram_bytes"] is None and m["peak_ram_bytes_state"]=="missing"


def test_missing_log_does_not_infer_first_pass(tmp_path):
    workflow,_=setup_run(tmp_path,condition="A")
    workflow.run()
    path=workflow.journal.path
    records=[json.loads(line) for line in path.read_text().splitlines()]
    records=[e for e in records if e["kind"]!="logical_task"]
    path.write_text("\n".join(json.dumps(e) for e in records)+"\n")
    m=reduce_run(path.parent,condition="A")
    assert m["first_contract"]["state"]=="missing" and m["first_contract"]["value"] is None


def test_duplicate_attempts_idempotent_and_conflicts_rejected(tmp_path):
    workflow,_=setup_run(tmp_path,condition="A")
    workflow.run()
    path=workflow.journal.path
    original=reduce_run(path.parent,condition="A")
    text=path.read_text()
    path.write_text(text+text)
    assert reduce_run(path.parent,condition="A")["request_count"]==8
    terminal=next(e for e in original["events"] if e["kind"]=="call" and e["payload"]["status"]=="succeeded")
    terminal=deepcopy(terminal)
    terminal["event_id"]="conflicting-new-event"
    terminal["payload"]["total_tokens"]+=1
    with path.open("a") as stream:stream.write(json.dumps(terminal)+"\n")
    with pytest.raises(ValueError,match="conflicting terminal"):
        reduce_run(path.parent,condition="A")


def test_blind_pack_no_identity_and_human_defaults(rehearsal,tmp_path):
    path=tmp_path/"blind"
    audit=build_blind_pack(rehearsal,path)
    assert audit["canonical_outputs"]==8 and audit["hidden_repeats"]==2 and audit["rating_copies"]==10
    mapping=read_csv(path/"private/identity_mapping.csv")
    for file in (path/"reviewer").rglob("*"):
        if file.is_file():
            text=file.read_text(encoding="utf-8-sig")
            assert all(m["run_id"] not in text for m in mapping)
            assert "s4-synthetic-only" not in text
    ratings=read_csv(path/"reviewer/ratings.csv")
    assert all(all(r[f"AQ{i}"]=="" for i in range(1,7)) for r in ratings)
    assert not (path/"reviewer/gold_ledger.csv").exists()
    ledger=read_csv(path/"private/gold_ledger_candidates.csv")
    assert all(r["support_verdict"]==r["high_impact"]=="" for r in ledger)
    assert any("content.segment" in r["occurrences"] for r in ledger)
    assert any("financial_values" in r["occurrences"] for r in ledger)
    human,consistency=import_human(path)
    assert all(v["academic_quality"] is None for v in human.values())
    with pytest.raises(ValueError,match="finish all"):
        release_gold(path)
    assert len(consistency)==2


def audited_row(id,text="claim",**kw):
    return dict(candidate_id=id,claim_text=text,decision_critical="yes",atomic_reviewed="yes",duplicate_of="",
        human_claim_type="factual",support_verdict="sufficient",correct_assumption="no",high_impact="yes",
        human_evidence_locations="S1 lines 1-2",rationale="Synthetic test judgment",reviewer="fixture",reviewed_at="fixture",
        model_claim_type="factual",**kw)


def test_gold_three_denominators_partial_and_correct_assumptions():
    coverage=dict(all_sections_and_financial_rows_checked="yes",atomization_and_dedup_complete="yes",ledger_complete="yes",reviewer="fixture",reviewed_at="fixture")
    a=audited_row("c1")
    b=audited_row("c2");b.update(support_verdict="partial_support")
    c=audited_row("c3");c.update(human_claim_type="assumption",model_claim_type="assumption",support_verdict="none",correct_assumption="yes")
    d=audited_row("c4");d.update(duplicate_of="c1")
    m=claim_metrics([a,b,c,d],coverage)
    assert m["claim_grounding"]["value"]==1/3
    assert m["assumption_transparency"]["value"]==1/2
    assert m["high_impact_unsupported"]["value"]==1/2
    b["correct_assumption"]="yes"
    with pytest.raises(ValueError,match="genuine"):
        claim_metrics([a,b,c],coverage)
    assert claim_metrics([a],{})["claim_grounding"]["state"]=="pending_human_review"
    a.update(decision_critical="no")
    assert claim_metrics([a],coverage)["claim_grounding"]["reason"]=="zero_denominator"


def test_statistics_weights_pairs_and_equal_case_ratios():
    assert academic_score([5,4,5,4,5,4])==pytest.approx(88.75)
    assert academic_score([2,2,5,3,1,3])==pytest.approx(38.75)
    rows=[dict(case_id=c,condition=a,q=v,execution="succeeded",q_state="observed") for c,values in
        (("c1",[1,3,4,2]),("c2",[4,3,5,None])) for a,v in zip("ABCD",values)]
    details,s=paired(rows,"q")
    assert s[0]["mean_difference"]==.5
    assert s[0]["median_difference"]==.5 and s[0]["difference_iqr"]==1.5
    assert (s[0]["improved"],s[0]["worsened"],s[2]["complete_pairs"])==(1,1,1)
    rows=[dict(case_id="a",condition="A",r=1/2),dict(case_id="b",condition="A",r=9/10)]
    assert condition_summary(rows,["r"])[0]["mean"]==.7


def test_export_trace_and_no_pseudo_quality(rehearsal,tmp_path):
    from evaluation.s4_export import METRICS
    out=tmp_path/"export"
    audit=export_experiment(rehearsal,out)
    assert audit["planned_rows"]==8 and audit["quality_results_available"]==0
    assert len(read_csv(out/"run_metrics.csv"))==8
    assert len(read_csv(out/"paired_cases.csv"))==6*len(METRICS)
    assert not list((out/"figures").glob("academic_quality*"))
    assert list((out/"figures").glob("total_tokens*.vl.json"))
    spec=read_json(out/"figures/total_tokens.vl.json")
    assert "SYNTHETIC" in spec["title"]
    assert all(i["sha256"] for i in audit["inputs"])


def test_cli_offline(tmp_path):
    path=tmp_path/"cli"
    assert main(["dry-run","--output-dir",str(path)])==0
    assert main(["resume","--experiment",str(path)])==0
    assert main(["check-freeze","--experiment",str(path)])==2
    assert main(["execute","--experiment",str(path)])==2
    assert status(path)["formal_runs_started"]==0


def test_ui_sqlite_new_events_not_collapsed_and_legacy_unchanged():
    from types import SimpleNamespace
    from datetime import datetime
    from app import build_run_detail
    events=[dict(event_version="review-events-v1-s2",kind="gate",payload=dict(role=r,decision="revise_once")) for r in ("research","finance")]
    run=SimpleNamespace(run_id="x",status="completed",input_brief={},workflow_version="multi-agent-review-gates-v2",errors=[],sources=[],
        node_outputs=[SimpleNamespace(id=i,created_at=datetime(2026,1,1),node_name="s2.gate",output_snapshot=e) for i,e in enumerate(events)])
    detail=build_run_detail(run)
    assert {n.step for n in detail.node_outputs}=={"research.gate","finance.gate"}


def test_streamlit_readonly_path(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    path=tmp_path/"ui"
    create_experiment(path)
    app=AppTest.from_string("from evaluation.s4_ui import render_experiment_panel\nimport streamlit as st\nrender_experiment_panel(st)").run()
    app.text_input(key="s4_directory").set_value(str(path)).run()
    assert not app.exception
    assert len(app.dataframe[0].value)==8
    assert not app.button


def test_failed_final_review_keeps_scorable_artifact(tmp_path):
    from workflow.review_runtime import ProviderFailure
    from schemas.review import ComponentCritiqueReport
    def fail_review(request,count):
        if issubclass(request.schema, ComponentCritiqueReport):
            raise ProviderFailure("synthetic_api_failure",request_finished=True)
    workflow,_=setup_run(tmp_path,condition="B",before=fail_review)
    result=workflow.run()
    assert result["status"]=="failed" and result["scorable_artifact_ref"]
    assert result["terminal_contract_passed"] is False
    assert result["terminal_contract_state"]=="not_checked"
    m=reduce_run(workflow.journal.directory,condition="B")
    assert m["observed_first_complete_contract_seconds"] is not None
    assert m["first_valid_plan_seconds"] is None
    from evaluation.s4_blind import final_artifact
    assert final_artifact(m) is not None


def test_terminal_export_failure_is_distinct_from_scorability(tmp_path,monkeypatch):
    workflow,_=setup_run(tmp_path,condition="A")
    def fail_export(*a):raise OSError("synthetic disk full")
    monkeypatch.setattr(workflow.context,"export",fail_export)
    result=workflow.run()
    assert result["scorable_artifact_ref"] is not None
    assert result["terminal_contract_state"]=="failed"
    m=reduce_run(workflow.journal.directory,condition="A")
    assert m["first_contract"]["denominator"]==5 and m["first_contract"]["numerator"]==4
    assert next(r for r in m["roles"] if r["role"]=="export")["first_contract"]["value"]==0


def test_live_lock_and_changed_matrix_block_dispatch(tmp_path):
    from evaluation.s4_runner import runner_lock
    path=tmp_path/"lock"
    create_experiment(path,synthetic=True)
    with runner_lock(path):
        with pytest.raises(FileExistsError):execute(path,synthetic=True)
    plan=read_json(path/"plan.json")
    plan["rows"][0]["condition"]="D"
    write_json(path/"plan.json",plan,replace=True)
    with pytest.raises(ValueError):status(path)


def test_full_rating_import_release_gold_and_no_duplicate_sample(rehearsal,tmp_path):
    path=tmp_path/"rated"
    build_blind_pack(rehearsal,path)
    ratings=read_csv(path/"reviewer/ratings.csv")
    for row in ratings:
        row.update(reviewer="synthetic fixture reviewer",reviewed_at="fixture")
        for i in range(1,7):
            row[f"AQ{i}"]="3"
            row[f"AQ{i}_rationale"]="Synthetic unit test only"
    write_csv(path/"reviewer/ratings.csv",ratings)
    release_gold(path)
    assert len(read_csv(path/"reviewer/coverage.csv"))==8
    human,consistency=import_human(path)
    assert len(human)==8 and len(consistency)==2
    assert all(r["academic_quality"]==50 for r in human.values())
    assert all(r["absolute_score_difference"]==0 for r in consistency)
    assert all(r["claims"]["claim_grounding"]["value"] is None for r in human.values())


def test_blind_identity_removal_and_unknown_claim_detection():
    text="Model: gemini-2.5-flash\nrun_id: sensitive-123\nBusiness content [RING-01]. Generated by sensitive-123."
    cleaned=scrub_text(text,["sensitive-123","gemini-2.5-flash"])
    assert "sensitive-123" not in cleaned and "gemini-2.5-flash" not in cleaned
    assert "Business content [RING-01]" in cleaned
    artifact={"payload":{"problem":{"content":"Hidden unsupported material statement. A separate statement."}}}
    assert any("Hidden unsupported" in row["claim_text"] for row in candidate_claims(artifact,[]))


def test_partial_telemetry_and_revision_resource_attribution(tmp_path):
    workflow,_=setup_run(tmp_path,condition="B",fail_roles=("final",))
    workflow.run()
    for s in (dict(ram_total_bytes=100,ram_available_bytes=30,gpu_used_bytes=5,pagefile_used_bytes=10),
              dict(ram_total_bytes=100,ram_available_bytes=20,gpu_used_bytes=None,pagefile_used_bytes=None)):
        workflow.journal.emit("telemetry",s)
    m=reduce_run(workflow.journal.directory,condition="B")
    assert m["peak_ram_bytes"]==80 and m["peak_ram_bytes_state"]=="observed"
    assert m["peak_vram_bytes"]==5 and m["peak_vram_bytes_state"]=="partial"
    revision=next(r for r in m["roles"] if r["role"]=="Revision")
    assert revision["request_count"]==8
    assert m["review_token_share"]["numerator"]==15


def test_resume_keeps_canonical_failure_immutable(tmp_path):
    path=tmp_path/"failure"
    create_experiment(path,synthetic=True)
    def fail(plan,row,run_id,run_dir,permit):
        return dict(status="failed",terminal_contract_passed=False,scorable_artifact_ref=None,error={"error_type":"FixtureFailure"})
    execute(path,synthetic=True,max_runs=1,executor=fail)
    first=status(path)["rows"][0]
    reconcile(path)
    execute(path,synthetic=True,max_runs=1)
    assert status(path)["rows"][0]==first


def test_actual_streamlit_legacy_and_s4_navigation(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from evaluation.s4_runner import ROOT
    import app as application
    import storage.db as database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    monkeypatch.setattr(database,"engine",engine)
    monkeypatch.setattr(database,"SessionLocal",sessionmaker(bind=engine))
    monkeypatch.setattr(application,"_render_recent_runs_sidebar",lambda st:None)
    app=AppTest.from_file(str(ROOT/"app.py")).run()
    assert not app.exception
    app.radio[0].set_value("S4 Experiment Review").run()
    assert not app.exception
    assert any(b.disabled for b in app.button if b.label=="Generate Proposal")


def test_late_resource_failure_cannot_become_completed(tmp_path):
    path=tmp_path/"resources"
    create_experiment(path,synthetic=True)
    from evaluation.s4_runner import synthetic_executor
    def fail_resource(plan,row,run_id,run_dir,permit):
        result=synthetic_executor(plan,row,run_id,run_dir,permit)
        from workflow.review_events import utc_now
        append_event(run_dir/"events.jsonl",dict(run_id=run_id,kind="resource_stop",event_version="review-events-v1-s2",payload=dict(reason="synthetic_sustained_resource_limit")))
        return result
    output=execute(path,synthetic=True,executor=fail_resource)
    assert output["rows"][0]["execution"]=="failed"
    assert all(r["execution"]=="not_run" for r in output["rows"][1:])
    m=reduce_run(path/output["rows"][0]["run_path"],condition=output["rows"][0]["condition"])
    assert not m["completed"] and m["first_valid_plan_seconds"] is None


def test_per_attempt_diagnostic_keeps_legacy_phase_event_separate(tmp_path):
    from workflow.review_runtime import ProviderFailure
    def fail(request,count):
        provider.last_diagnostic={"http_status":200,"response":{"done":False,"message":{"content":"{\\n"}}}
        raise ProviderFailure("FixturePartialResponse",request_finished=True)
    workflow,provider=setup_run(tmp_path,before=fail)
    workflow.run()
    m=reduce_run(workflow.journal.directory,condition="C")
    diagnostics=[e["payload"] for e in m["events"] if e["kind"]=="physical_provider_diagnostic"]
    assert len(diagnostics)==1
    assert diagnostics[0]["attempt_id"]==m["attempts"][0]["attempt_id"]
    assert diagnostics[0]["diagnostic"]["response"]["done"] is False


def test_streamlit_reviewed_nodes_issues_and_offline_figure(rehearsal,tmp_path):
    from streamlit.testing.v1 import AppTest
    charts=tmp_path/"charts"
    charts.mkdir()
    write_json(charts/"tokens.vl.json",{"$schema":"https://vega.github.io/schema/vega-lite/v6.json",
        "data":{"values":[{"condition":"C","value":15}]},"mark":"point","encoding":{"x":{"field":"condition","type":"nominal"},"y":{"field":"value","type":"quantitative"}}})
    app=AppTest.from_string("from evaluation.s4_ui import render_experiment_panel\nimport streamlit as st\nrender_experiment_panel(st)").run()
    app.text_input(key="s4_directory").set_value(str(rehearsal)).run()
    app.selectbox(key="s4_slot").set_value("intelligent_ring-C").run()
    app.text_input(key="s4_figures").set_value(str(charts)).run()
    assert not app.exception
    assert app.warning
    assert any("research.gate" in expander.label for expander in app.expander)
    assert app.get("vega_lite_chart") or app.get("arrow_vega_lite_chart")


def test_not_run_zero_consumption_and_partial_peaks_are_not_complete_pairs(tmp_path):
    from evaluation.s4_export import metric_rows
    path=tmp_path/"unrun"
    create_experiment(path)
    rows=metric_rows(path)["rows"]
    assert all(r["request_count"]==0 and r["request_count_state"]=="not_run" for r in rows)
    _,summaries=paired(rows,"request_count",direction="lower")
    assert all(s["complete_pairs"]==0 and s["mean_difference"] is None for s in summaries)
    _,completion=paired(rows,"completion")
    assert all(s["complete_pairs"]==2 for s in completion)  # all planned rows remain in completion denominator
    for row in rows:
        row.update(peak_ram_bytes=100,peak_ram_bytes_state="partial")
    assert all(r["valid_cases"]==0 for r in condition_summary(rows,["peak_ram_bytes"]))
