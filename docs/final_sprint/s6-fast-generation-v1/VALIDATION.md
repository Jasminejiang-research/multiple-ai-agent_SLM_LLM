# S6 validation

## Final test results

All commands used the bundled Python runtime with the repository's existing `.venv/Lib/site-packages` on `PYTHONPATH`; no dependency installation or network access occurred.

1. S6 acceptance:
   `python -m pytest tests/test_s6_compact_protocol.py -q -p no:cacheprovider`
   Result: **13 passed in 3.84s**. Log: `validation/s6_acceptance_final.junit.xml`, SHA-256 `5f099690b19158d2545da1ff597418251b38ff96cb63d23ac1ac4dfd9072b1e5`.
2. Full repository regression from repository root:
   `python -m pytest -q -p no:cacheprovider`
   Result: **638 passed, 25 deselected, 3 subtests passed in 96.57s**. Log: `validation/full_final.junit.xml`, SHA-256 `137269716f74b74abe4571ad32db4b347b4c6022fcbfd32a47a5a71bc71515c6`.
3. Dependency validation:
   `python -m pip check` returned `No broken requirements found`; imports for Pydantic, Google GenAI, LangGraph, SQLAlchemy, Streamlit, Requests, and Tokenizers succeeded.

The full regression includes existing timeout, partial/invalid output, citation pollution, finance mismatch, budget exhaustion, resource-stop, cleanup, immutable failure, and resume coverage. S6-specific tests add compact DTO/canonical roundtrip, fixed 13 sections, 21/27 case-specific finance results, short-ID closure, bounded repair, patch overreach, second-revision refusal, score-only non-routing, unresolved-state inheritance, and C/D hash equivalence.

## Eight-slot synthetic rehearsal

`python -m evaluation.s4 rehearsal ...` and `python -m evaluation.s4 export ... --no-figures` completed the frozen two-case A–D matrix using only `SyntheticProvider`.

- 8/8 executions succeeded; 8/8 terminal contracts passed.
- 8/8 recorded MVP30 reached and 8/8 ValidPlan60 reached.
- 53/53 synthetic physical calls succeeded.
- Maximum instruction length was 269 Unicode characters (limit 500).
- Every estimated input target passed. Research maximum was 2,498/2,500; Finance maximum was 2,977/3,000; Revision maximum was 1,800/1,800.
- Maximum full prompt was 13,188 characters, below the shared 26,000-character guard.
- All high/critical synthetic paths revised once; no second semantic Critic or revision occurred.

Raw events and exports are under `mock_rehearsal_final/`. `mock_rehearsal/` is an earlier preserved rehearsal that exposed and led to fixing a revision-input estimate overrun; it is not the final acceptance evidence. Synthetic timings and content are engineering evidence only, not real model quality, real latency, or proof that Granite meets 30/60 minutes.

## Real validation and formal runs

S6 made 18 real Granite calls: 10 in the D engineering preflight and 8 in the separately authorized best-effort product demo. It made zero Gemini calls and zero formal calls. All inspected formal manifests remain 0/8. The D preflight was explicitly authorized, ran within the common 3,600-second/18-request/160,000-token/1,800-output ceiling, and ended `no_go`; therefore the approved bounded Gemini smokes did not start. The independent demo cannot satisfy that gate. Details are in `REAL_CALL_STATUS.json`, `D_PREFLIGHT_ATTEMPT_03.json`, and `BEST_EFFORT_DEMO_RESULT.json`.

### D preflight engineering fixes and offline regression

- Attempt 01 made zero calls and exposed missing compact aliases for warmup/context.
- Attempt 02 passed warmup and 32K CPU context in 2 calls/12,979 tokens, then exposed a pre-dispatch component protocol-injection defect.
- The preflight now uses compact probes, propagates the compact protocol into all component paths, uses the compact Writer wire, shares one request/token/time budget across phases, and supports a strictly validated resume that restores earlier calls/tokens/time instead of resetting allowances.
- Final targeted regression: **64 passed in 6.09s**. JUnit: `validation/preflight_fix_stage2_targeted_final.junit.xml`, SHA-256 `0aef529274253a42e7c12c5ca6471c3899ded04425e8286859adcc2c143b733e`.
- Final full regression: **638 passed, 25 deselected, 3 subtests passed in 137.60s**. JUnit: `validation/preflight_fix_stage2_full_final.junit.xml`, SHA-256 `9b129438d564661575032f92218c8908a09a68d44e6947b0a5a31c80ac818bff`.

### Authorized D result

