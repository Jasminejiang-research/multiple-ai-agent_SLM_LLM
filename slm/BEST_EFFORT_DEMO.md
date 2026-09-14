# SLM best-effort demo

`slm_best_effort_demo` is an independent, non-formal product mode. It does not modify, implement, replace, or produce an A–D experimental condition.

It runs Research, Strategy, Finance, Writer, and one advisory Critic after each role. Critic responses and scores are persisted, but failure, timeout, or a low score is never a semantic quality gate and never prevents deterministic plan assembly or export. There is no semantic revision loop. If a transport timeout leaves a local request's completion unknown, the safety gate stops additional physical dispatches to avoid overlap; remaining roles are recorded as not run and the code path still assembles all 13 headings with fixed placeholders.

The transport is deliberately minimal: one text field for generators and one score plus short issues field for Critics. Writer is asked for the fixed 13 headings with one short sentence per heading. The assembler preserves available Writer text, removes unknown evidence IDs from the display copy, labels uncited text `assumption/unsupported`, inserts the fixed Chinese placeholder `信息不足，待验证` for missing sections, and overwrites the financial section with every case-specific value produced by the existing deterministic finance contract.

Every export is visibly labelled `LOW QUALITY / NON-FORMAL / NOT ELIGIBLE FOR C-D COMPARISON`. Raw provider responses, diagnostics, role results, Critic results, cumulative budget, resource samples, and process cleanup evidence are retained alongside the Markdown/JSON plan.
