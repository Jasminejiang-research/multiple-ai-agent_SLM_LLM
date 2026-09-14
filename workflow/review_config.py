"""Versioned S2 configuration. Request/token/output limits have no implicit defaults."""
from typing import Literal
from pydantic import Field, StrictInt, model_validator
from schemas.evidence import StrictModel, canonical_hash
from schemas.compact_wire import WIRE_VERSION
from workflow.compact_protocol import (
    CONFIG_VERSION, GEMINI_8192_CONFIG_VERSION, GEMINI_8192_MINIMAL_CONFIG_VERSION,
    GEMINI_8192_CONTRACT_CONFIG_VERSION, GEMINI_8192_THINKING_CONFIG_VERSION,
    GEMINI_8192_REASON200_CONFIG_VERSION, GEMINI_8192_REPAIR_CONFIG_VERSION,
    GEMINI_8192_PUNCTUATION_REPAIR_CONFIG_VERSION,
    GEMINI_8192_PREMISE_CONFIG_VERSION,
    GEMINI_8192_TEXT_EQUALS_CLAIM_CONFIG_VERSION,
    GEMINI_8192_CITATION_CONTRACT_CONFIG_VERSION,
    GEMINI_8192_CITATION_FORMAT_CONFIG_VERSION,
    GEMINI_8192_GAP_COUNT_CONFIG_VERSION,
    GEMINI_8192_EXACT_CARDINALITY_CONFIG_VERSION,
    GEMINI_8192_FINANCE_MARKER_CONFIG_VERSION,
    GEMINI_8192_FINANCE_MARKER_PREFIX_CONFIG_VERSION,
    GEMINI_8192_SOURCE_QUALITY_CONFIG_VERSION,
    GEMINI_8192_BODY_ASSEMBLY_CONFIG_VERSION,
    GEMINI_8192_FINANCE_CAPACITY_CONFIG_VERSION,
    GEMINI_8192_FINANCE_PARTITION_CONFIG_VERSION,
    GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION,
    GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION, GEMINI_8192_LINEAGE_ID_CONFIG_VERSION, GEMINI_8192_ID_COLLISION_CONFIG_VERSION, GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION,
    LEGACY_PROTOCOL, MVP30_SECONDS,
    VALID_PLAN_SECONDS,
)

MULTI_REVIEW_VERSION = "multi-agent-review-gates-v3-two-stage"
SINGLE_CONTRACT_VERSION = "single-agent-common-contract-v2-two-stage"
MULTI_COMPACT_VERSION = "multi-agent-review-gates-v4-s6-compact"
SINGLE_COMPACT_VERSION = "single-agent-common-contract-v3-s6-compact"


