"""Read-only S5 admission diagnostics and immutable working-tree snapshots.

This module never constructs a provider, freezes a configuration or grants approval.
"""
from __future__ import annotations

import importlib.metadata as metadata
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from evaluation.s4_io import contained, file_hash, read_json, write_json
from evaluation.s4_runner import (ROOT, AUTHORITY_ROOT, AUTHORITY_NAMES, CASE_IDS,
                                  check_freeze, code_inventory, load_plan, status)


def dependency_check(root=ROOT):
    """Inspect installed distributions; no import of model clients or network probe."""
    from packaging.requirements import Requirement
    from dotenv import dotenv_values
    root = Path(root)
    requirements = []
    for relative in ("requirements.txt", "slm/requirements-slm.txt"):
        raw = (root / relative).read_bytes()
        encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        for line in raw.decode(encoding).splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            req = Requirement(line)
            if req.marker and not req.marker.evaluate():
                continue
            requirements.append((relative, req))
    # Used by the installed S3/S4 adapters, but absent from the legacy requirements.
    for name in ("tokenizers",):
        requirements.append(("S3/S4 runtime", Requirement(name)))
    rows = []
    for source, req in requirements:
        try:
            version = metadata.version(req.name)
            state = "satisfied" if version in req.specifier else "version_mismatch"
        except metadata.PackageNotFoundError:
            version, state = None, "missing"
        rows.append(dict(requirement=str(req), source=source, installed=version, status=state))
    check = subprocess.run([sys.executable, "-B", "-m", "pip", "check"],
                           capture_output=True, text=True, timeout=45)
    # Do not emit environment values, dotenv content, or a credential hash.
    dotenv = dotenv_values(root / ".env", interpolate=False)
    credential_present = bool(os.environ.get("GEMINI_API_KEY") or dotenv.get("GEMINI_API_KEY"))
    return dict(status="passed" if check.returncode == 0 and all(r["status"] == "satisfied" for r in rows) else "blocked",
        python=dict(executable=sys.executable, version=platform.python_version()), requirements=rows,
        pip_check=dict(exit_code=check.returncode, output=(check.stdout + check.stderr).strip()),
        gemini_credential_present=credential_present, gemini_quota_and_billing="not_checked_offline",
        ollama_executable=shutil.which("ollama"), ollama_model_and_service="not_probed",
        model_calls=0, dependency_mutations=0)


def validate_inputs(experiment, *, root=ROOT):
    """Reuse S1 input validators and S4 gates; distinguish damage from pending approval."""
    from workflow.contract_context import ContractContext
    from evaluation.s4_statistics import WEIGHTS, COMPARISONS
    errors, cases = [], []
    plan = load_plan(experiment)
    if plan["kind"] not in ("formal_plan", "synthetic_rehearsal"):
        errors.append("unknown experiment kind")
    if any(type(r.get("canonical")) is not bool or r["canonical"] != (plan["kind"] == "formal_plan") for r in plan["rows"]):
        errors.append("canonical/synthetic row identity mismatch")
    case_root = Path(plan["case_root"])
    protocol = read_json(case_root / "protocol.json")
    if (protocol.get("case_ids") != list(CASE_IDS) or protocol.get("condition_order") != list("ABCD") or
        protocol.get("planned_runs") != 8 or protocol.get("independent_cases") != 2 or
        protocol.get("academic_weights") != list(WEIGHTS) or protocol.get("comparisons") != [list(c) for c in COMPARISONS]):
        errors.append("protocol scope/weights differ from authoritative comparison")
    if file_hash(case_root / "protocol.json") != plan["protocol_sha256"]:
        errors.append("protocol hash changed")
    for case_id in CASE_IDS:
        try:
            contexts = [ContractContext.from_case(case_root, case_id, condition=a) for a in "ABCD"]
            pair = (contexts[0].brief_sha256, contexts[0].packet_sha256)
            if any((c.brief_sha256, c.packet_sha256) != pair for c in contexts):
                raise ValueError("A-D inputs differ")
            if any((r["brief_sha256"], r["packet_sha256"]) != pair for r in plan["rows"] if r["case_id"] == case_id):
                raise ValueError("planned brief/packet hash differs from current input")
            case = read_json(case_root / "cases" / case_id / "case.json")
            cases.append(dict(case_id=case_id, integrity="passed", brief_sha256=pair[0], packet_sha256=pair[1],
                review_status=case["review_status"], approval_record_present=bool(case.get("approval_record")),
                evidence_review_status=contexts[0].packet.review_status))
        except (ValueError, OSError, KeyError) as exc:
            errors.append(f"{case_id}: {exc}")
    try:
        gate = check_freeze(experiment, root=root)
    except (ValueError, OSError, KeyError, TypeError, metadata.PackageNotFoundError) as exc:
        gate = dict(ready=False, blockers=[f"freeze validation unavailable: {exc}"])
    state = status(experiment)
    if state["journal_truncated"] or state["lock_present"] or any(r["execution"] in ("running", "interrupted_unknown") for r in state["rows"]):
        errors.append("active/uncertain experiment; reconcile before export or admission")
    return dict(valid=not errors, errors=errors, cases=cases, formal_gate=gate,
        formal_execution_authorized_by_this_command=False, model_calls=0)


def tree_inventory(root):
    root = Path(root)
    return {p.relative_to(root).as_posix(): file_hash(p) for p in sorted(root.rglob("*")) if p.is_file()}


