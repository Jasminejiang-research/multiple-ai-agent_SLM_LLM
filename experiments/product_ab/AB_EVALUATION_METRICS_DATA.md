# A/B Experiment Evaluation Metrics Data Record

**Record date:** 13 September 2026  
**Metric specification:** [`@ai_agent_evaluation_metrics_spec_v2_fast_generation.md`](../../docs/evaluation/@ai_agent_evaluation_metrics_spec_v2_fast_generation.md)  
**Model:** `gemini-2.5-flash`

## 1. Evaluation Scope

| Condition | Architecture | Execution control |
| --- | --- | --- |
| A | Single Agent | Structured proposal generation followed by schema validation, bounded correction, and terminal product checks |
| B | Multi-Agent | Validator, deterministic Supervisor, Research, Strategy, Finance, retrieval, Writer, final Critic, conditional Revision, and Export |

The analysis set comprises one selected execution of each condition for each of two product cases.

| Case | Condition A record | Condition B record |
| --- | --- | --- |
| Berlin restaurant ingredient-waste forecasting SaaS | [`berlin-restaurant-waste-product-ab-v1-20260912/A/`](berlin-restaurant-waste-product-ab-v1-20260912/A/) | [`berlin-restaurant-waste-product-ab-v1-20260912/B/`](berlin-restaurant-waste-product-ab-v1-20260912/B/) |
| AI Tutor for MBA Students — United States | [`mba-ai-tutor-us-product-ab-v1-20260913/A/`](mba-ai-tutor-us-product-ab-v1-20260913/A/) | [`mba-ai-tutor-us-product-b-v2-20260913/B/`](mba-ai-tutor-us-product-b-v2-20260913/B/) |

## 2. Provenance and Calculation Rules

- Terminal status, elapsed time, accounting values, product-acceptance records, correction events, and workflow state were read from `result.json`, `results.json`, and `state.json`.
- Provider token values were summed from `usage_metadata` in the recorded `calls/*.response.json` files.
- A completed execution denotes a selected condition record with a formal terminal product artifact and a recorded elapsed time not exceeding 3,600 seconds.
- Canonical input hashes were calculated as SHA-256 over UTF-8 JSON serialized with sorted keys and compact separators.
- Code-inventory hashes were calculated as SHA-256 over the canonical JSON representation of the file-level `code_sha256` mapping stored in each manifest.
- Full-prompt character counts were calculated from the recorded `contents` field of every request.
- Response-schema byte counts were calculated from the compact UTF-8 JSON serialization of `config.response_schema` for every request.
- Condition-level totals are sums across the two selected case executions. Mean elapsed time is the arithmetic mean across the same two executions.
- The selected United States MBA condition A and condition B records listed above are the authoritative final records. They share the same canonical input hash and code-inventory hash; all reported MBA metrics are computed exclusively from these selected executions.

The Berlin manifest and both selected United States MBA source manifests matched their recorded `manifest_lock.json` SHA-256 values at the time this document was prepared.

## 3. Input, Version, and Execution Records

| Case and source bundle | Recorded order | Harness version | Harness SHA-256 | Input bytes | Canonical input SHA-256 | Code files | Code-inventory SHA-256 |
| --- | --- | --- | --- | ---: | --- | ---: | --- |
| Berlin restaurant ingredient-waste forecasting SaaS | A, B | `product-ab-v3-accepted-per-agent` | `351ac4f23e13108f324202cd36ee7312163992530e8162fc74f61c5b15260848` | 2,588 | `88a52f70d911be871dfd8978c902d072cac3d5135aa9ec58dd9a95cd4256ea0e` | 98 | `62f5919165ba8e2dd05dc8a275eb40f02aa2955e847feb6ef23f026af11cc828` |
| AI Tutor for MBA Students — United States, selected A source | A, B | `product-ab-v3-accepted-per-agent` | `351ac4f23e13108f324202cd36ee7312163992530e8162fc74f61c5b15260848` | 2,781 | `002e59cdaa25158a203a5e9270eaa9a28f2a83574d8cd89a1fe249aa3a4493c6` | 98 | `62f5919165ba8e2dd05dc8a275eb40f02aa2955e847feb6ef23f026af11cc828` |
| AI Tutor for MBA Students — United States, selected B source | B | `product-ab-v3-accepted-per-agent` | `3d9ffeb5dce2f66bf558986ad3fcf48fd8c77261be205eb7c6bc34128bfafda6` | 2,781 | `002e59cdaa25158a203a5e9270eaa9a28f2a83574d8cd89a1fe249aa3a4493c6` | 98 | `62f5919165ba8e2dd05dc8a275eb40f02aa2955e847feb6ef23f026af11cc828` |

