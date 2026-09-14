"""Small generation profile; the full canonical reader still accepts history.

The user authorized shorter Research on 2026-09-07. Bounds reject overlong
model output; no finding, claim or evidence is silently truncated by code.
"""
from typing import Annotated, ClassVar

from pydantic import Field

from schemas.contract_outputs import ContractResearchAnalysis, GroundedFinding
from schemas.evidence import GroundedClaim
from workflow.research_limits import RESEARCH_PROFILE_VERSION


class BriefResearchClaim(GroundedClaim):
    claim_text: str = Field(min_length=1, max_length=240)
    claim_domain: str = Field(min_length=1, max_length=48)
    premise: str = Field(max_length=200)
    financial_value_ids: list[str] = Field(max_length=0,
        description='Research makes no financial calculations. Return []; Finance owns financial-value analysis.')


class BriefResearchFinding(GroundedFinding):
    topic: str = Field(min_length=3, max_length=60)
    finding: str = Field(min_length=20, max_length=240)
    rationale: str = Field(min_length=20, max_length=160)
    claims: list[BriefResearchClaim] = Field(min_length=1, max_length=1)


class BriefResearchAnalysis(ContractResearchAnalysis):
    __research_profile__: ClassVar[str] = RESEARCH_PROFILE_VERSION
    analysis_summary: str = Field(min_length=20, max_length=280)
    market_trends: list[BriefResearchFinding] = Field(min_length=1, max_length=1)
    customer_notes: list[BriefResearchFinding] = Field(min_length=1, max_length=1)
    competitor_assumptions: list[BriefResearchFinding] = Field(min_length=1, max_length=1)
    unsupported_claims: list[BriefResearchClaim] = Field(default_factory=list, max_length=0)
    needs_human_review: list[Annotated[str, Field(min_length=1, max_length=140)]] = Field(default_factory=list, max_length=3)


RESEARCH_INSTRUCTION = f'''Research generation profile: {RESEARCH_PROFILE_VERSION}.
Return exactly ONE priority market finding, ONE customer finding and ONE competitor/substitute finding.
Each finding expresses ONE atomic core claim. Its rationale explains why that claim matters, without adding
other decision-critical assertions that would require more claims. Annotate each finding with exactly ONE claim.
Return unsupported_claims=[]: do not create a fourth claim group. Keep the uncertainty and evidence status of each
of the three core claims explicit. Record material remaining evidence gaps in needs_human_review (at most 3).
Aim for one complete sentence of at most 120 characters per finding, at most 90 per rationale, and 180 for the summary.
Choose fewer words to finish the sentence; never end on an unfinished clause such as "if" to fit a length bound.
Keep the analysis summary within 280 characters, topics within 60, findings within 240, rationales within 160,
claim_text within 240, premises within 200, and each human-review item within 140. These are ceilings, not targets.
Prefer a narrow accurately supported observation or clearly labelled assumption over a collection of weak assertions.
Unmeasured MBA growth, student needs and willingness to pay are assumptions, not validated market facts.
For every assumption or projection set evidence_status="assumption", even when supporting evidence is unavailable.
Example: claim_type="assumption", evidence_status="assumption", source_support="none", evidence_span_ids=[], with a
nonempty premise explaining the uncertainty. Evidence absence does not change an assumption's status to "unsupported".
Check any source statistic's exact year, population and denominator. Do not calculate break-even, profit, cash flow
or scenario forecasts in Research; Finance receives the full brief and owns those calculations. financial_value_ids=[].
Preserve source provenance, inherited claim identities and uncertainty. Full packet inputs remain available downstream.
Do not replace missing evidence with invented market sizes, competitor prices, learning outcomes or adoption rates.'''
