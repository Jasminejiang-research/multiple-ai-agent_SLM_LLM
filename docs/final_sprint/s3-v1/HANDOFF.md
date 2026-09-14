# S3 Granite preflight handoff

Status (2026-09-07 Europe/Berlin): **engineering integration delivered; S3 acceptance blocked by real preflight no_go. D is not qualified for formal experiments. S4 has not started.** The authoritative stop rule is sprint_plan_ §6: “D不通过可行性门时保留记录，停止需要D成功的后续安排并请用户确认范围”. No model, experiment group, output cap or budget was changed after failure.

## Actual outcome and evidence

`real_preflight_03/result.json` is the unmodified real result; `events.jsonl` holds 87 resource samples, ownership and run metadata. Child `warmup/events.jsonl` and `context/events.jsonl` contain the two physical attempts. `setup_03/server.stderr.log` preserves the runtime error and diagnostic prefill progression; `server.stdout.log` preserves HTTP access records. Full component probes and D smoke are **not_run**, not passed or simulated substitutes.

| Gate / measurement | Actual result |
|---|---|
| Exact model | official IBM Granite 4.0 H Micro, 3,191,396,096 parameters, Q4_K_M; Ollama 0.33.2 |
| Alias digest | `eec81a822241037c5d8e47a870b3d26423bfa1b010e02fcdf1b5f9f2de5c3b2b` |
| Warmup | passed; 42.484 s wall clock; 332 input / 9 output tokens |
| Warmup phases | load 19.7858806 s; prefill 21.797817 s; generation 0.850571 s (10.58 output token/s) |
| Context allocation | `/api/ps` telemetry observed `context_length=32768` with one loaded model |
| Long input request | failed after 486.344 s; provider `OllamaMissingCompletion`; no complete API usage returned |
| Runtime diagnostics | sampler log reports 31,331 text tokens; final processing log 484.03 s; `truncated=0`; these are diagnostic counters, not successful API usage |
| Failure | `Unexpected empty grammar stack after accepting piece: @ (31)` during structured decoding; HTTP returned 200 without a normal completed response |
| Baseline | physical RAM 16,969,424,896 B; available 7,099,645,952 B; actual pagefile used 550,502,400 B |
| Sampled resource extrema | minimum available RAM 4,453,490,688 B (~4.148 GiB); peak system RAM used 12,515,934,208 B (~11.656 GiB); peak GPU used 552,599,552 B (~0.515 GiB); pagefile growth 0 B |
| Resource/time gates | passed for the observed attempts; largest sample gap 8.109 s; neither 60-second resource threshold nor 1200-second parent deadline triggered |
| Shutdown | owned PID 28292 process tree confirmed terminated; request lease deliberately retained |

The context result has null post-stop allocation and API counts because the server was terminated before final metadata collection. Earlier telemetry proves allocation, but does not convert the failed request into a successful effective-context/structured-output gate. Missing usage remains null; the 64,890-token reservation retained for this attempt is a conservative budget charge, **not** measured consumption. Do not report the unfinished context generation as zero output tokens or derive its generation throughput.

`real_preflight_01` and `real_preflight_02` preserve two initialization failures with **zero model calls**. A Windows single-PID serialization compatibility fix is covered by the added tests; attempt 02 and attempt 03 have confirmed owned-process termination. Attempt 01's termination proof was unconfirmed, followed by a read-only process/port check showing no remaining Ollama process or listener. The initial startup script and setup logs are retained. No hidden generation retry, alternative model, quota query, Gemini call or formal run occurred.

## Resume decision and remaining gates

Stop here pending the user's decision under the S3 no-go rule. A follow-up can investigate the current H Micro / Ollama structured-decoding failure while preserving this attempt, or the user can approve another treatment of D. This handoff does not authorize H 1B, a cloud substitution, Granite Single, a smaller D-only context or schema, or larger budgets. The four component tests and full D smoke still require successful real validation; the present run provides no quality evidence for them.

The marker `data/granite_endpoint_leases/2fb24565ac96fa6667ae7aac126b1d1c01bd9ec999315b419e6010a19e5d9461.lease.json` remains quarantined. Before any approved new attempt, inspect the recorded PID/start time and confirm the old process tree and endpoint are gone, archive the exact marker with the shutdown evidence, and explicitly reconcile it. Never auto-delete it based on elapsed time or restart the server under it. Use fresh setup/output directories.

Keep common A–D limits **unfrozen**. The observed failure does not justify changing 1024/18 or choosing a larger cap. First resolve the runtime gate and complete the real Research, Critic, Finance, Writer and D smoke checks; only then choose one common policy covering repairs/revisions and the existing time limits. Both cases' brief/packet approvals and S4/S5 freeze/runner/review remain pending; formal status is 0/8 and Gemini calls/cost are zero in S3. Existing ~CNY50 Gemini spending constraint is unchanged.

Next package entry is sprint_plan_ §7 **S4**, the current `docs/final_sprint_status.md`, and `slm/factories.py:build_slm_review_workflow` / `workflow/review_runtime.py`. S4 may not assume D success; its D handling requires the user's scope decision. No S4 implementation or formal experiment was started.

## Implementation and reproducible commands