## 4. Run-Level Reliability and Resource Accounting

| Case | Condition | Terminal status | Elapsed time (s) | LLM requests | Run-budget retries | Prompt tokens | Candidate tokens | Thought tokens | Total tokens | Model cost (USD) | Web requests | Correction events |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Berlin restaurant ingredient-waste forecasting SaaS | A | `accepted_with_issues` | 54.922 | 3 | 1 | 12,157 | 5,186 | 6,807 | 24,150 | 0.0336296 | 0 | 1 |
| Berlin restaurant ingredient-waste forecasting SaaS | B | `accepted_with_issues` | 433.641 | 16 | 2 | 240,501 | 40,208 | 60,239 | 340,948 | 0.3232678 | 2 | 2 |
| AI Tutor for MBA Students — United States | A | `accepted_with_issues` | 44.891 | 3 | 1 | 12,752 | 6,333 | 3,360 | 22,445 | 0.0280581 | 0 | 1 |
| AI Tutor for MBA Students — United States | B | `accepted_with_issues` | 398.765 | 17 | 3 | 253,216 | 38,248 | 56,614 | 348,078 | 0.3131198 | 2 | 3 |

## 5. Condition-Level Aggregates

| Condition | Selected executions | Completed within 60 min | Completion rate | Total elapsed time (s) | Mean elapsed time (s) | LLM requests | Run-budget retries | Prompt tokens | Candidate tokens | Thought tokens | Total tokens | Model cost (USD) | Web requests | Correction events |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 2 | 2 | 100% | 99.813 | 49.907 | 6 | 2 | 24,909 | 11,519 | 10,167 | 46,595 | 0.0616877 | 0 | 2 |
| B | 2 | 2 | 100% | 832.406 | 416.203 | 33 | 5 | 493,717 | 78,456 | 116,853 | 689,026 | 0.6363876 | 4 | 5 |

## 6. Prompt and Response-Schema Load

| Case | Condition | Recorded calls | Full-prompt characters, total | Full-prompt characters, range per call | Response-schema UTF-8 bytes, total | Response-schema UTF-8 bytes, range per call |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Berlin restaurant ingredient-waste forecasting SaaS | A | 3 | 27,987 | 3,161–19,305 | 6,922 | 924–2,999 |
| Berlin restaurant ingredient-waste forecasting SaaS | B | 16 | 982,178 | 2,895–91,754 | 26,382 | 221–2,510 |
| AI Tutor for MBA Students — United States | A | 3 | 30,430 | 3,186–21,665 | 6,922 | 924–2,999 |
| AI Tutor for MBA Students — United States | B | 17 | 991,764 | 2,920–87,493 | 26,122 | 221–2,510 |

| Condition | Recorded calls | Full-prompt characters, total | Response-schema UTF-8 bytes, total | Provider-reported prompt tokens |
| --- | ---: | ---: | ---: | ---: |
| A | 6 | 58,417 | 13,844 | 24,909 |
| B | 33 | 1,973,942 | 52,504 | 493,717 |

## 7. Condition A Output and Correction Records

| Case | Schema-valid terminal proposal | Markdown characters | Heading count | Recorded correction actor | Correction count |
| --- | --- | ---: | ---: | --- | ---: |
| Berlin restaurant ingredient-waste forecasting SaaS | `true` | 12,736 | 14 | A | 1 |
| AI Tutor for MBA Students — United States | `true` | 15,932 | 14 | A | 1 |

## 8. Condition B Workflow and Output Records

| Case | Completed proposal sections | Section characters | Writer batch checkpoints | Recorded graph nodes | Web sources | RAG documents | Final Critic executed | Revision executed | Citation-check failures | Recorded correction actors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | --- |
| Berlin restaurant ingredient-waste forecasting SaaS | 13 | 16,368 | 4 | 11 | 10 | 3 | `true` | `true` | 6 | Research: 1; Revision: 1 |
| AI Tutor for MBA Students — United States | 13 | 16,708 | 4 | 11 | 10 | 3 | `true` | `true` | 0 | Finance: 1; Writer: 1; Revision: 1 |

