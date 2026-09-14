"""S5 preparation and post-run evidence tools. No execution/freeze/provider commands."""
import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("dependencies")
    p = commands.add_parser("check-inputs")
    p.add_argument("--experiment", type=Path, required=True)
    p = commands.add_parser("snapshot")
    p.add_argument("--experiment", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p = commands.add_parser("verify-snapshot")
    p.add_argument("--snapshot", type=Path, required=True)
    for name in ("check-review", "import-review"):
        p = commands.add_parser(name)
        p.add_argument("--experiment", type=Path, required=True)
        p.add_argument("--pack", type=Path, required=True)
        if name == "check-review":
            p.add_argument("--require-complete", choices=("ratings", "gold"))
        else:
            p.add_argument("--output-dir", type=Path, required=True)
            p.add_argument("--ratings", type=Path)
            p.add_argument("--gold-ledger", type=Path)
            p.add_argument("--coverage", type=Path)
    p = commands.add_parser("export")
    p.add_argument("--experiment", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--human-pack", type=Path)
    p.add_argument("--reproduction", type=Path)
    p.add_argument("--allow-synthetic", action="store_true")
    p.add_argument("--no-figures", action="store_true")
    args = parser.parse_args(argv)
    try:
        from evaluation.s5_preparation import dependency_check, validate_inputs, capture_reproduction, verify_snapshot
        code = 0
        if args.command == "dependencies":
            result = dependency_check()
            code = 0 if result["status"] == "passed" else 2
        elif args.command == "check-inputs":
            result = validate_inputs(args.experiment)
            code = 0 if result["valid"] and result["formal_gate"]["ready"] else 2
        elif args.command == "snapshot":
            result = capture_reproduction(args.experiment, args.output_dir)
        elif args.command == "verify-snapshot":
            result = verify_snapshot(args.snapshot)
            code = 0 if result["valid"] else 2
        elif args.command == "check-review":
            from evaluation.s5_review import check_review
            result = check_review(args.experiment, args.pack)
            if args.require_complete and not result[args.require_complete + "_complete"]:
                code = 2
        elif args.command == "import-review":
            from evaluation.s5_review import import_review
            result = import_review(args.experiment, args.pack, args.output_dir, ratings=args.ratings,
                                   gold_ledger=args.gold_ledger, coverage=args.coverage)
        else:
            from evaluation.s5_export import export_bundle
            result = export_bundle(args.experiment, args.output_dir, human_pack=args.human_pack,
                reproduction=args.reproduction, allow_synthetic=args.allow_synthetic, figures=not args.no_figures)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return code
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps(dict(status="blocked", reason=str(exc)), ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
