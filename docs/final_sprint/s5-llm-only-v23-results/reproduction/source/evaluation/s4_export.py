"""Recomputable raw-event -> CSV -> paired table -> Altair figure pipeline."""
from __future__ import annotations

from pathlib import Path

from evaluation.s4_io import contained,file_hash,read_csv,read_json,write_csv,write_json
from evaluation.s4_runner import status
from evaluation.s4_metrics import reduce_run,ratio
from evaluation.s4_statistics import paired,condition_summary,metric_observed

METRICS = {"completion":"higher","mvp30_material":"higher","valid_plan60":"higher",
    "first_mvp30_material_seconds":"lower","first_contract":"higher","handoff":"higher",
    "review_token_share":"descriptive","first_valid_plan_seconds":"lower",
    "request_count":"lower","total_tokens":"lower","transport_retry_count":"lower",
    "peak_ram_bytes":"lower","peak_vram_bytes":"lower","peak_pagefile_bytes":"lower",
    "academic_quality":"higher","claim_grounding":"higher","assumption_transparency":"higher",
    "high_impact_unsupported":"lower"}


def metric_rows(experiment, *, human=None):
    experiment = Path(experiment)
    rows,roles,attempts,tasks,handoffs,traces,nodes,inputs = [],[],[],[],[],[],[],[]
    snapshot = status(experiment)
    for slot in snapshot["rows"]:
        row = dict(slot)
        row.update(academic_quality=None,academic_quality_state="pending_human_review" if slot["scorable_output"]=="available" else "no_scorable_output")
        for name in ("claim_grounding","assumption_transparency","high_impact_unsupported"):
            row.update({name:None,name+"_state":row["academic_quality_state"],name+"_numerator":None,name+"_denominator":None})
        if slot["run_path"]:
            reduced = reduce_run(contained(experiment,slot["run_path"]),condition=slot["condition"])
            if slot["execution"]=="succeeded" and not reduced["completed"]:
                raise ValueError("successful manifest slot lacks a consistent durable completion")
            for field in ("request_count","prompt_tokens","output_tokens","total_tokens","visible_output_tokens",
                          "thinking_tokens","thinking_tokens_known","thinking_status","transport_retry_count",
                          "structure_repair_count","semantic_revision_request_count","usage_missing_calls",
                          "first_valid_plan_seconds","first_valid_plan_state","observed_first_complete_contract_seconds",
                          "first_mvp30_material_seconds","first_mvp30_material_state","artifact_class",
                          "deterministic_mechanical_repair_count",
                          "peak_ram_bytes","peak_vram_bytes","peak_pagefile_bytes","peak_ram_bytes_state",
                          "peak_vram_bytes_state","peak_pagefile_bytes_state","telemetry_samples","event_sha256"):
                row[field] = reduced[field]
            row["first_valid_plan_seconds_state"] = reduced["first_valid_plan_state"]
            row["first_mvp30_material_seconds_state"] = reduced["first_mvp30_material_state"]
            row.update(mvp30_material=int(reduced["mvp30_material_reached"]),
                mvp30_material_state="observed", mvp30_material_numerator=int(reduced["mvp30_material_reached"]),
                mvp30_material_denominator=1, valid_plan60=int(reduced["valid_plan60_reached"]),
                valid_plan60_state="observed", valid_plan60_numerator=int(reduced["valid_plan60_reached"]),
                valid_plan60_denominator=1)
            for name in ("request_count","transport_retry_count"):
                row[name+"_state"] = "observed" if reduced["events"] else "missing"
                if not reduced["events"]:
                    row[name] = None
            row["total_tokens_state"] = "missing" if reduced["usage_incomplete"] or not reduced["events"] else "observed"
            if not reduced["events"]:
                row["total_tokens"] = None
            for name in ("first_contract","handoff","review_token_share"):
                metric = reduced[name]
                row.update({name:metric["value"],name+"_numerator":metric["numerator"],name+"_denominator":metric["denominator"],
                    name+"_state":metric["state"],name+"_reason":metric["reason"]})
            for name,target in (("roles",roles),("attempts",attempts),("logical_tasks",tasks),("handoffs",handoffs),("routes",traces),("nodes",nodes)):
                target.extend(dict(planned_id=slot["planned_id"],case_id=slot["case_id"],condition=slot["condition"],
                    **{k:v for k,v in item.items() if k not in ("planned_id","case_id","condition")}) for item in reduced[name])
            inputs.append(dict(planned_id=slot["planned_id"],path=slot["run_path"]+"/events.jsonl",sha256=reduced["event_sha256"]))
        else:
            for name in METRICS:
                row.setdefault(name,None)
                row.setdefault(name+"_state","not_run")
            # There were no calls; zero is explicitly known here, not imputed usage.
            row.update(request_count=0,total_tokens=0,transport_retry_count=0)
        row.update(completion=int(slot["execution"] == "succeeded"),completion_state="observed",
            completion_numerator=int(slot["execution"] == "succeeded"),completion_denominator=1)
        if human and slot["planned_id"] in human:
            review = human[slot["planned_id"]]
            row.update(academic_quality=review["academic_quality"],academic_quality_state=review["academic_quality_state"])
            for name,value in review["claims"].items():
                row.update({name:value["value"],name+"_numerator":value["numerator"],name+"_denominator":value["denominator"],name+"_state":value["state"]})
        rows.append(row)
    return dict(rows=rows,roles=roles,attempts=attempts,tasks=tasks,handoffs=handoffs,routes=traces,nodes=nodes,inputs=inputs,kind=snapshot["kind"])