The recorded Condition B graph-node set is `critic`, `export`, `finance`, `rag_retrieval`, `research`, `revision`, `seal_writer_recovery`, `strategy`, `supervisor`, `validator`, and `writer`.

| Case | Recorded RAG documents |
| --- | --- |
| Berlin restaurant ingredient-waste forecasting SaaS | `investor_proposal_template.md`; `unit_economics.md`; `tam_sam_som.md` |
| AI Tutor for MBA Students — United States | `investor_proposal_template.md`; `porter_five_forces.md`; `tam_sam_som.md` |

## 9. First-Submission Contract Pass Rates for Condition B

A logical task was counted when it produced a model-generated object governed by a predefined parse, schema, or product-contract check. Deterministic graph nodes were excluded from this denominator. Query planning and financial planning were counted separately from the Research and Finance canonical artifacts because each had its own model call and output contract. The Writer and Revision stages each comprised four predefined batch tasks. A correction request associated with a task records failure of that task's first submission; subsequent correction success does not alter the first-submission result.

| Case | Role or stage | Triggered logical tasks | First submissions passed | First-submission contract pass rate |
| --- | --- | ---: | ---: | ---: |
| Berlin restaurant ingredient-waste forecasting SaaS | Research, including query planning | 2 | 1 | 50.0% |
| Berlin restaurant ingredient-waste forecasting SaaS | Strategy | 1 | 1 | 100.0% |
| Berlin restaurant ingredient-waste forecasting SaaS | Finance, including financial planning | 2 | 2 | 100.0% |
| Berlin restaurant ingredient-waste forecasting SaaS | Writer | 4 | 4 | 100.0% |
| Berlin restaurant ingredient-waste forecasting SaaS | Critic | 1 | 1 | 100.0% |
| Berlin restaurant ingredient-waste forecasting SaaS | Revision | 4 | 3 | 75.0% |
| AI Tutor for MBA Students — United States | Research, including query planning | 2 | 2 | 100.0% |
| AI Tutor for MBA Students — United States | Strategy | 1 | 1 | 100.0% |
| AI Tutor for MBA Students — United States | Finance, including financial planning | 2 | 1 | 50.0% |
| AI Tutor for MBA Students — United States | Writer | 4 | 3 | 75.0% |
| AI Tutor for MBA Students — United States | Critic | 1 | 1 | 100.0% |
| AI Tutor for MBA Students — United States | Revision | 4 | 3 | 75.0% |

| Role or stage | Triggered logical tasks, both cases | First submissions passed | First-submission contract pass rate |
| --- | ---: | ---: | ---: |
| Research, including query planning | 4 | 3 | 75.0% |
| Strategy | 2 | 2 | 100.0% |
| Finance, including financial planning | 4 | 3 | 75.0% |
| Writer | 8 | 7 | 87.5% |
| Critic | 2 | 2 | 100.0% |
| Revision | 8 | 6 | 75.0% |
| **All model-generated logical tasks** | **28** | **23** | **82.1%** |

The first-submission failures recorded for Berlin were the Research canonical artifact and Revision batch 1. The first-submission failures recorded for the United States MBA case were the Finance canonical artifact, Writer batch 1, and Revision batch 3.

## 10. Condition B Handoff Ledger

The prescribed handoff denominator was the ten directed edges connecting the eleven recorded graph nodes. A handoff was counted as completed when the event stream recorded the upstream and downstream nodes in the prescribed order and the persisted run state contained the upstream artifact required by the downstream node. Retransmissions and model-level correction requests did not add handoffs to the denominator.

| Prescribed workflow edge | Berlin | MBA — United States |
| --- | --- | --- |
| Validator → Supervisor | Completed | Completed |
| Supervisor → Research | Completed | Completed |
| Research → Strategy | Completed | Completed |
| Strategy → Finance | Completed | Completed |
| Finance → RAG retrieval | Completed | Completed |
| RAG retrieval → Writer | Completed | Completed |
| Writer → Seal Writer Recovery | Completed | Completed |
| Seal Writer Recovery → Critic | Completed | Completed |
| Critic → Revision | Completed | Completed |
| Revision → Export | Completed | Completed |

