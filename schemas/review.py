"""S2 role-aware review inputs; scores and routing are computed, never self-reported."""
from __future__ import annotations

from typing import Literal
from pydantic import Field, StrictInt, model_validator
from schemas.evidence import StrictModel

REVIEW_VERSION = "component-review-v1-s2"
METRICS = {
    "research": ("source_integrity", "evidence_alignment", "task_relevance", "uncertainty_disclosure"),
    "strategy": ("brief_alignment", "evidence_consistency", "action_feasibility", "assumption_transparency"),
    "finance": ("arithmetic_and_units", "input_provenance", "cross_section_consistency", "assumption_sensitivity"),
    "final": ("factual_citation_correctness", "reasoning_consistency", "structure_completeness",
              "business_plausibility", "uncertainty_calibration", "clarity_traceability"),
}


class ReviewMetric(StrictModel):
    criterion: str = Field(min_length=1)
    score: StrictInt = Field(ge=0, le=4)
    rationale: str = Field(min_length=1)
    evidence_anchor: str = Field(min_length=1)


class ReviewIssue(StrictModel):
    issue_id: str = Field(min_length=1)
    severity: Literal["low", "medium", "high", "critical"]
    criterion: str = Field(min_length=1)
    description: str = Field(min_length=1)
    suggested_fix: str = Field(min_length=1)
    affected_claim_ids: list[str]
    source_ids: list[str]
    target_fields: list[str] = Field(default_factory=list, max_length=6)
    evidence_ids: list[str] = Field(default_factory=list, max_length=6)
    fix_code: str | None = Field(default=None, max_length=80)
    artifact_version: StrictInt = Field(ge=1, le=2)


class ComponentCritiqueReport(StrictModel):
    role: Literal["research", "strategy", "finance", "final"]
    artifact_id: str = Field(min_length=1)
    artifact_version: StrictInt = Field(ge=1, le=2)
    metrics: list[ReviewMetric]
    issues: list[ReviewIssue] = Field(max_length=3)
    provider_status: Literal["PASS", "FAIL"] | None = None

    @model_validator(mode="after")
    def validate_fixed_metrics(self):
        keys = [m.criterion for m in self.metrics]
        if len(keys) != len(set(keys)) or set(keys) != set(METRICS[self.role]):
            raise ValueError(f"{self.role} requires each fixed criterion exactly once: {METRICS[self.role]}")
        ids = [i.issue_id for i in self.issues]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate issue ID")
        for issue in self.issues:
            if issue.criterion not in keys or issue.artifact_version != self.artifact_version:
                raise ValueError("issue criterion/version does not match reviewed artifact")
            if len(issue.affected_claim_ids) != len(set(issue.affected_claim_ids)):
                raise ValueError("duplicate affected claim ID")
        return self

    @property
    def mean_metric_score(self) -> float:
        return sum(m.score for m in self.metrics) / len(self.metrics)

    @property
    def overall_score(self) -> float:
        return self.mean_metric_score * 2.5

    @property
    def blocking(self) -> bool:
        return any(i.severity == "critical" for i in self.issues)

    @property
    def revision_required(self) -> bool:
        # S6: scores remain diagnostic; only high/critical issues trigger Revision.
        return any(i.severity in ("high", "critical") for i in self.issues)

    def gate(self, *, revision_count=0, budget_snapshot=None):
        if revision_count != 0:
            raise ValueError("a second semantic review/revision is prohibited")
        return dict(role=self.role, artifact_id=self.artifact_id, artifact_version=self.artifact_version,
            overall_score=self.overall_score, revision_required=self.revision_required, blocking=self.blocking,
            revision_count=0, decision="revise_once" if self.revision_required else "pass",
            trigger_issue_ids=[i.issue_id for i in self.issues if i.severity in ("high", "critical")],
            budget_snapshot=budget_snapshot or {}, semantic_verification_status="reviewed_initial")

    def as_dict(self):
        return {**self.model_dump(mode="json"), "overall_score": self.overall_score,
                "mean_metric_score": self.mean_metric_score,
                "must_fix": [i.suggested_fix for i in self.issues if i.severity in ("high", "critical")],
                "review_version": REVIEW_VERSION}
