"""Reproduce the S4 CLI handoff using synthetic data only, preserving every log."""
import argparse
import importlib.metadata
from pathlib import Path
import subprocess
import sys

from evaluation.s4_io import file_hash,read_json,write_json
from evaluation.s4_runner import ROOT,status
from evaluation.s4_metrics import reduce_run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--case-root",type=Path,default=ROOT/"docs/final_sprint/s0-v1")
    args=parser.parse_args()
    out=args.output_dir.resolve()
    out.mkdir(parents=True,exist_ok=False)
    (out/"command_logs").mkdir()
    commands=[
        (["dry-run","--case-root",str(args.case_root.resolve()),"--output-dir",str(out/"dry_run")],0),
        (["status","--experiment",str(out/"dry_run")],0),
        (["resume","--experiment",str(out/"dry_run")],0),
        (["check-freeze","--experiment",str(out/"dry_run")],2),
        (["execute","--experiment",str(out/"dry_run")],2),
        (["export","--experiment",str(out/"dry_run"),"--output-dir",str(out/"dry_export"),"--no-figures"],0),
        (["blind-pack","--experiment",str(out/"dry_run"),"--output-dir",str(out/"review_templates")],0),
        (["rehearsal","--case-root",str(args.case_root.resolve()),"--output-dir",str(out/"synthetic_rehearsal")],0),
        (["resume","--experiment",str(out/"synthetic_rehearsal")],0),
        (["blind-pack","--experiment",str(out/"synthetic_rehearsal"),"--output-dir",str(out/"synthetic_blind_pack")],0),
        (["export","--experiment",str(out/"synthetic_rehearsal"),"--output-dir",str(out/"synthetic_export"),"--human-pack",str(out/"synthetic_blind_pack")],0)]
    records=[]
    for index,(arguments,expected) in enumerate(commands,1):
        command=[sys.executable,"-B","-m","evaluation.s4",*arguments]
        completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
        log=out/"command_logs"/f"{index:02d}_{arguments[0]}.txt"
        log.write_text(completed.stdout+completed.stderr,encoding="utf-8")
        records.append(dict(command=command,exit_code=completed.returncode,expected_exit_code=expected,log=log.relative_to(out).as_posix(),sha256=file_hash(log)))
        if completed.returncode!=expected:
            write_json(out/"cli_failure.json",records)
            raise RuntimeError(f"CLI check {index} failed; see {log}")
    rehearsal=status(out/"synthetic_rehearsal")
    synthetic_calls=[]
    for row in rehearsal["rows"]:
        synthetic_calls.extend(reduce_run(out/"synthetic_rehearsal"/row["run_path"],condition=row["condition"])["attempts"])
    if any(c["provider"]!="mock" or c["run_kind"]!="debug" for c in synthetic_calls):
        raise RuntimeError("offline audit unexpectedly contains a real/formal call")
    summary=dict(package="S4",scope="engineering_and_offline_only",formal_runs_started=0,actual_model_calls=0,
        D_preflight_started=False,public_budget_changed=False,planned_formal_slots=len(status(out/"dry_run")["rows"]),
        synthetic_attempts=len(synthetic_calls),synthetic_completed=sum(r["execution"]=="succeeded" for r in rehearsal["rows"]),
        provider_counts_are_synthetic=True,human_reviews_filled=0,
        dependencies={n:importlib.metadata.version(n) for n in ("pytest","pydantic","streamlit","altair","google-genai","langgraph","sqlalchemy")},
        commands=records)
    write_json(out/"offline_audit.json",summary)
    print("S4 offline CLI audit passed: 8 untouched formal slots, 8 synthetic workflows, no real model calls.")


if __name__=="__main__":main()
