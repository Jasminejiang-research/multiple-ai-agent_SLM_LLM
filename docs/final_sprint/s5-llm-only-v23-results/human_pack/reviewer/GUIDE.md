# Human review instructions

Read one anonymous proposal at a time. Complete the six dimensions (integer 1–5),
each rationale, reviewer and date in ratings.csv. Do not compare adjacent outputs.
Use the frozen rubric formula (the documented Example A correction is 88.75).
Record rating/audit minutes; these are workflow planning records, not paper outcomes.

Gold review is a second phase after ratings. The coordinator provides unique final
outputs for a single shared ledger audit; hidden rating repeats are not new runs or
additional Gold audits. All visible candidate rows are initially UNJUDGED.

Review every section, its prose, declared claims, premises and financial rows. The
extractor is only a locator. Add omitted material statements; split compound claims
into atomic rows. Mark decision_critical yes/no and atomic_reviewed yes. For semantic
duplicates within the SAME output, set duplicate_of to its candidate ID and preserve
all locations. Never merge different outputs. State human_claim_type as factual,
assumption, recommendation or projection. support_verdict is sufficient,
partial_support, none or contradicted. Partial support is not sufficient. A verifiable
fact lacking evidence cannot become a correct assumption merely by its model label.
correct_assumption and high_impact are yes/no human judgments. Record evidence
locations, rationale, reviewer and reviewed_at. Complete coverage.csv only after all
decision-critical claims (including ones not proposed by the model) have been checked.
No claim metric is calculated before coverage and judgments are complete.

Model-proposed support, confidence and citations are content to review, not truth.
Source IDs and quotes remain visible. RAM, tokens, model/condition and run identity
are not shown. Content style/length may still make perfect architecture blinding
impossible. No external publication approval is implied by this internal packet.
