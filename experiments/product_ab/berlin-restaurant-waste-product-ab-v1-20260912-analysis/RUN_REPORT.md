# Berlin Restaurant Waste Forecasting SaaS — Product A/B Run Report

## Outcome

The frozen one-case, one-run-per-arm exploratory product test completed successfully through both native product paths. Both outputs were accepted under the one-correction policy with unresolved issues. This run is suitable for inspecting product behavior, but it does not support statistical, causal, or general claims that either architecture is superior.

## Frozen test conditions

- Case: Berlin Restaurant Ingredient Waste Forecasting SaaS, positioned as a conventional forecasting product for a traditional industry.
- Input language: Chinese; required output language: English.
- No preset case evidence, competitors, financial figures, or manually supplied financial model.
- Execution order: A, then B.
- One paid execution per arm; no resume, repair, output editing, or automatic rerun.
- A used the native single-agent proposal route and one shared correction opportunity.
- B used Validator, Supervisor, two live Web searches, Research, Strategy, Finance, RAG retrieval, four Writer batches, Critic, Revision, and Export. Research and Revision each consumed one correction opportunity.

## Results

| Measure | A | B |
| --- | ---: | ---: |
| Product status | `accepted_with_issues` | `accepted_with_issues` |
| Elapsed time | 54.922 s | 433.641 s |
| Model responses | 3 | 16 |
| Tokens | 24,150 | 340,948 |
| Model cost | USD 0.033630 | USD 0.323268 |
| Plan characters | 12,854 | 16,014 |
| Plan words | 1,722 | 2,171 |
| Formal sections | 14 | 13 of 13 |
| Live Web searches/results | 0 / 0 | 2 / 10 |
| RAG documents | 0 | 3 |

Combined model usage was 365,098 tokens across 19 requests at USD 0.356897. The Web-search pay-as-you-go upper bound was USD 0.016, giving a combined upper-bound cost of USD 0.372897.

## End-to-end and RAG verification

B reached Export after completing every required graph node: Validator, Supervisor, Research, Strategy, Finance, RAG retrieval, Writer, Critic, Revision, and Export. Its evidence mode was `rag_and_web`. RAG returned three chunks from the generic documents `investor_proposal_template.md`, `unit_economics.md`, and `tam_sam_som.md`; the two live searches returned ten Web results. The run did not use a frozen case dossier.

## Output-policy verification

Both formal plans contain zero Chinese ideographs. Neither formal plan contains the acceptance status, correction log, confidence labels, bracketed `NEEDS_VALIDATION` or `UNSUPPORTED` markers, Source IDs lists, internal `web-*` or `source_*` identifiers, or unresolved financial placeholders. B retains all 13 required sections, including Appendix. A and B each have a separate audit report, and B's structured audit JSON parses successfully with 13 section records and 13 registered sources.

The plan/audit separation is technically improved but not semantically complete. B's Appendix still summarizes unsupported claims, unverified assumptions, and items needing human review in natural language. Those are audit-like statements even though the prohibited metadata and IDs are absent. This is a retained product defect, not a modification made during analysis.

## Accepted issues

### A

A exhausted its single correction after the model supplied numeric financial projections without a financial-model ledger. The formal plan still contains illustrative ranges such as a 70–85% gross margin and a 24–36 month break-even expectation. These are not grounded in a generated quantitative scenario and are recorded in the separate A audit report.

### B

B correctly kept finance qualitative because the frozen input supplied no pricing, customer-count, cost, or market-size parameters. Consequently, it did not produce a quantitative financial model. Its audit also records unresolved evidence-provenance problems: six citation-shape failures, ten Web sources without publication dates, unverified regulatory/customer claims that survived the final revision, and generic-source quality concerns. The RAG path ran, but the retrieval record indicates that evidence collection was budget-limited.

## Interpretation

For this single run, B used the intended multi-agent, Web, and RAG architecture and produced a longer complete plan, but it was substantially slower and more token-intensive. Neither output achieved a fully validated quantitative financial section. B also retained citation-quality and semantic audit-leakage defects. These observations describe this artifact pair only.