def source_inventory(root):
    """S4 inventory plus tests and build/config inputs omitted by its runtime filter."""
    root = Path(root)
    files = set(code_inventory(root))
    for folder in ("agents", "evaluation", "prompts", "rag", "schemas", "slm", "storage", "tools", "workflow", "tests"):
        for p in (root / folder).rglob("*"):
            if not p.is_file() or any(x in p.parts for x in ("__pycache__", ".pytest_cache")):
                continue
            if p.suffix in (".py", ".ps1", ".json", ".md", ".yaml", ".yml", ".toml", ".ini") or p.name.startswith(("requirements", "Modelfile")):
                files.add(p.relative_to(root).as_posix())
    files.update(p.name for p in root.iterdir() if p.is_file() and
                 (p.suffix in (".py", ".toml", ".ini", ".yaml", ".yml") or p.name.startswith("requirements")))
    # Environment and credential files are deliberately excluded, even if added to a runtime inventory.
    return {r: file_hash(contained(root, r)) for r in sorted(files) if not any(part.startswith(".env") for part in Path(r).parts)}


def _git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=15)
    return dict(exit_code=result.returncode, output=result.stdout.strip())


def capture_reproduction(experiment, output, *, root=ROOT):
    root, experiment, output = Path(root).resolve(), Path(experiment).resolve(), Path(output).resolve()
    if output.is_relative_to(experiment):
        raise ValueError("snapshot must be outside the experiment")
    plan = load_plan(experiment)
    inputs = validate_inputs(experiment, root=root)
    if not inputs["valid"]:
        raise ValueError("invalid input: " + "; ".join(inputs["errors"]))
    case_root = Path(plan["case_root"])
    sources = source_inventory(root)
    mapping = {"source/" + r: contained(root, r) for r in sources}
    for relative in tree_inventory(case_root):
        mapping["inputs/" + relative] = contained(case_root, relative)
    for name in AUTHORITY_NAMES:
        mapping["authority/" + name] = AUTHORITY_ROOT / name
    for name in ("plan.json", "freeze.json", "schedule.jsonl", "manifest.csv"):
        if (experiment / name).exists():
            mapping["experiment/" + name] = experiment / name
    # Capture explicit preflight evidence references without querying a model or server.
    freeze = read_json(experiment / "freeze.json")
    for arm, ref in freeze.get("preflight_reports", {}).items():
        if arm not in "ABCD" or len(arm) != 1:
            raise ValueError("unknown preflight reference")
        path = Path(ref["path"])
        if file_hash(path) != ref["sha256"]:
            raise ValueError("preflight evidence hash changed")
        mapping[f"preflight/{arm}/{path.name}"] = path
    initial = {r: file_hash(p) for r, p in mapping.items()}
    output.mkdir(parents=True, exist_ok=False)
    for relative, source in mapping.items():
        destination = contained(output, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(source.read_bytes())
    if (initial != {r: file_hash(p) for r, p in mapping.items()} or
        initial != tree_inventory(output) or sources != source_inventory(root)):
        write_json(output / "CAPTURE_FAILED.json", {"reason": "files changed during capture; preserve partial snapshot, retry in new directory"})
        raise ValueError("concurrent changes during capture; snapshot not valid")
    report = dict(version="s5-reproduction-v1", state="frozen_configuration_captured" if inputs["formal_gate"]["ready"] else "preparation_only_not_frozen",
        root=str(root), experiment=str(experiment), kind=plan["kind"], randomization_seed=plan["randomization_seed"],
        git_head=_git(root, "rev-parse", "HEAD"), git_status=_git(root, "status", "--porcelain=v1", "--untracked-files=all"),
        runtime=dependency_check(root), inputs=inputs, source_files=sources, files=initial,
        model_metadata=freeze.get("model_metadata", {}), frozen_configs=freeze.get("configs", {}),
        model_metadata_state="see captured preflight and freeze; no live model probe", model_calls=0,
        excludes=["credentials and .env", "virtualenv binaries", "historical run bulk data (preserved at original path)"],
        commands={"check": f"{root / '.venv/Scripts/python.exe'} -B -m evaluation.s5 check-inputs --experiment \"{experiment}\"",
                  "future_execution_requires_explicit_user_start": f"{root / '.venv/Scripts/python.exe'} -B -m evaluation.s4 execute --experiment \"{experiment}\""})
    write_json(output / "reproducibility.json", report)
    (output / "11_reproducibility_manifest.md").write_text(
        "# S5 reproducibility capture\n\n" + report["state"] + "\n\n"
        "Actual source bytes include uncommitted changes, tests, Modelfile, prompts, schemas, and config files. "
        "The JSON manifest records hashes, Git status, runtime, inputs and pending gates. "
        "This command grants no budget, input approval, configuration freeze or execution authorization.\n\n"
        "Verify: python -B -m evaluation.s5 verify-snapshot --snapshot <this directory>\n",
        encoding="utf-8")
    return dict(status=report["state"], files=len(initial), snapshot=str(output), model_calls=0)


def verify_snapshot(snapshot):
    snapshot = Path(snapshot)
    manifest = read_json(snapshot / "reproducibility.json")
    actual = tree_inventory(snapshot)
    for name in ("reproducibility.json", "11_reproducibility_manifest.md"):
        actual.pop(name, None)
    errors = []
    if actual != manifest["files"]:
        errors.append("snapshot file inventory/hash mismatch")
    for name in manifest["files"]:
        contained(snapshot, name)
    return dict(valid=not errors, errors=errors, state=manifest["state"], model_calls=0)
