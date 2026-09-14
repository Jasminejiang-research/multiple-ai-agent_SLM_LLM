"""S1 complete output contract. Legacy schemas remain readable and unchanged."""
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from schemas.agent_outputs import (ResearchFinding, ResearchAnalysis, StrategyInsight,
                                   StrategyAnalysis, FinanceAssumption, FinanceAssumptions)
from schemas.evidence import StrictModel, GroundedClaim, Confidence, ConfidenceReason
from schemas.financial import FinancialValue
from schemas.workflow import ProposalDraft, SECTION_FIELD_BY_TITLE

CONTRACT_VERSION = "proposal-grounding-v3-frozen-reference-bounds"


class GroundedFinding(ResearchFinding):
    claims: list[GroundedClaim] = Field(min_length=1, max_length=8)
    confidence_reason: ConfidenceReason


class GroundedInsight(StrategyInsight):
    claims: list[GroundedClaim] = Field(min_length=1, max_length=8)
    confidence_reason: ConfidenceReason


class GroundedFinanceAssumption(FinanceAssumption):
    claims: list[GroundedClaim] = Field(min_length=1, max_length=8)
    value_ids: list[str]
    confidence_reason: ConfidenceReason

    @field_validator("value_ids")
    @classmethod
    def unique_value_references(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("value_ids must contain unique financial references")
        return values


class ContractResearchAnalysis(ResearchAnalysis):
    market_trends: list[GroundedFinding] = Field(min_length=1, max_length=6)
    customer_notes: list[GroundedFinding] = Field(min_length=1, max_length=6)
    competitor_assumptions: list[GroundedFinding] = Field(min_length=1, max_length=6)
    unsupported_claims: list[GroundedClaim] = Field(default_factory=list, max_length=8)


class ContractStrategyAnalysis(StrategyAnalysis):
    value_proposition: list[GroundedInsight] = Field(min_length=1, max_length=5)
    business_model_logic: list[GroundedInsight] = Field(min_length=1, max_length=5)
    gtm_strategy: list[GroundedInsight] = Field(min_length=1, max_length=5)
    moat_hypotheses: list[GroundedInsight] = Field(min_length=1, max_length=5)
    unsupported_market_data: list[GroundedClaim] = Field(default_factory=list, max_length=8)


class ContractFinanceAssumptions(FinanceAssumptions):
    revenue_assumptions: list[GroundedFinanceAssumption] = Field(min_length=1, max_length=6)
    cost_assumptions: list[GroundedFinanceAssumption] = Field(min_length=1, max_length=6)
    unit_economics_assumptions: list[GroundedFinanceAssumption] = Field(min_length=1, max_length=6)
    unsupported_financial_claims: list[GroundedClaim] = Field(default_factory=list, max_length=8)
    financial_values: list[FinancialValue] = Field(min_length=1)


class ContractSection(StrictModel):
    title: str
    content: str = Field(min_length=40)
    key_claims: list[GroundedClaim] = Field(min_length=1, max_length=8)
    source_ids: list[str] = Field(max_length=8)
    confidence: Confidence
    confidence_reason: ConfidenceReason


class ContractFinancialSection(ContractSection):
    financial_values: list[FinancialValue] = Field(min_length=1)


class ContractProposal(ProposalDraft):
    """Same thirteen named sections as ProposalDraft, with strict v1 provenance."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    executive_summary: ContractSection
    problem: ContractSection
    target_customer: ContractSection
    market_opportunity: ContractSection
    solution: ContractSection
    value_proposition: ContractSection
    competitor_analysis: ContractSection
    business_model: ContractSection
    go_to_market_strategy: ContractSection
    financial_assumptions: ContractFinancialSection
    risks_and_mitigations: ContractSection
    implementation_roadmap: ContractSection
    appendix: ContractSection

    @model_validator(mode="after")
    def ensure_fixed_sections_match_fields(self):
        ids = []
        for title, field in SECTION_FIELD_BY_TITLE.items():
            section = getattr(self, field)
            if section.title != title:
                raise ValueError(f"{field} must have title {title!r}")
            ids.extend(section.source_ids)
        derived = list(dict.fromkeys(ids))
        if self.global_source_ids and set(self.global_source_ids) != set(derived):
            raise ValueError("global source IDs differ from section citations")
        self.global_source_ids = derived
        return self


class ConfidenceChange(StrictModel):
    artifact_version: int
    location: str
    previous: Confidence
    current: Confidence
    reason: ConfidenceReason
    basis: Literal["proposed_support_structurally_checked_not_human_gold"] = "proposed_support_structurally_checked_not_human_gold"
