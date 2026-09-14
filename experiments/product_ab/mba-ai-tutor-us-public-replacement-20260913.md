# AI Tutor for MBA Students — United States Replacement Record

## Outcome

The public A/B plan and audit artifacts for the AI Tutor for MBA Students case were replaced in place with outputs bounded to the United States. Both formal outputs were accepted under the one-correction product policy with unresolved issues recorded separately in their audit reports.

## Source runs

- A source run: `docs/comparisons/mba-ai-tutor-us-product-ab-v1-20260913`
- B source run: `docs/comparisons/mba-ai-tutor-us-product-b-v2-20260913`
- The initial B attempt in the A/B source run was preserved as a hard budget-admission failure.
- The approved B-only rerun used the same frozen input with the corrected 480,000-token B ceiling.

## Replaced public artifacts

- `docs/comparisons/mba-ai-tutor-a-separated-v1-20260912/AI_Tutor_for_MBA_Students_A_Plan.md`
- `docs/comparisons/mba-ai-tutor-a-separated-v1-20260912/AI_Tutor_for_MBA_Students_A_Audit.md`
- `docs/comparisons/mba-ai-tutor-b-separated-v1-20260912/2026-09-12_ai_tutor_for_mba_students_product_ab_mba_ai_tutor_product_b_v2_20260912_b.md`
- `docs/comparisons/mba-ai-tutor-b-separated-v1-20260912/2026-09-12_ai_tutor_for_mba_students_product_ab_mba_ai_tutor_product_b_v2_20260912_b_audit.md`

All four post-copy SHA-256 hashes matched their respective new source artifacts.

## Verification

- A: 14 formal sections, 13 United States references, zero China references, zero Han characters, and zero prohibited audit markers.
- B: 13 of 13 formal sections, 16 United States references, zero China references, zero Han characters, and zero prohibited audit markers.
- B completed Validator, Supervisor, two live Web searches, Research, Strategy, Finance, RAG retrieval, Writer, Critic, Revision, and Export.
- The B structured audit JSON parsed successfully with 13 section records and 13 registered sources.
- The four prior public artifacts were backed up under `docs/comparisons/mba-ai-tutor-public-backup-before-us-replacement-20260913`.

## Usage and cost

- Successful A: 22,445 tokens; USD 0.028058 model cost.
- Successful B rerun: 348,078 tokens; USD 0.313120 model cost; two Web searches with USD 0.016 upper-bound search cost.
- Initial A/B attempt, including the failed B execution: USD 0.368451 model cost and USD 0.016 upper-bound search cost.
- Total incurred across the initial attempt and approved B rerun: USD 0.681571 model cost plus USD 0.032 upper-bound search cost, or USD 0.713571 combined upper bound.

This remains a one-case exploratory comparison and does not support statistical or causal claims of architecture superiority.
