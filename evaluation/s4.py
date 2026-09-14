"""S4 offline commands and guarded S5 runner. No default model execution."""
import argparse
import json
from pathlib import Path


def main(argv=None):
    from evaluation.s4_runner import ROOT,create_experiment,status,execute,reconcile,check_freeze,resolve_unknown
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest="command",required=True)
    for name in ("dry-run","rehearsal"):
        p=commands.add_parser(name)
        p.add_argument("--output-dir",required=True,type=Path)
        p.add_argument("--case-root",type=Path,default=ROOT/"docs/final_sprint/s0-v1")
        p.add_argument("--seed",type=int,default=20260906)
    for name in ("status","check-freeze","resume","execute","resolve-unknown"):
        p=commands.add_parser(name)
        p.add_argument("--experiment",required=True,type=Path)
        if name == "resume":
            p.add_argument("--recover-dead-lock",action="store_true")
        if name == "execute":
            p.add_argument("--max-runs",type=int,default=8)
        if name == "resolve-unknown":
            p.add_argument("--planned-id",required=True)
            p.add_argument("--note",required=True)
    for name in ("export","blind-pack"):
        p=commands.add_parser(name)
        p.add_argument("--experiment",required=True,type=Path)
        p.add_argument("--output-dir",required=True,type=Path)
        if name == "export":
            p.add_argument("--human-pack",type=Path)
            p.add_argument("--no-figures",action="store_true")
    p=commands.add_parser("gold-phase")
    p.add_argument("--pack",required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        if args.command in ("dry-run","rehearsal"):
            create_experiment(args.output_dir,case_root=args.case_root,seed=args.seed,synthetic=args.command=="rehearsal")
            result=execute(args.output_dir,synthetic=True) if args.command=="rehearsal" else status(args.output_dir)
        elif args.command == "status":result=status(args.experiment)
        elif args.command == "check-freeze":result=check_freeze(args.experiment)
        elif args.command == "resume":result=reconcile(args.experiment,recover_dead_lock=args.recover_dead_lock)
        elif args.command == "execute":result=execute(args.experiment,max_runs=args.max_runs)
        elif args.command == "resolve-unknown":
            resolve_unknown(args.experiment,args.planned_id,args.note)
            result=status(args.experiment)
        elif args.command == "export":
            from evaluation.s4_export import export_experiment
            result=export_experiment(args.experiment,args.output_dir,human_pack=args.human_pack,figures=not args.no_figures)
        elif args.command == "blind-pack":
            from evaluation.s4_blind import build_blind_pack
            result=build_blind_pack(args.experiment,args.output_dir)
        else:
            from evaluation.s4_blind import release_gold
            result=release_gold(args.pack)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if args.command=="check-freeze" and not result["ready"] else 0
    except (ValueError,FileExistsError) as exc:
        print(json.dumps(dict(status="blocked",reason=str(exc)),ensure_ascii=False,indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