- Combined attempts 02+03: **10/18 requests**, **30,817/160,000 charged tokens**, **1,233.531/3,600 active seconds**; exact known usage was 24,738 prompt + 6,079 output tokens.
- Warmup and context passed. The context call measured 12,905 expected/observed input tokens with zero delta; Ollama reported one loaded 32K model and `size_vram=0`.
- Research (450 output cap), Research Critic (180), Finance (600), and Writer (1,800) each returned `finish_reason=length` on its initial call and sole structure repair. All eight component calls therefore failed strict structure validation. No third attempt, transport retry, semantic revision, D smoke, Gemini smoke, or formal execution occurred.
- Combined resources passed across 242 samples; minimum available RAM was 4,857,692,160 bytes and the maximum sampling gap was 5.422 seconds.
- Exact cleanup passed: project-owned PID 9660 is absent, 11434 has zero listeners, and the active project lease count is zero. The archived old `inflight_or_unknown` lease was not deleted or refunded.
- Immutable raw result: `real_preflight_d_ai_education_03/probe/result.json`, SHA-256 `9a675099cc1dc0ff06bbcf8f61e0b9c551353e0fc7b3d94dc409ac0be639c6b9`. Derived cross-segment accounting: `D_PREFLIGHT_ATTEMPT_03.json`.

The derived D record is explicitly labelled `nonformal_engineering_preflight_failure`, `status=no_go`, `formal_experiment_result=false`, and `c_minus_d_comparison_eligible=false`. This was a classification-only amendment: its 10-call measurements and immutable raw-result hash did not change.

### Independent best-effort demo validation

- Mode-specific tests plus S6 compact/reference controls: **21 passed in 4.58s**. JUnit: `validation/best_effort_targeted_final.junit.xml`, SHA-256 `dd631e46fcb05727325b5bb34766b957623b0ac8ddcb31c924a0b0114af3e44a`.
- Full repository regression before the live demo: **638 passed, 25 deselected, 3 subtests passed in 133.32s**. The JUnit contains 641 cases and zero failures/errors: `validation/best_effort_full_01.junit.xml`, SHA-256 `3e507456f348b102dab7aa7318b4914862ddd2be3fcf43dfe41b0868a54bd533`.
- Verified offline branches: all four Critics execute; malformed Critic output and low scores do not gate later roles/export; truncated Writer text is saved and reused; missing sections receive only `信息不足，待验证`; request exhaustion and unknown transport timeout stop additional physical dispatch but still produce the deterministic 13-section low-quality export.
- Single authorized real run: **8/10 requests**, **5,170/80,000 tokens** (4,273 input, 897 output), **189.828/1,800 seconds**, no retry and no missing usage. Research alone ended `finish_reason=length` at its 128-token cap and was saved as `truncated_saved`; the remaining seven calls ended `stop` and completed.
- All 13 fixed sections were exported. Twelve non-financial sections are marked `assumption/unsupported`; the display plan contains no short IDs and no unknown IDs. The financial section contains all 21 case-specific values from deterministic code and overwrites Writer-generated financial prose.
- All four Critics ran and were retained: Research 3, Strategy 3, Finance 2, final 0. Their issue text is in the raw responses and `BEST_EFFORT_DEMO_RESULT.json`; no score triggered a retry or gate.
- Resources passed: 38 samples, minimum available RAM 5,440,462,848 bytes, peak RAM used 11,528,962,048 bytes, peak pagefile delta 1,544,192 bytes, maximum sample gap 5.172 seconds, loaded-model `size_vram=0`, and no missing observations.
- Cleanup passed: owned PID 16236 is absent, listener count on 11434 is zero, and active lease count is zero. No lease deletion/refund occurred.
- Immutable run evidence: `real_best_effort_ai_education_01/demo/result.json` SHA-256 `34253b64dd9388db82d26adb69a327dd6e5c9ed807c1e6b86835d88fb0c31d9b`; event journal SHA-256 `617a0a2b69bf82fc8bb04f9501a7ede179114bb0521b7e82448dd5797f9384b9`; 16 original text/provider files remain in `raw_responses/`.

## Post-handoff process, lease, and gate validation

On 2026-09-07 after the user-requested reconciliation:

- PID 24092, the exact project-owned S3 native identity, was absent. PIDs 17860/18776 had later creation times and an Ollama Desktop parent/child chain, so neither was stopped.
- The active lease path became absent only after its 137 original bytes were moved to the project archive. The archived SHA-256 is unchanged at `c185cb7770cf89f12a168ed27c9d09c6000c9cb38df43198de8cac93bd6f475a`; status remains `inflight_or_unknown`, with no deletion or refund.
- Five affected JSON records parsed successfully: process/lease reconciliation, D proposal, Gemini approval, real-call status, and pending freeze.
- `python -B -m evaluation.s4 check-freeze --experiment docs/final_sprint/s6-fast-generation-v1/next_s5_entry` returned exit code 2 with `ready=false`. It retained the D real-preflight, A/B/C real-smoke, common-config/input, total-stop-limit, and formal-authorization blockers. This is the required fail-closed result; S5 was not entered.

After the authorized D result, the freeze remains deliberately pending: D is `no_go`, Gemini A/B/C was not run, and no common refreeze was performed. A fresh `check-freeze` is expected to remain fail-closed until an explicitly approved D scope resolution and both real smoke gates pass.

After the independent best-effort demo and handoff update, the final consistency check parsed seven controlling/result JSON files, reconfirmed the immutable D raw SHA-256, found zero 11434 listeners and zero active leases, and reran `evaluation.s4 check-freeze`. It returned the required exit code 2 with `ready=false`; therefore the product demo did not clear or weaken any S5 entry gate.