def write_figures(rows, details, output, *, synthetic=False, roles=()):
    """Use existing Altair. Vega-Lite JSON is offline and renders in Streamlit.

    HTML previews use the renderer CDN when opened standalone; no network is used
    when generating or validating these specifications. No chart of unfilled Q.
    """
    import altair as alt
    output.mkdir()
    index=[]
    label = "SYNTHETIC ENGINEERING DATA — " if synthetic else ""
    for metric in METRICS:
        values=[dict(case_id=r["case_id"],condition=r["condition"],value=r[metric]) for r in rows if metric_observed(r,metric)]
        if not values:
            continue
        chart=alt.Chart(alt.Data(values=values)).mark_point(filled=True,size=90).encode(
            x=alt.X("condition:N",sort=list("ABCD"),title="Condition"),y=alt.Y("value:Q",title=metric,scale=alt.Scale(zero=False)),
            color=alt.Color("case_id:N",title="Case"),shape="case_id:N",tooltip=["case_id:N","condition:N","value:Q"]
        ).properties(width=360,height=250,title=label+metric)
        chart.save(str(output/f"{metric}.vl.json"))
        chart.save(str(output/f"{metric}.html"))
        diffs=[dict(case_id=r["case_id"],comparison=r["comparison"],difference=r["difference"]) for r in details if r["metric"]==metric and r["difference"] is not None]
        if diffs:
            delta=alt.Chart(alt.Data(values=diffs)).mark_point(filled=True,size=90).encode(
                x=alt.X("comparison:N",sort=["B-A","C-B","C-D"]),y="difference:Q",color="case_id:N",shape="case_id:N",
                tooltip=["case_id:N","comparison:N","difference:Q"]).properties(width=360,height=250,title=label+metric+" paired differences")
            zero=alt.Chart(alt.Data(values=[{"zero":0}])).mark_rule(color="gray").encode(y="zero:Q")
            (delta+zero).save(str(output/f"{metric}_paired.vl.json"))
        index.append(dict(metric=metric,observed_values=len(values),spec=f"{metric}.vl.json",standalone_preview=f"{metric}.html"))
    for metric in ("request_count","total_tokens","first_contract"):
        values=[]
        for row in roles:
            value=row.get(metric)
            if isinstance(value,dict):value=value["value"]
            if value is not None and row["applicability"]=="applicable":
                values.append(dict(case_id=row["case_id"],condition=row["condition"],role=row["role"],value=value))
        if values:
            chart=alt.Chart(alt.Data(values=values)).mark_point(filled=True).encode(
                x="role:N",y=alt.Y("value:Q",title=metric),color="condition:N",shape="case_id:N",
                tooltip=["case_id:N","condition:N","role:N","value:Q"]).properties(width=620,height=260,title=label+"Role "+metric)
            chart.save(str(output/f"role_{metric}.vl.json"))
            index.append(dict(metric="role_"+metric,observed_values=len(values),spec=f"role_{metric}.vl.json"))
    for resource in ("total_tokens","first_valid_plan_seconds","peak_ram_bytes"):
        values=[dict(case_id=r["case_id"],condition=r["condition"],quality=r["academic_quality"],resource=r[resource])
            for r in rows if metric_observed(r,"academic_quality") and metric_observed(r,resource)]
        if values:
            chart=alt.Chart(alt.Data(values=values)).mark_point(filled=True,size=90).encode(
                x=alt.X("resource:Q",title=resource),y=alt.Y("quality:Q",title="Academic Quality",scale=alt.Scale(domain=[0,100])),
                color="condition:N",shape="case_id:N",tooltip=["case_id:N","condition:N","quality:Q","resource:Q"]
            ).properties(width=400,height=280,title=label+"Quality and "+resource)
            chart.save(str(output/f"quality_vs_{resource}.vl.json"))
            index.append(dict(metric="quality_vs_"+resource,observed_values=len(values),spec=f"quality_vs_{resource}.vl.json"))
    write_json(output/"index.json",index)
    return index