| Case | Prescribed handoffs | Completed handoffs | Handoff success rate |
| --- | ---: | ---: | ---: |
| Berlin restaurant ingredient-waste forecasting SaaS | 10 | 10 | 100.0% |
| AI Tutor for MBA Students — United States | 10 | 10 | 100.0% |
| **Both cases** | **20** | **20** | **100.0%** |

## 11. Scheduling and Review Token Share for Condition B

The metric-specification numerator comprises Supervisor and Critic model-call tokens. The evaluated Supervisor was deterministic and issued no model request. Revision calls are reported separately and are not included in the scheduling-and-review numerator.

| Case | Condition B total tokens | Supervisor tokens | Critic prompt tokens | Critic candidate tokens | Critic thought tokens | Critic total tokens | Scheduling and review token share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Berlin restaurant ingredient-waste forecasting SaaS | 340,948 | 0 | 18,110 | 1,727 | 9,761 | 29,598 | 8.68% |
| AI Tutor for MBA Students — United States | 348,078 | 0 | 19,562 | 939 | 7,284 | 27,785 | 7.98% |
| **Both cases** | **689,026** | **0** | **37,672** | **2,666** | **17,045** | **57,383** | **8.33%** |

| Case | Revision requests | Revision prompt tokens | Revision candidate tokens | Revision thought tokens | Revision total tokens | Revision share of Condition B tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Berlin restaurant ingredient-waste forecasting SaaS | 5 | 97,218 | 17,522 | 23,754 | 138,494 | 40.62% |
| AI Tutor for MBA Students — United States | 5 | 98,637 | 14,244 | 20,005 | 132,886 | 38.18% |
| **Both cases** | **10** | **195,855** | **31,766** | **43,759** | **271,380** | **39.39%** |

## 12. Condition B Critic and Revision Records

| Case | Critic overall score | Critic issues | Severity distribution | Must-fix entries | Revision applied | Applied-critique summary entries | Recorded unresolved issues after revision | Terminal acceptance status |
| --- | ---: | ---: | --- | ---: | --- | ---: | ---: | --- |
| Berlin restaurant ingredient-waste forecasting SaaS | 3.0 | 12 | Critical: 4; high: 4; medium: 4 | 6 | `true` | 5 | 8 | `accepted_with_issues` |
| AI Tutor for MBA Students — United States | 4.0 | 7 | High: 4; medium: 3 | 4 | `true` | 3 | 6 | `accepted_with_issues` |

No post-revision semantic Critic call was recorded for either Condition B execution. The issue registers below therefore preserve the pre-revision Critic output, the Revision node's applied-critique summaries, and the unresolved issues recorded by that node; they do not constitute a second semantic adjudication.

### Berlin restaurant ingredient-waste forecasting SaaS

| # | Section | Severity | Issue type | Recorded description |
| ---: | --- | --- | --- | --- |
| 1 | Executive Summary | High | `missing_evidence` | Key regulatory and market-trend claims had `needs_validation` status and empty claim-level `source_ids`; critical sources were marked as unknown quality. |
| 2 | Problem | High | `unsupported_market_claim` | Regulatory targets and annual food-waste volume claims had `needs_validation` status and empty claim-level `source_ids`; cited sources were marked as unknown quality. |
| 3 | Target Customer | Medium | `unclear_customer` | Restaurant-trend and smaller-outlet claims had `needs_validation` status and empty claim-level `source_ids`; one customer source was marked as unknown quality. |
| 4 | Market Opportunity | High | `unsupported_market_claim` | Regulatory, tourism, and digital-adoption claims lacked claim-level source IDs; several sources were marked as unknown quality; TAM, SAM, and SOM were stated as unsupported. |
| 5 | Solution | Critical | `logic_gap` | Product inputs, forecast horizon, integration requirements, operating workflow, and differentiation were undefined assumptions. |
| 6 | Value Proposition | Medium | `missing_evidence` | A food-waste reduction target claim relied on a source marked as unknown quality. |
| 7 | Competitor Analysis | Medium | `missing_evidence` | Competitor claims relied on sources marked as unknown quality. |
| 8 | Business Model | Critical | `financial_inconsistency` | Pricing, contract terms, sales model, customer counts, costs, and margins were unvalidated assumptions. |
| 9 | Go-to-Market Strategy | Critical | `weak_gtm` | Target segments, pilots, campaigns, and partnerships were based on unvalidated assumptions. |
| 10 | Financial Assumptions | Critical | `financial_inconsistency` | Pricing, acquisition, operating-cost, revenue, unit-economics, and break-even values were not quantified. |
| 11 | Risks and Mitigations | Medium | `missing_evidence` | Competitive-risk and small-restaurant claims relied on sources marked as unknown quality; mitigations were recorded at a high level. |
| 12 | General | High | `missing_evidence` | Several institutional and industry sources were marked as unknown quality in the source metadata. |