Final installed offline validation: **586 passed, 25 deselected, 3 subtests passed in 91.96 s** (`final_validation.txt`). Final S3-only staging suite: 38 passed in 3.75 s. Dependency check passed without installing/upgrading Python packages. S0 preparation integrity passed; formal freeze guard correctly returned exit 2. Prior baseline: 548 passed; earlier integration: 584 passed. Mocks verify implementation and routing only; none are model-feasibility evidence.

The implementation uses `slm/granite_preflight.py`, `granite_provider.py`, `granite_config.py`, `resource_monitor.py`, `owned_ollama.py`, and `start_granite.ps1`. It injects the native Ollama provider into the existing S2 `build_slm_review_workflow` and therefore uses the same Research, Strategy, Finance, Writer, three role Critics, final Critic, conditional revisions and 4/3/3/3 Writer batches as C. Legacy Qwen/hosted entry points and all S0–S2 changes remain intact.

The versioned `slm/configs/granite_preflight_v1.json` is an unfrozen candidate: official IBM H Micro Q4_K_M, alias `granite-h-micro-32k`, explicit 32768 context, temperature 0, 1024 output tokens, 18 requests, 160000 total charged tokens and 90000 prompt characters. The 160000 total ceiling retains the legacy initial ceiling; 18 and 1024 are the design's starting values. Limits apply independently to warmup, context, combined component probes, and complete D smoke. No budget automatically expands after a failure. S4/S5 must freeze a common A–D policy; this file is not a formal experiment configuration.

Each physical call records raw output, usage and finish reason. Nanosecond `prompt_eval_duration` and `eval_duration` remain separate. Prefill rate uses uncached input count if exposed; when cache count is missing its explicitly labelled all-input ratio must not be read as pure uncached throughput. Budget reservations use S2's conservative byte estimate; measured usage remains null when unavailable.

Warmup is separate from measured component timings. The raw context probe uses the hash-verified official base tokenizer and roughly 31K input tokens, with the full common system instruction and small acknowledgement schema. It records actual `prompt_eval_count`, expected tokenizer count, their difference, and `/api/ps` context allocation. A 32768 allocation alone is not effective-context proof. The raw prompt deliberately avoids hidden chat templating; subsequent role calls use the common chat prompts without evidence pruning.

Component probes use full frozen case inputs. Research is generated from the packet; Critic, Finance and Writer isolate their schemas with clearly tagged synthetic upstream artifacts from S2. These are test inputs, never model results or Gold. Only the complete D smoke uses actual generated upstream artifacts throughout. A structure failure permits the other independent component probes within the same budget; it blocks complete smoke. Resource/time/transport/budget failures also stop remaining probes.

One baseline spans the full invocation, before loading through final sampling. RAM is Windows physical available memory; pagefile is the actual sum of `Win32_PageFileUsage.CurrentUsage`, not commit or allocated size. GPU memory is system GPU occupancy from `nvidia-smi`; peaks are sampled, not exact continuous maxima. Missing values retain null/reasons. Available RAM below 2 GiB or pagefile growth above 2 GiB for 60 continuous seconds cancels work and terminates only the verified owned Ollama process tree. Parent node <=1200 seconds includes every batch, Critic, repair and revision; complete Multi <=5400 seconds. A timed-out/unknown request retains its endpoint lease, even after termination, until explicit reconciliation.

Reproduction from the requested project directory (fresh paths required):

```powershell
# First resolve/reconcile the quarantined attempt under the user's decision.
& ./slm/start_granite.ps1 -OutputDirectory data/s3-new-setup
# Model setup was already completed in S3; skip these two commands for the installed alias.
& "$env:LOCALAPPDATA/Programs/Ollama/ollama.exe" pull hf.co/ibm-granite/granite-4.0-h-micro-GGUF:Q4_K_M
& "$env:LOCALAPPDATA/Programs/Ollama/ollama.exe" create granite-h-micro-32k -f slm/Modelfile.granite-h-micro-32k
& ./.venv/Scripts/python.exe -B -m slm.granite_preflight --phase all --case ai_education --output-dir data/s3-new-preflight --server-owner data/s3-new-setup/server_owner.json --tokenizer docs/final_sprint/s3-v1/setup/tokenizer.json --tokenizer-provenance docs/final_sprint/s3-v1/setup/tokenizer_provenance.json
```

For the installed model, use the startup and preflight commands after resolving the failure and stale lease. Run them in the same supervised shell session; the preflight terminates its owned server on completion or failure. `--phase` supports isolated diagnostic runs; `phase_passed` cannot qualify D. The default `all` requires warmup, measured context, all four component probes, complete smoke, and resource gates. A failed attempt is never overwritten or auto-resumed. No command starts S4 or a formal run.

Primary transport/model references consulted on 2026-09-06: [official IBM GGUF](https://huggingface.co/ibm-granite/granite-4.0-h-micro-GGUF), [Ollama chat API](https://docs.ollama.com/api/chat), [raw generation and timing fields](https://docs.ollama.com/api/generate), [loaded-model context allocation](https://docs.ollama.com/api/ps), [Ollama context configuration](https://docs.ollama.com/context-length). Local metadata and real event records determine the actual installed behavior.
