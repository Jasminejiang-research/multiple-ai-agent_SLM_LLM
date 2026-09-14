# S3 90-minute recovery v2: claim identity and host sleep

User objective: a complete AI-education proposal within **5400 seconds per model**, with independent SLM and LLM clocks. This package repairs shared generation code and Windows execution protection. It does not claim a successful complete plan or start the formal S5 experiment.

## Observed causes

The prior annotation described the earlier `s3-two-stage-v1` Windows CIM pagefile probe timeout. The installed v1 recovery replaced that probe with native pagefile occupancy sampling; the latest run had no missing RAM/pagefile observations. Its failure was different:

1. `s3-90m-fix-v1/run_01/probe/result.json`: Research body passed, 923 output tokens in 217.438 seconds. Grounding stopped naturally with 6055 output tokens in 1240.266 seconds but failed canonical validation. The model reused a body-span-style ID for claims with different meanings/evidence metadata. A second repeated ID was legal because its identity was unchanged; blindly renaming or deduplicating every repeated ID would corrupt the contract.
2. The sole authorized structure repair did not finish before the 5400-second inference deadline. The final record took 5405.172 seconds including cleanup. Its usage is unknown; the 83,219-token reservation remains charged, not relabeled as actual usage or refunded.
3. Limited Windows Kernel-Power events confirm three sleep intervals totaling **2989.447614 seconds (49m49.45s)**. The maximum observed resource sample gap was **2423.437 seconds**. The original resource summary's `passed` means sampled threshold checks passed; **continuous resource coverage was not certified**. Original evidence is preserved. See `validation/power_events.json` and the prior `run_01/audit/RESOURCE_COVERAGE.md`.
4. Grounding decode consumed 1026.2 of 1240.266 seconds (about 83%). Minifying the same JSON value reduces offline tokenizer count from 6000 to 4801. The service reported 6055 tokens; the discrepancy is recorded without speculation. This is an offline formatting opportunity, not measured post-fix performance. See `validation/GROUNDING_MINIFY_AUDIT.md`.

## Precise changes

- New claim IDs use a role prefix and dot, with task/group examples. Existing IDs are preserved exactly; inherited arbitrary historical IDs are accepted. Parent IDs are existing inherited IDs or null. Every claim has the current artifact version. This blocks the observed span-ID misuse, but does not guarantee all semantic collisions are impossible.
- Identity collisions report the actual ID, both canonical paths and differing fields with bounded excerpts. The identity comparison itself is unchanged. Repair retains the original identity/evidence order for the same inherited claim; a true split uses a new ID and valid parent.
- Schema enum instructions use proper JSON literals, allow nullable parents, and do not misrepresent open unions as closed enums.
- Shared A–D prompts request compact JSON and concise necessary claims. For new claims, select the minimum sufficient nonredundant evidence; inherited anchors and required inline sources remain mandatory. No candidate source text is removed and no generated output is silently rewritten.
- Run-scoped Windows System/Execution power requests are acquired before inference and released after resource/server cleanup. No global power plan, display-on or Away Mode change is made. Windows policy and user sleep remain authoritative; DC Modern Standby can expire these requests.
- Resource sample gaps exceeding `max(3 * interval, 15 seconds)` cancel the run and invalidate coverage. The original RAM/pagefile 2 GiB / 60-second gate is unchanged.
- The public Granite preflight and the new non-formal complete-D helper use the power scope. Entry/exit/monitor/owned-server failures cannot be reported as successful validation.
- A fresh full-D run uses the existing Research acceptance gate inside D. It does not generate an extra isolated Research before restarting the same work. No node, Critic or revision in D is skipped.

## Invariants and versions

`prompt=grounded-generation-v7-claim-identity`; canonical `proposal-grounding-v5-two-stage`; wire `body-then-grounding-v1`. A–D share this prompt/schema behavior and must be re-frozen together for formal comparison. Prior prompt outputs are not pooled into the new experiment.

All 13 sections, 21 financial result rows, exact financial metadata, citations, source hashes, content anchors, lineage, uncertainty, Critics and the single shared structural repair remain. No model/digest/quantization/GPU change. Public formal budgets stay unchanged; this package does not approve the pending common formal 8192-output budget.

## Budget boundary and next run

The latest immutable cumulative history is **16 requests / 296,569 charged tokens / 10,193.483 seconds**. The old aggregate allowance leaves **20 requests / 203,431 charged tokens / 4206.517 seconds**. Unknown usage remains charged. Do not use an older carryover record.

`authorization.json` is deliberately pending for a **new independent 90-minute non-formal full-D validation**, with the previously approved per-test ceilings of 8192 output tokens, 36 requests, and 500,000 total tokens. The new allowance would be separate from preserved historical consumption and therefore needs the user's budget-scope confirmation. Check-only rejects it before model startup while pending. See `NEXT_RUN_PROPOSAL.md`.

Strict structural acceptance is separate from factual/human Gold quality. The old Research body also misread a degree statistic's time period and percentage denominator; no old model output was edited to conceal this.

## Validation and preservation

Exact results are recorded in `validation/` and `HANDOFF.md` after the full regression and installation verification finish. `change_manifest.json`, `before/`, `runtime_manifest.json` and `runtime_source.zip` preserve precise changes and tested source. Existing uncommitted changes and historical run files are retained; no commit/reset or next package launch is performed.
