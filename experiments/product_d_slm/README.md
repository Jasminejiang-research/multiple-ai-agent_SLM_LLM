# Experiment D / SLM restoration audit

Audit date: 2026-09-12 (Europe/Berlin)

## Scope

- Target: `C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM_gitlab`
- Mother repository: `C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM`
- Requested scope: SLM code, experiment-D plans and execution evidence, outputs, and supporting reproducibility records

## Audit result

The target was not entirely missing SLM support. Its `slm/` package contained 50 non-temporary files and matched the mother repository byte-for-byte by relative path and SHA-256. The common `evaluation/` implementation also matched; the target only had two additional documentation/helper files in that directory.

The missing part was the experiment-D evidence chain. Before restoration, the target had no `docs/final_sprint/` tree, no root SLM or Phase-7 plan, and no D package under `experiments/`. Its README described only the completed A/B execution records.

## Truthful experiment status

Condition D was designed as the reviewed multi-agent pathway using local IBM Granite 4.0 H Micro on CPU with a 32,768-token context. It did not become a completed formal experiment.

The authoritative preserved preflight is `docs/final_sprint/s6-fast-generation-v1/D_PREFLIGHT_ATTEMPT_03.json`:

- status: `no_go`;
- record label: `nonformal_engineering_preflight_failure`;
- cumulative usage: 10 requests, 30,817 tokens, 1,233.531 active seconds;
- warmup and context: passed from the preserved second attempt;
- components: failed because Research, Research Critic, Finance, and Writer each reached the frozen role output cap on both the initial and sole structure-repair call;
- complete D smoke: not run;
- formal D runs: 0;
- C-D comparison eligibility: false.

The separately authorized best-effort demo completed eight requests and exported a 13-section artifact. It is labelled `LOW QUALITY / NON-FORMAL / NOT ELIGIBLE FOR C-D COMPARISON`; its final Critic score was 0. It must not be substituted for a formal D observation.

## Restored material

The original mother-repository paths are retained so internal references and hashes remain meaningful:

- `slm/` — already present and hash-identical; no overwrite was needed;
- `sprint_plan_SLM.md` and `sprint_plan_phase7_eval.md` — SLM and evaluation plans;
- `docs/multiple_ai_agent_optimization_2day_plan.md` and `docs/final_sprint_status.md` — design and chronological status;
- `docs/final_sprint/s0-v1`, `s1-v1`, and `s2-v1` — shared frozen cases, contracts, review gates, and inputs required by D;
- every `docs/final_sprint/s3-*` package — Granite bring-up, diagnostics, fixes, real failed attempts, raw responses, resource telemetry, and handoffs;
- `docs/final_sprint/s4-v1` — A-D runner, dry-run/synthetic evidence, manifests, review/export machinery, and D gate definitions;
- `docs/final_sprint/s6-fast-generation-v1` — final D preflight attempts, authoritative no-go record, best-effort output, raw evidence, and validation;
- `docs/final_sprint/s5-llm-only-v23-results` — final formal-results package preserving both D slots as preflight no-go and the C-D comparison as unavailable;
- the authority and baseline files directly under `docs/final_sprint/`.

The restored selection contains 3,974 mother-repository files across 26 source paths (135,635,850 bytes before adding this index and the README update). No `.env`, database, key/certificate, model-weight, or endpoint-lease file was selected. A content scan found no live-looking Google, OpenAI, or Tavily key; matches were limited to the literal test placeholder `synthetic-unused`.

## Post-restoration validation

- All 3,974 restored mother-repository files were re-hashed in the target: 0 missing, extra, or mismatched files within the selected paths.
- All 50 non-temporary files already present under `slm/` were re-hashed against the mother repository: 0 mismatches.
- A coherent offline SLM contract suite passed: 202 tests in 11.00 seconds. It covered Granite S3 behavior, process ownership, reference bounds, resource observations, S1/S2 adapters, schema contracts, CLI/client/config/factories/pipeline/preflight/pruning, and Windows awake/memory handling. It made no model or network calls.
- The authoritative D raw-result hash, best-effort plan hash, and best-effort raw-result hash all match their recorded SHA-256 values.
- The final reproduction schedule contains exactly two D policy events, for `ai_education-D` and `intelligent_ring-D`; both are `not_run_preflight_no_go`.

A broader historical suite was also attempted and reported 218 passed, 17 failed, and 14 setup errors. These failures are inherited from the mother snapshot rather than copy mismatches: stale preflight/best-effort test fixtures no longer match the current interfaces, S4 still resolves its authority documents through an obsolete absolute Desktop path, isolation checks assume a Git worktree while this target directory has no `.git`, and one Streamlit test exceeded its three-second test timeout. These portability/test-drift findings were not repaired during this evidence-restoration task, because doing so would alter the copied experimental source rather than preserve it.

## Entry points

- Final D outcome: `../../docs/final_sprint/s6-fast-generation-v1/D_PREFLIGHT_ATTEMPT_03.json`
- Final S6 handoff: `../../docs/final_sprint/s6-fast-generation-v1/HANDOFF.md`
- Best-effort summary: `../../docs/final_sprint/s6-fast-generation-v1/BEST_EFFORT_DEMO_RESULT.json`
- Best-effort plan: `../../docs/final_sprint/s6-fast-generation-v1/real_best_effort_ai_education_01/demo/artifact/best_effort_plan.md`
- Formal-results failure analysis: `../../docs/final_sprint/s5-llm-only-v23-results/09_failure_analysis.md`
- D formal reproduction record: `../../docs/final_sprint/s5-llm-only-v23-results/reproduction/preflight/D/D_PREFLIGHT_ATTEMPT_03.json`
- D implementation: `../../slm/`
- A/B package: `../product_ab/README.md`

## Interpretation rule

Use the restored records as engineering and feasibility evidence. Do not report them as a successful formal D run, do not calculate a C-D quality comparison from the best-effort artifact, and do not treat synthetic S4 rehearsal outputs as real model observations.
