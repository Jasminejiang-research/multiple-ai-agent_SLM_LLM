# AI Tutor for MBA Students Proposal

Confidence uses structurally checked model-proposed support. Human fact verification is pending.

## Executive Summary

This proposal assesses a staged launch for an AI Tutor for MBA Students, focusing on differentiation and cash needs.

Confidence: medium; reason: assumption_dominant

## Problem

The pilot tests if students need more timely, personalized business-case reasoning feedback than current arrangements.

Confidence: medium; reason: assumption_dominant

## Target Customer

US adults 18+ in MBA/business graduate programs or applying, with instructors as potential institutional buyers.

Confidence: medium; reason: partial_support

## Market Opportunity

Graduate completion counts establish historical volume but not demand, TAM, or willingness to pay for this service.

Confidence: medium; reason: partial_support

## Solution

An English-language AI case-coaching service offers guided questions, evidence-aware feedback, and practice.

Confidence: medium; reason: partial_support

## Value Proposition

Differentiation from broad tutoring comes from an MBA-specific offering with specialized content and feedback.

Confidence: medium; reason: assumption_dominant

## Competitor Analysis

Khanmigo is an adjacent tutoring benchmark at $4/month or $44/year, not a direct MBA substitute [EDU-01].

Confidence: high; reason: directly_supported

## Business Model

Direct monthly subscription is the base financial scenario, excluding institutional licensing revenue.

Confidence: medium; reason: partial_support

## Go-to-Market Strategy

A staged launch involves 3 months discovery/prototype, 3 months limited pilot, then conditional scaling.

Confidence: medium; reason: partial_support

## Financial Assumptions

Achieving operating break-even requires 500 average paying users monthly over 12 months.

Confidence: medium; reason: assumption_dominant

Scenario calculations (input provenance is retained in brief.json; these are not forecasts):

| Value ID | Value | Unit | Period | Origin | Formula |
|---|---:|---|---|---|---|
| low.monthly_revenue | 1900.00 | USD/month | month | calculated_result | s0-case-formulas-v1/ai_education/monthly_revenue |
| low.monthly_variable_cost | 400.00 | USD/month | month | calculated_result | s0-case-formulas-v1/ai_education/monthly_variable_cost |
| low.monthly_contribution | 1500.00 | USD/month | month | calculated_result | s0-case-formulas-v1/ai_education/monthly_contribution |
| low.monthly_operating_result | -6000.00 | USD/month | month | calculated_result | s0-case-formulas-v1/ai_education/monthly_operating_result |
| low.annual_cash_change | -90000.00 | USD | year_1 | calculated_result | s0-case-formulas-v1/ai_education/annual_cash_change |
| low.ending_cash | 30000.00 | USD | year_1 | calculated_result | s0-case-formulas-v1/ai_education/ending_cash |
| low.break_even_users | 500 | customers | monthly average over 12 months | calculated_result | s0-case-formulas-v1/ai_education/break_even_users |
| base.monthly_revenue | 4750.00 | USD/month | month | calculated_result | s0-case-formulas-v1/ai_education/monthly_revenue |
| base.monthly_variable_cost | 1000.00 | USD/month | month | calculated_result | s0-case-formulas-v1/ai_education/monthly_variable_cost |
| base.monthly_contribution | 3750.00 | USD/month | month | calculated_result | s0-case-formulas-v1/ai_education/monthly_contribution |
| base.monthly_operating_result | -3750.00 | USD/month | month | calculated_result | s0-case-formulas-v1/ai_education/monthly_operating_result |
| base.annual_cash_change | -63000.00 | USD | year_1 | calculated_result | s0-case-formulas-v1/ai_education/annual_cash_change |
| base.ending_cash | 57000.00 | USD | year_1 | calculated_result | s0-case-formulas-v1/ai_education/ending_cash |
| base.break_even_users | 500 | customers | monthly average over 12 months | calculated_result | s0-case-formulas-v1/ai_education/break_even_users |
| high.monthly_revenue | 9500.00 | USD/month | month | calculated_result | s0-case-formulas-v1/ai_education/monthly_revenue |
| high.monthly_variable_cost | 2000.00 | USD/month | month | calculated_result | s0-case-formulas-v1/ai_education/monthly_variable_cost |
| high.monthly_contribution | 7500.00 | USD/month | month | calculated_result | s0-case-formulas-v1/ai_education/monthly_contribution |
| high.monthly_operating_result | 0.00 | USD/month | month | calculated_result | s0-case-formulas-v1/ai_education/monthly_operating_result |
| high.annual_cash_change | -18000.00 | USD | year_1 | calculated_result | s0-case-formulas-v1/ai_education/annual_cash_change |
| high.ending_cash | 102000.00 | USD | year_1 | calculated_result | s0-case-formulas-v1/ai_education/ending_cash |
| high.break_even_users | 500 | customers | monthly average over 12 months | calculated_result | s0-case-formulas-v1/ai_education/break_even_users |

## Risks and Mitigations

FERPA compliance is critical for any school data ingestion, requiring careful privacy review [EDU-03].

Confidence: high; reason: directly_supported

## Implementation Roadmap

Interviews, content licenses, school data permissions, and learning-outcome tests are needed before expansion.

Confidence: medium; reason: assumption_dominant

## Appendix

This section provides supplementary information and detailed data supporting the proposal's claims.

Confidence: medium; reason: partial_support

Frozen sources (Appendix):

[EDU-01] Khanmigo pricing — https://www.khanmigo.ai/pricing; snapshot SHA-256: 3ba7b605f33ac8d94f437a7d447df31b4378b947d3ec92845f1dd83be2022c00

[EDU-02] Graduate Degree Fields — https://nces.ed.gov/programs/coe/indicator/ctb/graduate-degree-fields; snapshot SHA-256: 77a5e89be05b54e137ef920e582abbf0a8f5d479f9ff785c992934df721bc56c

[EDU-03] What is FERPA? — https://studentprivacy.ed.gov/faq/what-ferpa; snapshot SHA-256: 1fc5afa18f74989ee9bd9208790148bf03dd8e84376b7afacca5ec4089e280c1
