# Product A/B Experimental Materials

This directory preserves the plans, audit documents, execution traces, and derived records for the two product-level experiments conducted with Gemini 2.5 Flash. Condition A uses the single-agent pathway; Condition B uses the multi-agent pathway with final Critic review and conditional revision. No unexecuted experimental condition is represented as an observed result.

The governing metric definitions are provided in [`docs/evaluation/@ai_agent_evaluation_metrics_spec_v2_fast_generation.md`](../../docs/evaluation/@ai_agent_evaluation_metrics_spec_v2_fast_generation.md). The executable A/B harness and reduction utilities are located in [`tools/`](../../tools/), while the broader metric, resource, export, and statistical modules are located in [`evaluation/`](../../evaluation/).

## Berlin restaurant ingredient-waste forecasting SaaS

- Condition A plan: [`berlin-restaurant-waste-product-ab-v1-20260912/A/proposal.md`](berlin-restaurant-waste-product-ab-v1-20260912/A/proposal.md)
- Condition A audit: [`berlin-restaurant-waste-product-ab-v1-20260912/A/audit_report.md`](berlin-restaurant-waste-product-ab-v1-20260912/A/audit_report.md)
- Condition B plan: [`berlin-restaurant-waste-product-ab-v1-20260912/B/2026-09-12_berlin_restaurant_ingredient_waste_forecasting_saas_product_ab_berlin_restaurant_waste_product_ab_v1_20260912_b.md`](berlin-restaurant-waste-product-ab-v1-20260912/B/2026-09-12_berlin_restaurant_ingredient_waste_forecasting_saas_product_ab_berlin_restaurant_waste_product_ab_v1_20260912_b.md)
- Condition B audit: [`berlin-restaurant-waste-product-ab-v1-20260912/B/2026-09-12_berlin_restaurant_ingredient_waste_forecasting_saas_product_ab_berlin_restaurant_waste_product_ab_v1_20260912_b_audit.md`](berlin-restaurant-waste-product-ab-v1-20260912/B/2026-09-12_berlin_restaurant_ingredient_waste_forecasting_saas_product_ab_berlin_restaurant_waste_product_ab_v1_20260912_b_audit.md)
- Execution evidence: [`berlin-restaurant-waste-product-ab-v1-20260912/`](berlin-restaurant-waste-product-ab-v1-20260912/)
- Derived records: [`berlin-restaurant-waste-product-ab-v1-20260912-analysis/`](berlin-restaurant-waste-product-ab-v1-20260912-analysis/)

## AI Tutor for MBA Students — United States

- Frozen input: [`inputs/mba-ai-tutor-us-input-v1-20260913.json`](inputs/mba-ai-tutor-us-input-v1-20260913.json)
- Experiment protocol: [`mba-ai-tutor-us-v1-PROTOCOL-20260913.md`](mba-ai-tutor-us-v1-PROTOCOL-20260913.md)
- Condition A plan: [`mba-ai-tutor-a-separated-v1-20260912/AI_Tutor_for_MBA_Students_A_Plan.md`](mba-ai-tutor-a-separated-v1-20260912/AI_Tutor_for_MBA_Students_A_Plan.md)
- Condition A audit: [`mba-ai-tutor-a-separated-v1-20260912/AI_Tutor_for_MBA_Students_A_Audit.md`](mba-ai-tutor-a-separated-v1-20260912/AI_Tutor_for_MBA_Students_A_Audit.md)
- Condition B plan: [`mba-ai-tutor-b-separated-v1-20260912/2026-09-12_ai_tutor_for_mba_students_product_ab_mba_ai_tutor_product_b_v2_20260912_b.md`](mba-ai-tutor-b-separated-v1-20260912/2026-09-12_ai_tutor_for_mba_students_product_ab_mba_ai_tutor_product_b_v2_20260912_b.md)
- Condition B audit: [`mba-ai-tutor-b-separated-v1-20260912/2026-09-12_ai_tutor_for_mba_students_product_ab_mba_ai_tutor_product_b_v2_20260912_b_audit.md`](mba-ai-tutor-b-separated-v1-20260912/2026-09-12_ai_tutor_for_mba_students_product_ab_mba_ai_tutor_product_b_v2_20260912_b_audit.md)
- Condition A source execution: [`mba-ai-tutor-us-product-ab-v1-20260913/`](mba-ai-tutor-us-product-ab-v1-20260913/)
- Condition A derived records: [`mba-ai-tutor-us-product-ab-v1-20260913-analysis/`](mba-ai-tutor-us-product-ab-v1-20260913-analysis/)
- Condition B source execution: [`mba-ai-tutor-us-product-b-v2-20260913/`](mba-ai-tutor-us-product-b-v2-20260913/)
- Condition B derived records: [`mba-ai-tutor-us-product-b-v2-20260913-analysis/`](mba-ai-tutor-us-product-b-v2-20260913-analysis/)

The separated A and B plan/audit files are presentation copies of the authoritative final outputs. Paper reporting uses only the selected Condition A and Condition B source executions and derived records listed above.

## Record types

| Record | Purpose |
| --- | --- |
| `manifest.json` and `manifest_lock.json` | Frozen input, model, order, budget, and source-code identity |
| `events.jsonl` | Append-only execution events and timing/accounting observations |
| `calls/*.request.json` and `calls/*.response.json` | Provider-call inputs and raw responses used for traceability |
| `nodes/*.json` and `writer_checkpoints/` | Multi-agent intermediate artifacts and recovery checkpoints |
| `state.json`, `result.json`, and `results.json` | Condition-level and run-level terminal records |
| `METRICS.json` and `RUN_REPORT.md` | Deterministically derived evaluation records |
| `*_audit.md` and `audit_report.md` | Audit material stored separately from the user-facing plan |

The presence of a record in this directory establishes provenance; it does not, by itself, constitute an interpretation of experimental performance. Statistical and qualitative conclusions belong in the associated academic report.
