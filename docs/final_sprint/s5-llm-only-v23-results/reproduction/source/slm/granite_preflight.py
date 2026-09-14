"""S3 real-model preflight and complete D smoke, with preserved non-formal evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from threading import Event
import time
from typing import Literal
from uuid import uuid4

from schemas.evidence import StrictModel
from schemas.review import ComponentCritiqueReport
from schemas.workflow import SECTION_FIELD_BY_TITLE
from workflow.contract_context import ContractContext
from workflow.contract_generation import (COMMON_INSTRUCTION, ContractGenerator, PROMPT_VERSION,
                                            build_generation_prompt)
from workflow.generation_batches import CONTRACT_BATCH_MODELS, PROPOSAL_SECTION_BATCHES, build_contract_batch_prompt
from workflow.review_events import EventJournal, replay_events
from workflow.review_runtime import BoundedClient, LocalRequestLease
from workflow.run_budget import RunBudget
from workflow.compact_protocol import SYSTEM_INSTRUCTION as COMPACT_SYSTEM_INSTRUCTION
from schemas.compact_wire import WIRE_VERSION
from agents.component_critic import ComponentCritic
from evaluation.s2_fixtures import synthetic_artifact
from slm.factories import build_slm_review_workflow
from slm.granite_config import GraniteConfig
from slm.granite_provider import GranitePhysicalProvider, inspect_ollama
from slm.resource_monitor import ResourceMonitor, WindowsResourceProbe
from slm.owned_ollama import OwnedOllama
from slm.windows_awake import WindowsAwake


class ProbeAck(StrictModel):
    ok: Literal[True]


def writer_probe_prompt(context, upstream):
    """Same S1 Writer first batch prompt, including the full frozen inputs."""
    payload = context.input_payload("writer", upstream)
    base = build_generation_prompt(payload, "writer", version=1)
    return build_contract_batch_prompt(base, 1, version=1)


def load_context_tokenizer(tokenizer_path, provenance_path):
    provenance = json.loads(Path(provenance_path).read_text(encoding="utf-8-sig"))
    if provenance.get("model") != "ibm-granite/granite-4.0-h-micro":
        raise ValueError("context tokenizer must be the same official H Micro model")
    actual = hashlib.sha256(Path(tokenizer_path).read_bytes()).hexdigest()
    if actual != provenance.get("tokenizer_sha256"):
        raise ValueError("context tokenizer hash changed")
    from tokenizers import Tokenizer
    return Tokenizer.from_file(str(tokenizer_path))


class GranitePreflight:
    def __init__(self, *, config, context, output_dir, owner_path, tokenizer_path, tokenizer_provenance,
                 probe=None, metadata=None, provider_factory=GranitePhysicalProvider, owner_factory=OwnedOllama,
                 awake_factory=None, resume_from=None):
        self.config, self.context = config, context
        self.journal = EventJournal(output_dir, str(uuid4()))
        self.cancel = Event()
        self.phases = {}
        self.prior_attempts = []
        self.resume = None
        self.shared_budget = RunBudget(max_requests=config.max_requests, max_total_tokens=config.max_total_tokens)
        self.shared_started = time.monotonic()
        self.provider_factory = provider_factory
        self.awake_factory = awake_factory or WindowsAwake
        self.owner = None
        try:
            self.owner = owner_factory(owner_path, journal=self.journal, endpoint=config.endpoint)
            self.owner.validate()
            self.metadata = metadata if metadata is not None else inspect_ollama(config)
            self.tokenizer = load_context_tokenizer(tokenizer_path, tokenizer_provenance)
            self.probe = probe or WindowsResourceProbe(endpoint=config.endpoint)
            # This single baseline spans warmup, context, components and complete smoke.
            self.monitor = ResourceMonitor(self.probe, self.journal, self.cancel, interval=config.sample_seconds,
                abort=self.owner.stop)
            if resume_from is not None:
                self._load_resume(resume_from)
        except (Exception, KeyboardInterrupt) as exc:
            import traceback
            result = dict(package="S3", status="no_go", phases={"initialization": {"status":"failed", "error_type":type(exc).__name__}},
                model_calls=0, formal_runs_started=0, next_package_started=False,
                error_location=[dict(file=Path(f.filename).name, line=f.lineno, function=f.name) for f in traceback.extract_tb(exc.__traceback__)],
                server_stop=self.owner.stop() if self.owner else None)
            self.journal.emit("preflight_result", result)
            (self.journal.directory / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            raise
        self.lease_dir = Path(__file__).resolve().parents[1] / "data/granite_endpoint_leases"
        self.journal.emit("preflight_manifest", dict(config=config.model_dump(mode="json"), metadata=self.metadata,
            case_id=context.case_id, packet_sha256=context.packet_sha256, brief_sha256=context.brief_sha256,
            tokenizer_provenance=json.loads(Path(tokenizer_provenance).read_text(encoding="utf-8-sig")),
            formal_runs_started=0, case_approval_status=context.packet.review_status,
            synthetic_upstream_only_in_component_probes=True, complete_smoke_uses_real_upstream=True,
            resume=self.resume))

    def _load_resume(self, result_path):
        """Resume only a clean pre-dispatch component failure under one cumulative cap."""
        result_path = Path(result_path).resolve()
        prior = json.loads(result_path.read_text(encoding="utf-8-sig"))
        expected_phases = prior.get("phases", {})
        if (prior.get("status") != "no_go" or prior.get("requested_phase") != "all"
                or prior.get("config") != self.config.model_dump(mode="json")):
            raise ValueError("resume source is not the same failed full preflight configuration")
        if (expected_phases.get("warmup", {}).get("status") != "passed"
                or expected_phases.get("context", {}).get("status") != "passed"
                or expected_phases.get("components", {}).get("status") != "failed"
                or expected_phases.get("smoke", {}).get("status") != "not_run"):
            raise ValueError("resume source must have passed warmup/context and no smoke execution")
        if (prior.get("resources", {}).get("status") != "passed"
                or prior.get("server_stop", {}).get("status") != "owned_process_tree_terminated"):
            raise ValueError("resume source cleanup/resource evidence is not passed")
        if prior.get("metadata", {}).get("model_digest") != self.metadata.get("model_digest"):
            raise ValueError("resume source model digest differs from the currently inspected model")

        prior_root = result_path.parent
        attempts = []
        for path in sorted(prior_root.glob("*/events.jsonl")):
            attempts.extend(replay_events(path)["attempts"])
        if len(attempts) != prior.get("model_calls"):
            raise ValueError("resume source model call count does not match durable events")
        for attempt in attempts:
            charge = attempt.get("budget_token_charge")
            if type(charge) is not int or charge < 0 or attempt.get("ended_at_utc") is None:
                raise ValueError("resume source has an unknown/unfinalized token charge")
            prompt = attempt.get("prompt_tokens")
            output = attempt.get("output_tokens")
            known = type(prompt) is int and type(output) is int and charge >= prompt + output
            self.shared_budget.reserve_request()
            self.shared_budget.record_usage(prompt_tokens=prompt if known else 0,
                output_tokens=output if known else 0, total_tokens=charge)
            if attempt.get("transport_retry_of"):
                self.shared_budget.record_retry()

        elapsed_candidates = []
        for line in (prior_root / "events.jsonl").read_text(encoding="utf-8-sig").splitlines():
            event = json.loads(line)
            elapsed = event.get("payload", {}).get("elapsed_seconds")
            if type(elapsed) in (int, float) and elapsed >= 0:
                elapsed_candidates.append(float(elapsed))
        for phase in ("warmup", "context"):
            elapsed = expected_phases[phase].get("budget", {}).get("run_elapsed_seconds")
            if type(elapsed) in (int, float) and elapsed >= 0:
                elapsed_candidates.append(float(elapsed))
        if not elapsed_candidates:
            raise ValueError("resume source lacks cumulative elapsed-time evidence")
        prior_elapsed = max(elapsed_candidates)
        current_elapsed = time.monotonic() - self.shared_started
        self.shared_started = time.monotonic() - prior_elapsed - current_elapsed
        self.phases = {name: expected_phases[name] for name in ("warmup", "context")}
        self.prior_attempts = attempts
        self.resume = dict(result_path=str(result_path), result_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest(),
            prior_model_calls=len(attempts), prior_elapsed_seconds=prior_elapsed,
            prior_resources=prior["resources"], prior_server_stop=prior["server_stop"],
            resumed_phases=["components", "smoke"])
        self.journal.emit("preflight_resume", dict(**self.resume,
            cumulative_budget=self.shared_budget.snapshot()))

    def _surface(self, name, kind="preflight", *, raw_context=False):
        config = self.config.review_config(kind, model_digest=self.metadata["model_digest"])
        journal = EventJournal(self.journal.directory / name, str(uuid4()))
        provider = self.provider_factory(self.config, model_digest=self.metadata["model_digest"],
            context_tokenizer=self.tokenizer if raw_context else None)
        lease = LocalRequestLease(self.lease_dir, self.config.endpoint)
        client = BoundedClient(provider, config, journal, cancel=self.cancel, local_lease=lease,
            budget=self.shared_budget, started_at=self.shared_started)
        client.input_refs = [dict(artifact_id="packet", artifact_version=1, sha256=self.context.packet_sha256),
                             dict(artifact_id="brief", artifact_version=1, sha256=self.context.brief_sha256)]
        generator = ContractGenerator(client, task_sink=lambda t: journal.emit("logical_task", t),
            attempt_scope=client.attempt_scope, protocol=self.config.protocol_version)
        return client, generator, journal

    def _task(self, client, journal, role, action):
        started = client.clock()
        try:
            client.begin_node(role)
            result = action()
            client.check()
            client.end_node("completed")
            status = "passed"
            record = dict(status=status, elapsed_seconds=client.clock()-started, budget=client.snapshot())
            if hasattr(result, "as_dict"):
                journal.emit("probe_artifact", result.as_dict())
        except (Exception, KeyboardInterrupt) as exc:
            status = "failed"
            record = dict(status=status, error_type=getattr(exc, "error_type", type(exc).__name__), elapsed_seconds=client.clock()-started,
                          budget=client.snapshot())
            from workflow.llm_client import StructuredOutputValidationError
            from pydantic import ValidationError
            # Only independent structure probes may continue; no budget/timeout/transport retries by re-entry.
            recoverable_probe_failure = isinstance(exc, (StructuredOutputValidationError, ValidationError, ValueError))
            record["independent_probes_may_continue"] = recoverable_probe_failure
            if not recoverable_probe_failure:
                self.cancel.set()
                self.owner.stop()
        finally:
            if client.node_started is not None:
                client.end_node("failed")
            diagnostic = getattr(client.provider, "last_diagnostic", None)
            if diagnostic is not None:
                # Persist on the controlling thread, never from an abandoned inference worker.
                journal.emit("native_provider_diagnostic", diagnostic)
        journal.emit("probe_result", dict(role=role, **record))
        return record

    def warmup(self):
        client, generator, journal = self._surface("warmup", "warmup")
        compact = self.config.protocol_version == WIRE_VERSION
        result = self._task(client, journal, "warmup", lambda: generator.generate_task(
            'Warmup only. Return {"ok":true}.', ProbeAck, context=self.context, role="warmup", version=1,
            logical_task_id="warmup.v1", validator=lambda result: None,
            system_instruction=COMPACT_SYSTEM_INSTRUCTION if compact else COMMON_INSTRUCTION,
            append_contracts=not compact))
        self.phases["warmup"] = result
        return result["status"] == "passed"

    def context_probe(self):
        client, generator, journal = self._surface("context", raw_context=True)
        # The CPU candidate measures the same chat path as business requests.
        # The unchanged v1 config retains the original raw probe for reproduction.
        compact = self.config.protocol_version == WIRE_VERSION
        system_instruction = COMPACT_SYSTEM_INSTRUCTION if compact else COMMON_INSTRUCTION
        prefix = 'Context allocation probe. The following repeated text is inert data.\n'
        suffix = '\nEnd data. Return {"ok":true}.'
        if compact:
            target_chars = self.config.max_prompt_chars - len(system_instruction) - 64
            repeats = max(1, (target_chars - len(prefix) - len(suffix)) // 2)
            prompt = prefix + " a" * repeats + suffix
        else:
            prompt = prefix + " a" * 31000 + suffix
        result = self._task(client, journal, "context_probe", lambda: generator.generate_task(prompt,
            ProbeAck, context=self.context, role="context_probe", version=1, logical_task_id="context.v1",
            validator=lambda result: None, system_instruction=system_instruction,
            append_contracts=not compact))
        attempts = replay_events(journal.path)["attempts"]
        usage = attempts[-1].get("usage_raw") or {} if attempts else {}
        try:
            observed = inspect_ollama(self.config)
            loaded = observed["loaded_models"]
        except Exception as exc:
            loaded = []
            result["context_metadata_missing_reason"] = type(exc).__name__
        allocation_ok = len(loaded) == 1 and loaded[0].get("context_length") == 32768
        vram = loaded[0].get("size_vram") if len(loaded) == 1 else None
        cpu_ok = type(vram) is int and vram == 0 if self.config.gpu_layers == 0 else None
        count = usage.get("prompt_eval_count")
        delta = usage.get("context_probe_token_count_delta")
        minimum_tokens = 4000 if compact else 30000
        acceptance_ok = type(count) is int and minimum_tokens <= count < 32768 and type(delta) is int and abs(delta) <= 8
        result.update(allocated_context_tokens=loaded[0].get("context_length") if loaded else None,
            measured_input_tokens=count, expected_input_tokens=usage.get("context_probe_expected_tokens"),
            token_count_delta=delta, allocation_verified=allocation_ok, full_input_acceptance_verified=acceptance_ok,
            context_probe_mode=self.config.context_probe_mode, cpu_only_verified=cpu_ok,
            compact_prompt_cap_verified=(len(prompt) + len(system_instruction or "") <= self.config.max_prompt_chars),
            full_prompt_chars=len(prompt) + len(system_instruction or ""))
        if not allocation_ok or not acceptance_ok or cpu_ok is False:
            result["status"] = "failed"
        journal.emit("context_measurement", result)
        self.phases["context"] = result
        return result["status"] == "passed"

    def components(self):
        client, generator, journal = self._surface("components")
        ctx = self.context
        research = ctx.accept("research", synthetic_artifact(ctx, "research", version=1, inputs={}))
        strategy = ctx.accept("strategy", synthetic_artifact(ctx, "strategy", version=1, inputs={}), upstream=(research,))
        finance = ctx.accept("finance", synthetic_artifact(ctx, "finance", version=1, inputs={}), upstream=(research, strategy))
        for artifact in (research, strategy, finance):
            journal.emit("synthetic_probe_input", artifact.as_dict())
        def writer():
            if self.config.protocol_version == WIRE_VERSION:
                return generator.generate(ctx, "writer", upstream=(research, strategy, finance))
            def validate(candidate):
                ctx.validate(candidate, version=1, upstream=(research, strategy, finance))
                for title, field in SECTION_FIELD_BY_TITLE.items():
                    if field in PROPOSAL_SECTION_BATCHES[0] and getattr(candidate, field).title != title:
                        raise ValueError("wrong Writer section title")
            return generator.generate_task(writer_probe_prompt(ctx, (research, strategy, finance)), CONTRACT_BATCH_MODELS[0],
                context=ctx, role="writer", version=1, logical_task_id="writer.v1.batch1", batch_number=1, validator=validate,
                two_stage=True, upstream=(research, strategy, finance))
        actions = [("research", lambda: generator.generate(ctx, "research")),
            ("component_critic", lambda: ComponentCritic(generator).review(ctx, research, role="research", artifact_id="research.initial")),
            ("finance", lambda: generator.generate(ctx, "finance", upstream=(research, strategy))), ("writer", writer)]
        results = {}
        for role, action in actions:
            if self.cancel.is_set():
                results[role] = dict(status="not_run", reason="prior stop gate")
                continue
            client.input_refs = [dict(artifact_id="packet", artifact_version=1, sha256=ctx.packet_sha256)]
            if role != "research":
                client.input_refs.extend(dict(artifact_id=f"synthetic.{a.role}", artifact_version=1, sha256=a.sha256)
                    for a in ((research,) if role == "component_critic" else (research, strategy) if role == "finance" else (research, strategy, finance)))
            results[role] = self._task(client, journal, role, action)
        result = dict(status="passed" if all(r["status"] == "passed" for r in results.values()) else "failed", probes=results)
        self.phases["components"] = result
        return result["status"] == "passed"

    def smoke(self):
        config = self.config.review_config("smoke", model_digest=self.metadata["model_digest"])
        provider = self.provider_factory(self.config, model_digest=self.metadata["model_digest"])
        workflow = build_slm_review_workflow(self.context, config=config, provider=provider,
            local_lease=LocalRequestLease(self.lease_dir, self.config.endpoint), cancel=self.cancel,
            output_dir=self.journal.directory / "smoke", shared_budget=self.shared_budget,
            started_at=self.shared_started)
        result = workflow.run()
        diagnostic = getattr(provider, "last_diagnostic", None)
        if diagnostic is not None:
            workflow.journal.emit("native_provider_diagnostic", diagnostic)
        self.phases["smoke"] = dict(status="passed" if result["status"] == "completed" else "failed", result=result)
        if result["status"] in ("timeout", "cancelled", "failed", "budget_exhausted"):
            self.cancel.set()
            self.owner.stop()
        return result["status"] == "completed"

    def run(self, phase="all"):
        if phase == "resume":
            if self.resume is None:
                raise ValueError("resume phase requires a validated resume result")
            selected = ("components", "smoke")
        else:
            selected = ("warmup", "context", "components", "smoke") if phase == "all" else (phase,)
        dependency_passed = True
        resources, server_stop = None, None
        cleanup_done = False

        def cleanup():
            nonlocal resources, server_stop, cleanup_done, dependency_passed
            if cleanup_done:
                return
            cleanup_done = True
            try:
                resources = self.monitor.close()
            except (Exception, KeyboardInterrupt) as exc:
                resources = dict(status="failed", reason="resource_monitor_cleanup_failed", error_type=type(exc).__name__)
                self.phases["resource_cleanup"] = dict(status="failed", error_type=type(exc).__name__)
                dependency_passed = False
                self.cancel.set()
            finally:
                # Stop owned inference before releasing the scoped power request,
                # including when monitor cleanup itself failed.
                try:
                    server_stop = self.owner.stop()
                except (Exception, KeyboardInterrupt) as exc:
                    server_stop = dict(status="termination_unconfirmed", error_type=type(exc).__name__, lease_released=False)
                if not isinstance(server_stop, dict) or server_stop.get("status") != "owned_process_tree_terminated":
                    self.phases["server_cleanup"] = dict(status="failed", reason="owned_server_termination_unconfirmed")
                    dependency_passed = False
                    self.cancel.set()

        try:
            # No provider is created or invoked before successful scope entry.
            # Its requests remain active through monitor and owned-server cleanup.
            with self.awake_factory(journal=self.journal):
                try:
                    self.monitor.start()
                    for name in selected:
                        if not dependency_passed or self.cancel.is_set():
                            self.phases[name] = dict(status="not_run", reason="prior feasibility gate failed")
                            continue
                        dependency_passed = getattr(self, "context_probe" if name == "context" else name)()
                except (Exception, KeyboardInterrupt) as exc:
                    self.phases["unexpected_stop"] = dict(status="failed", error_type=type(exc).__name__)
                    dependency_passed = False
                    self.cancel.set()
                finally:
                    cleanup()
        except (Exception, KeyboardInterrupt) as exc:
            self.phases["power_scope"] = dict(status="failed", error_type=type(exc).__name__)
            for name in selected:
                self.phases.setdefault(name, dict(status="not_run", reason="power request scope failed"))
            dependency_passed = False
            self.cancel.set()
        finally:
            # Enter failures still close the initialized monitor and owned server.
            cleanup()
        if self.resume is not None:
            prior_resources = self.resume["prior_resources"]
            def combined_number(key, reducer):
                values = [value for value in (prior_resources.get(key), resources.get(key))
                    if type(value) in (int, float)]
                return reducer(values) if values else None
            resources = dict(status="passed" if prior_resources.get("status") == resources.get("status") == "passed" else "failed",
                segments=[dict(kind="prior", evidence=prior_resources), dict(kind="resume", evidence=resources)],
                sample_count=(prior_resources.get("sample_count") or 0) + (resources.get("sample_count") or 0),
                min_available_ram_bytes=combined_number("min_available_ram_bytes", min),
                peak_gpu_used_bytes=combined_number("peak_gpu_used_bytes", max),
                maximum_observed_sample_gap_seconds=combined_number("maximum_observed_sample_gap_seconds", max))
        required = ("warmup", "context", "components", "smoke") if phase in ("all", "resume") else selected
        passed = (dependency_passed and not self.cancel.is_set() and resources["status"] == "passed"
            and all(self.phases.get(name, {}).get("status") == "passed" for name in required))
        attempts = []
        for path in self.journal.directory.glob("*/events.jsonl"):
            attempts.extend(replay_events(path)["attempts"])
        all_attempts = self.prior_attempts + attempts
        complete_request = phase in ("all", "resume")
        summary = dict(package="S3", status="go" if passed and complete_request else "phase_passed" if passed else "no_go",
            requested_phase="all" if complete_request else phase, phases=self.phases, resources=resources, metadata=self.metadata,
            config=self.config.model_dump(mode="json"), model_calls=len(all_attempts), formal_runs_started=0,
            cumulative_budget=self.shared_budget.snapshot(),
            cumulative_elapsed_seconds=time.monotonic() - self.shared_started, resume=self.resume,
            server_stop=server_stop, context_claim="allocated 32768; measured accepted input is reported separately",
            input_status="explicitly authorized non-formal preflight only", next_package_started=False,
            next_action="joint smoke freeze only; formal S5 remains prohibited" if passed and complete_request else "review feasibility evidence before dependent work")
        self.journal.emit("preflight_result", summary)
        (self.journal.directory / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("configs") / "granite_preflight_cpu_v2.json")
    parser.add_argument("--case", choices=("ai_education", "intelligent_ring"), default="ai_education")
    parser.add_argument("--phase", choices=("all", "warmup", "context", "components", "smoke", "resume"), default="all")
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--server-owner", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--tokenizer-provenance", type=Path, required=True)
    args = parser.parse_args()
    config = GraniteConfig.model_validate_json(args.config.read_text(encoding="utf-8-sig"))
    root = Path(__file__).resolve().parents[1] / "docs/final_sprint/s0-v1"
    context = ContractContext.from_case(root, args.case, condition="D")
    try:
        runner = GranitePreflight(config=config, context=context, output_dir=args.output_dir, owner_path=args.server_owner,
            tokenizer_path=args.tokenizer, tokenizer_provenance=args.tokenizer_provenance,
            resume_from=args.resume_from)
    except Exception as exc:
        print(json.dumps(dict(status="no_go", error_type=type(exc).__name__, output_dir=str(args.output_dir))))
        return 2
    result = runner.run(args.phase)
    print(json.dumps(dict(status=result["status"], phases={k:v["status"] for k,v in result["phases"].items()},
        model_calls=result["model_calls"], formal_runs_started=0, output_dir=str(args.output_dir)), indent=2))
    return 0 if result["status"] in ("go", "phase_passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
