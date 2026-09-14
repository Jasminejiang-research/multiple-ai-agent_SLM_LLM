"""Read-only S4 views embedded in the existing Streamlit app; no provider imports."""
from pathlib import Path

from evaluation.s4_io import contained,read_json
from evaluation.s4_metrics import reduce_run
from evaluation.s4_runner import ROOT,status


def event_step(event):
    kind,body=event.get("kind"),event.get("payload",{})
    if kind == "route":
        return body.get("node","route"),body.get("status","missing"),body
    if kind == "node":
        return body.get("node_scope_id","node")+".scope",body.get("status","missing"),body
    if kind == "artifact":
        return body["artifact_ref"]["artifact_id"],"recorded",body
    if kind == "call":
        return f"{body['task_role']}.attempt.{body['attempt_id']}",body["status"],body
    if kind == "logical_task":
        return body["logical_task_id"],"passed" if body.get("first_output_passed") else "first_failed_or_pending",body
    if kind in ("gate","critique"):
        return f"{body['role']}.{kind}",body.get("decision","recorded"),body
    if kind == "handoff":
        return "handoff."+body["handoff_id"],body["status"],body
    return "review."+str(kind),body.get("status","recorded"),body


def render_experiment_panel(st):
    st.header("Reviewed workflows · A–D")
    st.write("Gemini A: one generation role and a common 13-section contract. Gemini B: final review. Gemini C: Research, Strategy and Finance reviews plus final review. Granite D uses C's complete workflow through the CLI.")
    st.write("Each failed gate can trigger one revision. Passed gates skip revision. Initial, reviewed and effective artifacts remain visible below.")
    st.info("S4 engineering and offline verification. Public budgets and D preflight are deferred. Formal execution: locked (0 runs authorized in S4).")
    default=ROOT/"docs/final_sprint/s4-v1/dry_run"
    path=Path(st.text_input("Experiment directory",value=str(default),key="s4_directory"))
    if not (path/"plan.json").exists():
        st.caption("No experiment manifest at this path. Use the S4 dry-run CLI to create eight planned slots.")
        return
    try:
        snapshot=status(path)
        st.caption("Synthetic engineering rehearsal — no model results" if snapshot["kind"]=="synthetic_rehearsal" else "Formal plan; execution status is recorded per slot")
        st.dataframe([{k:r[k] for k in ("order","case_id","condition","execution","terminal_contract","scorable_output","needs_human_review")} for r in snapshot["rows"]],hide_index=True)
        options=[r["planned_id"] for r in snapshot["rows"]]
        selected=st.selectbox("Planned run",options,key="s4_slot")
        row=next(r for r in snapshot["rows"] if r["planned_id"]==selected)
        if not row["run_path"]:
            st.info("This slot has not run. No output or metrics are imputed.")
            return
        reduced=reduce_run(contained(path,row["run_path"]),condition=row["condition"])
        st.json({k:reduced[k] for k in ("first_contract","handoff","review_token_share","request_count","total_tokens","thinking_tokens","peak_ram_bytes","peak_vram_bytes","peak_pagefile_bytes")})
        st.dataframe(reduced["roles"],hide_index=True)
        result=reduced["result"] or {}
        if result.get("needs_human_review"):
            st.warning("High/critical issues need human review. Structural repair does not verify semantic resolution.")
        st.caption("Internal review artifacts; external readiness has not been approved.")
        st.subheader("Nodes, gates and revisions")
        latest={}
        for event in reduced["events"]:
            step,state,body=event_step(event)
            latest[step]=(state,body)
        for step,(state,body) in latest.items():
            with st.expander(f"{step} · {state}"):
                st.json(body)
        from evaluation.s4_blind import final_artifact,render_output
        artifact=final_artifact(reduced)
        if artifact:
            plan=read_json(path/"plan.json")
            packet=read_json(Path(plan["case_root"])/"cases"/row["case_id"]/"packet.json")
            with st.expander("Final output for internal review",expanded=False):
                st.markdown(render_output(artifact,packet,[]))
        chart_dir=Path(st.text_input("Optional exported figures directory",value=str(path.parent/"synthetic_export_final/figures"),key="s4_figures"))
        specs=sorted(chart_dir.glob("*.vl.json")) if chart_dir.is_dir() else []
        if specs:
            chosen=st.selectbox("Metric figure",[p.name for p in specs],key="s4_figure")
            st.vega_lite_chart(read_json(chart_dir/chosen),use_container_width=True)
    except (ValueError,OSError,KeyError) as exc:
        st.error(f"Experiment record unavailable: {exc}")
