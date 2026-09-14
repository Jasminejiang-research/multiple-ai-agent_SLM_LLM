# AI Tutor for MBA Students — United States A/B Product Protocol

## Objective

Run one exploratory A/B product comparison for the AI Tutor for MBA Students case with the United States as the sole geographic scope, then replace the four existing public MBA case artifacts (A plan, A audit, B plan, B audit) with the newly generated outputs. Preserve the immutable new run directory and the historical original run directories.

## Frozen input and controlled change

- Frozen input: `docs/comparisons/mba-ai-tutor-us-input-v1-20260913.json`.
- Compared with the previous MBA case, the only substantive case change is geography from unspecified/global to United States only.
- The complete mandatory product field set is supplied to both arms.
- Unknown problem details, features, commercial parameters and financial figures remain explicitly unspecified.
- No preset case, case whitelist, prewritten evidence pack, named competitor list or manual financial model is supplied.

## Arms

- A: native single-agent product path, including structured proposal generation, finance handling, one shared correction opportunity, formal-plan export and separate audit export.
- B: native controlled multi-agent path: Validator, Supervisor and dynamic search planning, two live Web searches, Research, Strategy, Finance, generic knowledge-base RAG retrieval, all Writer batches, Critic, all Revision batches, Export, formal-plan export and separate structured audit export.

## Output and acceptance rules

- Both formal plans must be English regardless of the input-language request.
- A has one correction opportunity total.
- Each B agent has one correction opportunity; Writer and Revision each share one opportunity across their batches.
- After an exhausted correction, unresolved non-hard issues are recorded in the audit and the formal output is accepted rather than labeled a draft.
- Authentication, network, accounting, complete-structure, wrong-final-language and hard-budget failures remain hard stops.
- Audit metadata, confidence labels, evidence-state tags, internal source IDs and correction logs must not appear in formal plans; Appendix must remain substantive and must not be deleted.

## Execution controls

- Run order: A then B; seed: 20260913.
- Independent experimental unit: one generated plan per arm for the same frozen brief.
- Replication: one run per arm; results are exploratory only.
- A token ceiling: 240,000; initial B token ceiling: 420,000; combined token ceiling: 540,000.
- Maximum model requests: 28 combined and 24 per arm.
- Model-cost guard: USD 0.80 combined.
- Live Web searches: two, with a USD 0.016 pay-as-you-go upper bound.
- Wall-clock ceiling: 2,400 seconds per arm.
- No source, prompt, input, budget, output, repair or retry changes after preparation.
- No automatic paid rerun. A failed arm is preserved and audited.

## Post-run budget correction

The first B execution was correctly stopped before a Revision dispatch because its conservative projected arm usage was 421,678 tokens against the initial 420,000-token ceiling. The completed usage at that point was 343,121 tokens. This showed that the prior B allowance did not cover the executor's required worst-case reservation even though the combined token and currency caps still had ample room. The reusable executor and its regression expectations were therefore raised to a 480,000-token B ceiling while retaining the 540,000 combined ceiling, 28-request ceiling and USD 0.80 currency cap. The failed run remains immutable, and no paid rerun is authorized by this correction alone.

## Replacement targets after successful verification

- `docs/comparisons/mba-ai-tutor-a-separated-v1-20260912/AI_Tutor_for_MBA_Students_A_Plan.md`
- `docs/comparisons/mba-ai-tutor-a-separated-v1-20260912/AI_Tutor_for_MBA_Students_A_Audit.md`
- `docs/comparisons/mba-ai-tutor-b-separated-v1-20260912/2026-09-12_ai_tutor_for_mba_students_product_ab_mba_ai_tutor_product_b_v2_20260912_b.md`
- `docs/comparisons/mba-ai-tutor-b-separated-v1-20260912/2026-09-12_ai_tutor_for_mba_students_product_ab_mba_ai_tutor_product_b_v2_20260912_b_audit.md`

Replacement occurs only after the new run completes, paths are verified to remain within `docs/comparisons`, formal plans pass the required English and plan/audit separation checks, and the source outputs are confirmed to be the new United States case. Historical raw run directories remain recoverable.
