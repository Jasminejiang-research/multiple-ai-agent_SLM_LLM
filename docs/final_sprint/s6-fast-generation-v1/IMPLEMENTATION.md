# S6 implementation

S6 installs one shared compact generation protocol for A–D while leaving the strict canonical contract local and versioned. No S5 formal run or real provider request was made.

## Installed behavior

- `compact-generation-v1-s6`, `compact-json-wire-v1-s6`, `deterministic-role-view-v1-s6`, and `review-run-v2-s6-compact` are explicit versions. Legacy `body-then-grounding-v1` remains selectable and historical artifacts are not migrated.
- Single/Writer still produce all 13 canonical sections. Research, Strategy, Finance, role Critics, final Critic, and patch Revision share provider-neutral strict JSON DTOs.
- Each business role produces body text and claims in one response. Local deterministic expansion restores source ID, chunk, exact quote, line range, snapshot hash, artifact version, finance IDs, and lineage before canonical validation.
- Role views contain only selected brief fields, frozen evidence text, effective upstream claim capsules, unresolved code-owned state, and compact finance tables. They contain no conversation history, previous long Critic prose, repeated source metadata, or model-generated summary.
- Finance values are code-owned. Per the user's conflict resolution, AI education preserves 21 frozen results and Intelligent ring preserves 27; Finance only explains assumptions, scenarios, risk, and decision meaning.
- Critic returns a fixed 0–4 vector, PASS/FAIL, and at most three issues. Only high/critical issues trigger one Revision; only critical is blocking; the 0–10 score is diagnostic.
- Revision accepts only targeted claim/field patches, records before/after hashes and the patch, refuses unknown targets and a second semantic revision, and preserves `unverified_after_revision`.
- Mechanical repair is limited to one complete JSON extraction, extra-field removal, and frozen enum aliases. All changes are journaled. Missing sections, unknown IDs, invalid finance, unresolved parse errors, and improperly sourced factual claims remain hard failures.
- The shared clocks are MVP30 at 1800 seconds and ValidPlan60/run stop at 3600 seconds. Per-role input/output/time targets are frozen in `PROTOCOL_MANIFEST.json` and enforced/observed by the common runtime.
- S4 events, manifest projection, CSV export, and UI now expose MVP30, ValidPlan60, artifact class, prompt/schema burden, stage latency, mechanical repair, and deterministic diffs while continuing to read old records.

## Main files

- DTOs: `schemas/compact_wire.py`
- Views, expansion, repair, patch, protocol snapshot: `workflow/compact_protocol.py`
- Dispatch and one-response orchestration: `workflow/contract_generation.py`, `workflow/review_runtime.py`
- Gate/config/graph: `schemas/review.py`, `workflow/review_config.py`, `workflow/review_graph.py`
- Evaluation compatibility: `evaluation/s4_runner.py`, `evaluation/s4_metrics.py`, `evaluation/s4_export.py`, `evaluation/s4_ui.py`
- Granite candidate config: `slm/configs/granite_preflight_compact_s6.json`

The complete implementation and authority hashes are in `VERSION_MANIFEST.json`. Recoverable pre-change copies and hashes are under `before/` and `before_inventory.json`.