class ReviewRunConfig(StrictModel):
    condition: Literal["A", "B", "C", "D"]
    run_kind: Literal["formal", "preflight", "smoke", "warmup", "debug"]
    provider: Literal["gemini", "local", "mock"]
    model_exact_id: str = Field(min_length=1)
    model_config_version: str = Field(min_length=1)
    max_requests: StrictInt = Field(ge=1)
    max_total_tokens: StrictInt = Field(ge=1)
    max_output_tokens: StrictInt = Field(ge=1)
    max_prompt_chars: StrictInt = Field(ge=1)
    node_seconds: float = Field(default=1200, gt=0, le=1200)
    run_seconds: float = Field(default=5400, gt=0, le=5400)
    request_seconds: float = Field(gt=0, le=1200)
    transport_retries: StrictInt = Field(default=0, ge=0, le=1)
    temperature: Literal[0] = 0
    thinking_budget: StrictInt | None = Field(default=None, ge=0, le=24576)
    context_tokens: Literal[32768] = 32768
    protocol_version: Literal["body-then-grounding-v1", "compact-json-wire-v1-s6"] = LEGACY_PROTOCOL
    mvp_seconds: float = Field(default=MVP30_SECONDS, gt=0, le=MVP30_SECONDS)
    config_version: Literal[
        "review-run-v1-s2", "review-run-v2-s6-compact",
        "review-run-v3-s6-compact-gemini-8192",
        "review-run-v4-s6-compact-gemini-8192-minimal",
        "review-run-v5-s6-compact-gemini-8192-contract",
        "review-run-v6-s6-compact-gemini-8192-thinking1024",
        "review-run-v7-s6-compact-gemini-8192-id3-reason200",
        "review-run-v8-s6-compact-gemini-8192-conservative-repair",
        "review-run-v9-s6-compact-gemini-8192-conservative-punctuation-repair",
        "review-run-v10-s6-compact-gemini-8192-punctuation-recommendation-premise",
        "review-run-v11-s6-compact-gemini-8192-text-equals-claim",
        "review-run-v12-s6-compact-gemini-8192-inline-citation-contract",
        "review-run-v13-s6-compact-gemini-8192-citation-bracket-format",
        "review-run-v14-s6-compact-gemini-8192-gap-count-inline-citation-mirror",
        "review-run-v15-s6-compact-gemini-8192-exact-array-cardinality",
        "review-run-v16-s6-compact-gemini-8192-structured-finance-markers",
        "review-run-v17-s6-compact-gemini-8192-finance-marker-prefix",
        "review-run-v18-s6-compact-gemini-8192-source-quality-scale",
        "review-run-v19-s6-compact-gemini-8192-existing-claim-body-assembly",
        "review-run-v20-s6-compact-gemini-8192-finance-claims-eight",
        "review-run-v21-s6-compact-gemini-8192-finance-partition-recency",
        "review-run-v22-s6-compact-gemini-8192-finance-assumption-notice",
        "review-run-v23-s6-compact-gemini-8192-repair-instruction-admission",
        "review-run-v24-s6-compact-gemini-8192-lineage-identity-continuity",
        "review-run-v25-s6-compact-gemini-8192-claim-id-collision",
        "review-run-v26-s6-compact-gemini-8192-dual-declared-lineage",
    ] = "review-run-v1-s2"

    @model_validator(mode="after")
    def compact_invariants(self):
        if self.protocol_version == WIRE_VERSION:
            if self.run_seconds != VALID_PLAN_SECONDS or self.mvp_seconds != MVP30_SECONDS:
                raise ValueError("compact protocol requires common MVP30/ValidPlan60 clocks")
            legacy = (self.config_version == CONFIG_VERSION and self.max_output_tokens == 1800
                and self.thinking_budget is None)
            gemini_8192_previous = (
                self.config_version in (GEMINI_8192_CONFIG_VERSION, GEMINI_8192_MINIMAL_CONFIG_VERSION,
                                        GEMINI_8192_CONTRACT_CONFIG_VERSION)
                and self.provider == "gemini" and self.condition in ("A", "B", "C")
                and self.max_output_tokens == 8192 and self.thinking_budget is None
            )
            gemini_8192_thinking = (
                self.config_version in (GEMINI_8192_THINKING_CONFIG_VERSION,
                    GEMINI_8192_REASON200_CONFIG_VERSION, GEMINI_8192_REPAIR_CONFIG_VERSION,
                    GEMINI_8192_PUNCTUATION_REPAIR_CONFIG_VERSION,
                    GEMINI_8192_PREMISE_CONFIG_VERSION,
                    GEMINI_8192_TEXT_EQUALS_CLAIM_CONFIG_VERSION,
                    GEMINI_8192_CITATION_CONTRACT_CONFIG_VERSION,
                    GEMINI_8192_CITATION_FORMAT_CONFIG_VERSION,
                    GEMINI_8192_GAP_COUNT_CONFIG_VERSION,
                    GEMINI_8192_EXACT_CARDINALITY_CONFIG_VERSION,
                    GEMINI_8192_FINANCE_MARKER_CONFIG_VERSION,
                    GEMINI_8192_FINANCE_MARKER_PREFIX_CONFIG_VERSION,
                    GEMINI_8192_SOURCE_QUALITY_CONFIG_VERSION,
                    GEMINI_8192_BODY_ASSEMBLY_CONFIG_VERSION,
                    GEMINI_8192_FINANCE_CAPACITY_CONFIG_VERSION,
                    GEMINI_8192_FINANCE_PARTITION_CONFIG_VERSION,
                    GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION,
                    GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION, GEMINI_8192_LINEAGE_ID_CONFIG_VERSION, GEMINI_8192_ID_COLLISION_CONFIG_VERSION, GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION)
                and self.provider == "gemini" and self.condition in ("A", "B", "C")
                and self.max_output_tokens == 8192 and self.thinking_budget == 1024
            )
            if not (legacy or gemini_8192_previous or gemini_8192_thinking) or self.max_prompt_chars > 26000:
                raise ValueError("compact config version/output and prompt caps do not match")
        return self

    @property
    def workflow_version(self):
        if self.protocol_version == WIRE_VERSION:
            return SINGLE_COMPACT_VERSION if self.condition == "A" else MULTI_COMPACT_VERSION
        return SINGLE_CONTRACT_VERSION if self.condition == "A" else MULTI_REVIEW_VERSION

    @property
    def reviewed_roles(self):
        return () if self.condition == "A" else ("final",) if self.condition == "B" else ("research", "strategy", "finance", "final")

    @property
    def sha256(self):
        return canonical_hash(self.model_dump(mode="json"))