def export_experiment(experiment,output,*,human_pack=None,figures=True):
    experiment,output=Path(experiment),Path(output)
    freeze = read_json(experiment/"freeze.json")
    llm_only = freeze.get("execution_branch") == "llm_only_after_D_no_go"
    comparisons = (("B","A"),("C","B")) if llm_only else None
    human,consistency=None,[]
    if human_pack:
        from evaluation.s4_blind import import_human
        slots={r["planned_id"]:r for r in status(experiment)["rows"]}
        for item in read_csv(Path(human_pack)/"private/identity_mapping.csv"):
            slot=slots.get(item["planned_id"])
            if not slot or slot["run_id"]!=item["run_id"] or slot["condition"]!=item["condition"] or slot["case_id"]!=item["case_id"]:
                raise ValueError("human packet belongs to different canonical outputs")
            if file_hash(contained(experiment,slot["run_path"])/"events.jsonl")!=item["source_event_sha256"]:
                raise ValueError("human packet source events changed")
        human,consistency=import_human(human_pack)
    data=metric_rows(experiment,human=human)
    output.mkdir(parents=True,exist_ok=False)
    for key,filename in (("rows","run_metrics.csv"),("roles","role_metrics.csv"),("attempts","attempts.csv"),
                         ("tasks","logical_tasks.csv"),("handoffs","handoffs.csv"),("routes","route_trace.csv"),("nodes","nodes.csv")):
        write_csv(output/filename,data[key],None if data[key] else ["planned_id"])
    details,summaries=[],[]
    for name,direction in METRICS.items():
        kwargs = {} if comparisons is None else {"comparisons": comparisons}
        d,s=paired(data["rows"],name,direction=direction,**kwargs)
        details.extend(d)
        summaries.extend(s)
    write_csv(output/"paired_cases.csv",details)
    write_csv(output/"paired_summary.csv",summaries)
    write_csv(output/"condition_summary.csv",condition_summary(data["rows"],METRICS))
    unavailable = ([dict(comparison="C-D", status="unavailable", reason="D_preflight_no_go",
        success_subset_substitution=False, planned_D_rows=2,
        D_row_state="not_run_preflight_no_go")] if llm_only else [])
    write_csv(output/"unavailable_comparisons.csv", unavailable,
        ["comparison","status","reason","success_subset_substitution","planned_D_rows","D_row_state"])
    write_csv(output/"hidden_repeat_consistency.csv",consistency,["anonymous_id","canonical_anonymous_id","absolute_score_difference","status","interpretation"])
    write_csv(output/"failure_analysis.csv",[r for r in data["rows"] if r["execution"] != "succeeded"],
        None if any(r["execution"] != "succeeded" for r in data["rows"]) else ["planned_id","execution","failure_reason"])
    chart_index=write_figures(data["rows"],details,output/"figures",synthetic=data["kind"]=="synthetic_rehearsal",roles=data["roles"]) if figures else []
    report=["# "+("SYNTHETIC engineering rehearsal" if data["kind"]=="synthetic_rehearsal" else "Planned experiment status"),
        "Independent unit: case_id; n=2. These tables preserve all eight planned slots and failure/missing states.",
        "Quality and claim results require human review. Empty values are not zero. Synthetic runs cannot support scientific conclusions.",
        "| Metric | Comparison | Pairs | Mean difference | Median | IQR | Improved / tied / worsened |",
        "|---|---|---:|---:|---:|---:|---|"]
    if llm_only:
        report.insert(2, "Approved LLM-only branch: report B−A and C−B only. C−D is unavailable because both D rows are fixed as not_run_preflight_no_go; no successful subset or imputation is substituted.")
    def show(value):return "missing" if value is None else str(round(value,6)) if isinstance(value,float) else str(value)
    for row in summaries:
        report.append("| "+" | ".join(show(row[k]) for k in ("metric","comparison","complete_pairs","mean_difference","median_difference","difference_iqr"))+f" | {show(row['improved'])} / {show(row['tied'])} / {show(row['worsened'])} |")
    report.extend(["", "Proportions are computed within case first, then equal-weighted. Review-token share has no improvement direction.",
        "Memory is local host sampled usage (cloud hardware unavailable); partial telemetry is marked. Provider totals include returned thinking; visible output is separate.",
        "Vega-Lite specifications are offline artifacts for Streamlit. Standalone HTML previews require access to the renderer CDN."])
    (output/"results_tables.md").write_text("\n\n".join(report)+"\n",encoding="utf-8")
    audit=dict(version="s4-export-v1",kind=data["kind"],planned_rows=len(data["rows"]),inputs=data["inputs"],
        plan_sha256=file_hash(experiment/"plan.json"),schedule_sha256=file_hash(experiment/"schedule.jsonl") if (experiment/"schedule.jsonl").exists() else None,
        human_source=str(Path(human_pack).resolve()) if human_pack else None,
        human_files={p.relative_to(human_pack).as_posix():file_hash(p) for p in Path(human_pack).rglob("*.csv")} if human_pack else {},
        figure_count=len(chart_index),quality_results_available=sum(r["academic_quality"] is not None for r in data["rows"]),
        comparison_policy=freeze.get("comparison_policy"), unavailable_comparisons=unavailable,
        outputs={p.relative_to(output).as_posix():file_hash(p) for p in output.rglob("*") if p.is_file()})
    write_json(output/"provenance.json",audit)
    return audit
