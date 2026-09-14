"""Provider-neutral compact JSON DTOs for the S6 generation protocol.

The DTOs deliberately contain no field descriptions.  They are transport
objects only; strict canonical validation remains in the existing schemas.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, StrictInt, model_validator

from schemas.evidence import Confidence, ConfidenceReason, StrictModel

WIRE_VERSION = "compact-json-wire-v1-s6"


class ClaimWire(StrictModel):
    i: str = Field(min_length=3, max_length=80)
    pi: str | None = Field(default=None, min_length=3, max_length=80)
    t: str = Field(min_length=3, max_length=600)
    k: Literal["factual", "assumption", "recommendation", "projection"]
    d: str = Field(min_length=2, max_length=200)
    s: Literal["sourced_fact", "needs_validation", "assumption", "unsupported"]
    e: list[str] = Field(default_factory=list, max_length=6)
    f: list[str] = Field(default_factory=list, max_length=12)
    ss: Literal["direct", "partial", "contextual", "none"]
    q: float = Field(ge=0, le=1, allow_inf_nan=False)
    r: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    p: str = Field(default="", max_length=500)
    dc: bool = False
    hi: bool = False
    cf: bool = False
    c: Confidence
    cr: ConfidenceReason

    @model_validator(mode="after")
    def disposition(self):
        if len(self.e) != len(set(self.e)) or len(self.f) != len(set(self.f)):
            raise ValueError("compact evidence/financial IDs must be unique")
        if self.s == "sourced_fact" and (self.k != "factual" or not self.e or self.ss != "direct"):
            raise ValueError("sourced_fact requires factual/direct evidence")
        if self.k in ("assumption", "projection") and (self.s != "assumption" or not self.p):
            raise ValueError("assumption/projection requires an explicit premise")
        return self


class ResearchNoteWire(StrictModel):
    topic: str = Field(min_length=3, max_length=120)
    text: str = Field(min_length=20, max_length=900)
    why: str = Field(min_length=20, max_length=700)
    c: Confidence
    cr: ConfidenceReason
    claims: list[ClaimWire] = Field(min_length=1, max_length=3)


class ResearchWire(StrictModel):
    summary: str = Field(min_length=20, max_length=800)
    market: list[ResearchNoteWire] = Field(min_length=1, max_length=1)
    customer: list[ResearchNoteWire] = Field(min_length=1, max_length=1)
    competition: list[ResearchNoteWire] = Field(min_length=1, max_length=1)
    gaps: list[ClaimWire] = Field(default_factory=list, max_length=3)
    review: list[str] = Field(default_factory=list, max_length=5)


class StrategyNoteWire(StrictModel):
    topic: str = Field(min_length=3, max_length=120)
    text: str = Field(min_length=20, max_length=900)
    why: str = Field(min_length=20, max_length=700)
    c: Confidence
    cr: ConfidenceReason
    claims: list[ClaimWire] = Field(min_length=1, max_length=3)


class StrategyWire(StrictModel):
    summary: str = Field(min_length=20, max_length=800)
    value: list[StrategyNoteWire] = Field(min_length=1, max_length=2)
    model: list[StrategyNoteWire] = Field(min_length=1, max_length=2)
    gtm: list[StrategyNoteWire] = Field(min_length=1, max_length=2)
    moat: list[StrategyNoteWire] = Field(min_length=1, max_length=2)
    gaps: list[ClaimWire] = Field(default_factory=list, max_length=3)
    review: list[str] = Field(default_factory=list, max_length=5)


class FinanceNoteWire(StrictModel):
    topic: str = Field(min_length=3, max_length=120)
    text: str = Field(min_length=20, max_length=900)
    why: str = Field(min_length=20, max_length=700)
    f: list[str] = Field(default_factory=list, max_length=12)
    c: Confidence
    cr: ConfidenceReason
    claims: list[ClaimWire] = Field(min_length=1, max_length=3)


class FinanceWire(StrictModel):
    summary: str = Field(min_length=20, max_length=800)
    revenue: list[FinanceNoteWire] = Field(min_length=1, max_length=2)
    costs: list[FinanceNoteWire] = Field(min_length=1, max_length=2)
    economics: list[FinanceNoteWire] = Field(min_length=1, max_length=2)
    break_even: str = Field(min_length=30, max_length=900)
    notice: str = Field(min_length=30, max_length=400)
    gaps: list[ClaimWire] = Field(default_factory=list, max_length=3)
    review: list[str] = Field(default_factory=list, max_length=5)


class FinanceNote8Wire(FinanceNoteWire):
    """Opt-in transport capacity matching the existing canonical note limit."""
    claims: list[ClaimWire] = Field(min_length=1, max_length=8)


class Finance8Wire(FinanceWire):
    revenue: list[FinanceNote8Wire] = Field(min_length=1, max_length=2)
    costs: list[FinanceNote8Wire] = Field(min_length=1, max_length=2)
    economics: list[FinanceNote8Wire] = Field(min_length=1, max_length=2)


SECTION_KEYS = (
    "executive_summary", "problem", "target_customer", "market_opportunity",
    "solution", "value_proposition", "competitor_analysis", "business_model",
    "go_to_market_strategy", "financial_assumptions", "risks_and_mitigations",
    "implementation_roadmap", "appendix",
)
SectionKey = Literal[
    "executive_summary", "problem", "target_customer", "market_opportunity",
    "solution", "value_proposition", "competitor_analysis", "business_model",
    "go_to_market_strategy", "financial_assumptions", "risks_and_mitigations",
    "implementation_roadmap", "appendix",
]


class SectionWire(StrictModel):
    key: SectionKey
    text: str = Field(min_length=40, max_length=2400)
    claims: list[ClaimWire] = Field(min_length=1, max_length=5)
    c: Confidence
    cr: ConfidenceReason


class ProposalWire(StrictModel):
    title: str = Field(min_length=3, max_length=200)
    sections: list[SectionWire] = Field(min_length=13, max_length=13)

    @model_validator(mode="after")
    def fixed_sections(self):
        if tuple(section.key for section in self.sections) != SECTION_KEYS:
            raise ValueError("compact proposal must contain the fixed 13 sections in order")
        return self


class CriticIssueWire(StrictModel):
    i: str = Field(min_length=3, max_length=80)
    sev: Literal["low", "medium", "high", "critical"]
    criterion: str = Field(min_length=2, max_length=80)
    claims: list[str] = Field(default_factory=list, max_length=6)
    fields: list[str] = Field(default_factory=list, max_length=6)
    e: list[str] = Field(default_factory=list, max_length=6)
    fix: str = Field(min_length=2, max_length=80)
    note: str = Field(min_length=5, max_length=500)


class CriticWire(StrictModel):
    scores: list[StrictInt] = Field(min_length=4, max_length=6)
    status: Literal["PASS", "FAIL"]
    issues: list[CriticIssueWire] = Field(default_factory=list, max_length=3)


class ClaimPatchWire(StrictModel):
    issue: str = Field(min_length=3, max_length=80)
    i: str = Field(min_length=3, max_length=80)
    t: str | None = Field(default=None, min_length=3, max_length=600)
    s: Literal["sourced_fact", "needs_validation", "assumption", "unsupported"] | None = None
    e: list[str] | None = Field(default=None, max_length=6)
    f: list[str] | None = Field(default=None, max_length=12)
    ss: Literal["direct", "partial", "contextual", "none"] | None = None
    p: str | None = Field(default=None, max_length=500)
    c: Confidence | None = None
    cr: ConfidenceReason | None = None

    @model_validator(mode="after")
    def has_change(self):
        if not self.model_fields_set.difference({"issue", "i"}):
            raise ValueError("claim patch has no changed field")
        return self


class FieldPatchWire(StrictModel):
    issue: str = Field(min_length=3, max_length=80)
    path: str = Field(min_length=2, max_length=160)
    value: str = Field(min_length=3, max_length=2400)


class PatchWire(StrictModel):
    claims: list[ClaimPatchWire] = Field(default_factory=list, max_length=3)
    fields: list[FieldPatchWire] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def nonempty(self):
        if not self.claims and not self.fields:
            raise ValueError("semantic revision patch cannot be empty")
        return self


ROLE_WIRES: dict[str, type[StrictModel]] = {
    "research": ResearchWire,
    "strategy": StrategyWire,
    "finance": FinanceWire,
    "single": ProposalWire,
    "writer": ProposalWire,
}


JsonValue = Any
