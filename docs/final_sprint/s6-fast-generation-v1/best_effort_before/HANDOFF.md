# S6 handoff

## Outcome

The S6 common compact protocol implementation and offline acceptance are complete. A–D, both cases, all roles/Critics, both model identities, 32K context, Tier 1, comparison plan, hard evidence/finance/terminal gates, and one-revision ceiling were preserved. The user-confirmed case-specific finance contract is 21 results for AI education and 27 for Intelligent ring.

The authorized real D preflight was executed and ended `no_go`. Warmup and 32K CPU context passed, but Research, Research Critic, Finance, and Writer each reached its frozen compact role output cap on both the initial and sole structure-repair call; every response ended with `finish_reason=length` and failed strict structure validation. The complete D smoke was therefore not run. Because the required D gate did not pass, the already-approved Gemini A/B/C smokes were not called and no joint refreeze occurred. No user history, prior run result, uncommitted work, or lease was deleted or overwritten. Formal S5 was not executed.

On 2026-09-07, the blocked process/lease state was reconciled. PID 17860 is the Ollama Desktop parent and PID 18776 its later-created `ollama.exe serve` child; neither matches the project-owned S3 PID 24092 or its native creation identity, so both were left running. PID 24092 is absent. The old 137-byte `inflight_or_unknown` lease was moved intact to `data/granite_endpoint_leases/archive/2026-09-07/`; its SHA-256 remains `c185cb7770cf89f12a168ed27c9d09c6000c9cb38df43198de8cac93bd6f475a`. Unknown usage remains charged/unknown: there was no deletion or refund. Full evidence is in `PROCESS_LEASE_RECONCILIATION.json`.

The bounded D proposal in `D_PREFLIGHT_PROPOSAL.json` was explicitly authorized in `D_PREFLIGHT_AUTHORIZATION.json`: one non-formal `ai_education × D` preflight, Granite H Micro CPU/32K, at most 3,600 active seconds, 18 physical requests, and 160,000 charged or conservatively reserved total tokens. Per-call output was at most 1,800 tokens and lower role caps applied. Attempt 01 was a zero-call adapter failure. Attempt 02 used 2 calls/12,979 tokens to pass warmup and context, then failed before component dispatch. Attempt 03 reused those passed phases and restored their calls/tokens/353.25 seconds into one cumulative ledger rather than rerunning them.

The final cumulative D result used 10/18 requests, 30,817/160,000 tokens and 1,233.531/3,600 active seconds. Known usage was 24,738 prompt plus 6,079 output tokens. Each component used exactly two calls: initial plus one structure repair, with no transport retry, semantic revision, third attempt, or formal execution. Combined resources passed over 242 samples; minimum available RAM was 4,857,692,160 bytes, observed model VRAM was zero, and the maximum sampling gap was 5.422 seconds. Project-owned PID 9660 was terminated by exact identity; post-run listener count on 11434 and active lease count were both zero. The immutable raw result and the derived exact accounting are in `real_preflight_d_ai_education_03/probe/result.json` and `D_PREFLIGHT_ATTEMPT_03.json`.

The user delegated the Gemini smoke approval after disclosure of calls and maximum spend. `GEMINI_SMOKE_APPROVAL.json` approves only three non-formal AI education A/B/C smokes on `gemini-2.5-flash` Standard with no paid tools: normal PASS path 14 calls, all semantic-revision path 19 calls, absolute stop at 54 calls and 480,000 total tokens. The normal planning envelope is about $0.03846 and the deliberately conservative maximum is $1.20. No Gemini call started because the preceding D gate failed.

## Evidence paths

- Protocol snapshot: `PROTOCOL_MANIFEST.json`
- File/authority/test hashes: `VERSION_MANIFEST.json`
- Implementation description: `IMPLEMENTATION.md`
- Tests and rehearsal: `VALIDATION.md`, `validation/`, `mock_rehearsal_final/`
- Real-call/lease state: `REAL_CALL_STATUS.json`
- Process/lease reconciliation: `PROCESS_LEASE_RECONCILIATION.json`
- Proposed D authorization boundary: `D_PREFLIGHT_PROPOSAL.json`
- D authorization: `D_PREFLIGHT_AUTHORIZATION.json`
- Preserved D attempts: `D_PREFLIGHT_ATTEMPT_01.json`, `D_PREFLIGHT_ATTEMPT_02.json`, `D_PREFLIGHT_ATTEMPT_03.json`, `real_preflight_d_ai_education_01/`, `real_preflight_d_ai_education_02/`, `real_preflight_d_ai_education_03/`
- Preflight fix hashes and regression logs: `D_PREFLIGHT_FIX_MANIFEST.json`
- Gemini smoke spend approval: `GEMINI_SMOKE_APPROVAL.json`
- Recoverability: `before_inventory.json`, `before/`
- Next S5 dry-run manifest: `next_s5_entry/` (formal 0/8, deliberately not frozen or executable)

## Remaining blockers

1. D is a real-model `no_go`: all tested compact role outputs truncated at their frozen role caps. Raising role/output caps, changing Granite/model, or altering the experiment/budget scope requires user confirmation.
2. Gemini spend remains approved for the three bounded non-formal smokes, but the required prior D gate failed, so A/B/C smoke evidence remains unrun.
3. Common configuration cannot be jointly frozen until both endpoint smoke gates pass. `next_s5_entry/freeze.json` remains pending and S5 must not start before a future approved resolution, both real smoke gates, and a passing `check-freeze`.

## Next package entry

Do not enter S5 from the present state. The next decision is S6/D scope resolution: obtain explicit direction before changing the frozen role caps, the Granite model, or any experiment/budget boundary. If an approved D resolution later passes, execute the already-bounded Gemini A/B/C smokes, jointly freeze the common S6 protocol and all eight slots, rerun `evaluation.s4 check-freeze`, and only then await explicit authorization for formal S5. Do not mix prior protocol runs into that matrix.
