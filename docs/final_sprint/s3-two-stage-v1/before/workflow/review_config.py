"""Versioned S2 configuration. Request/token/output limits have no implicit defaults."""
from typing import Literal
from pydantic import Field, StrictInt
from schemas.evidence import StrictModel, canonical_hash

MULTI_REVIEW_VERSION = "multi-agent-review-gates-v2"
SINGLE_CONTRACT_VERSION = "single-agent-common-contract-v1"


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
    context_tokens: Literal[32768] = 32768
    config_version: Literal["review-run-v1-s2"] = "review-run-v1-s2"

    @property
    def workflow_version(self):
        return SINGLE_CONTRACT_VERSION if self.condition == "A" else MULTI_REVIEW_VERSION

    @property
    def reviewed_roles(self):
        return () if self.condition == "A" else ("final",) if self.condition == "B" else ("research", "strategy", "finance", "final")

    @property
    def sha256(self):
        return canonical_hash(self.model_dump(mode="json"))