The Revision node recorded five applied-critique summary entries: source IDs were added where direct evidence was identified; selected `needs_validation` claims were changed to `sourced_fact`; unsupported claim IDs were removed; unsupported prose anchors were removed; and unsupported TAM, SAM, and SOM quantification was retained as such.

The Revision node recorded eight unresolved matters: Berlin-specific waste scale and willingness to pay; product definition and integration requirements; a quantitative financial model; Germany's reported annual food-waste volume; the demand-forecasting recommendation; smaller-outlet capital and training constraints; Germany's reported overnight-stay count; and unknown-quality sources affecting selected claims.

### AI Tutor for MBA Students — United States

| # | Section | Severity | Issue type | Recorded description |
| ---: | --- | --- | --- | --- |
| 1 | Problem | High | `unclear_customer` | The precise unmet needs, frequency, urgency, and willingness to pay of United States MBA students were unquantified and unsupported. |
| 2 | Market Opportunity | High | `unsupported_market_claim` | United States MBA-specific TAM, SAM, and SOM values were unquantified and explicitly identified as unsupported assumptions. |
| 3 | Solution | High | `logic_gap` | Product features, delivery model, pedagogical approach, and differentiation were undefined assumptions. |
| 4 | Financial Assumptions | High | `financial_inconsistency` | Pricing, conversion, customer counts, costs, margins, CAC, CLTV, and a quantitative financial model were absent. |
| 5 | Go-to-Market Strategy | Medium | `weak_gtm` | Engagement channels lacked concrete acquisition logic, budgets, and expected conversion rates. |
| 6 | General | Medium | `missing_evidence` | Several market, customer, and competitor claims relied on sources marked as unknown quality. |
| 7 | Risks and Mitigations | Medium | `logic_gap` | United States higher-education AI regulation and accreditation requirements were unknown and therefore unquantified. |

The Revision node recorded three applied-critique summary entries: customer-demand claims were reclassified to assumptions or unsupported; market-trend claims relying on unknown-quality sources were reclassified as assumptions; and unsupported TAM, SAM, and SOM claims remained explicitly unsupported.

The Revision node recorded six unresolved matters: customer validation; United States MBA-specific market sizing; product definition and pedagogy; the business model and quantitative financial model; operational go-to-market detail; and United States higher-education AI regulation or accreditation requirements.

## 13. Data Files

| Data group | Repository record |
| --- | --- |
| Berlin execution manifest and event stream | [`berlin-restaurant-waste-product-ab-v1-20260912/`](berlin-restaurant-waste-product-ab-v1-20260912/) |
| Berlin derived metrics | [`berlin-restaurant-waste-product-ab-v1-20260912-analysis/METRICS.json`](berlin-restaurant-waste-product-ab-v1-20260912-analysis/METRICS.json) |
| MBA — United States selected A execution manifest and event stream | [`mba-ai-tutor-us-product-ab-v1-20260913/`](mba-ai-tutor-us-product-ab-v1-20260913/) |
| MBA — United States selected A derived metrics | [`mba-ai-tutor-us-product-ab-v1-20260913-analysis/METRICS.json`](mba-ai-tutor-us-product-ab-v1-20260913-analysis/METRICS.json) |
| MBA — United States selected B execution manifest and event stream | [`mba-ai-tutor-us-product-b-v2-20260913/`](mba-ai-tutor-us-product-b-v2-20260913/) |
| MBA — United States selected B derived metrics | [`mba-ai-tutor-us-product-b-v2-20260913-analysis/METRICS.json`](mba-ai-tutor-us-product-b-v2-20260913-analysis/METRICS.json) |
