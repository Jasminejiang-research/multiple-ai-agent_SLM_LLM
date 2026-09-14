"""Serializable S2 journal payload schemas for S3 adapters and S4 reducers."""
from typing import Any, Literal
from pydantic import Field
from schemas.evidence import StrictModel


class ArtifactRef(StrictModel):
    artifact_id: str
    artifact_version: int
    sha256: str


class CallEventPayload(StrictModel):
    run_id: str
    planned_id: str | None
    run_kind: Literal["formal", "preflight", "smoke", "warmup", "debug"]
    logical_task_id: str
    node_scope_id: str
    batch_id: int | None
    attempt_id: str
    attempt_index: int = Field(ge=1)
    role: str
    task_role: str
    generation_stage: Literal["single", "body", "grounding", "compact", "patch"] = "single"
    purpose: Literal["generate", "critic", "revision", "structure_repair"]
    task_purpose: Literal["generate", "critic", "revision"]
    transport_retry_of: str | None
    provider: str
    model_exact_id: str
    model_config_version: str
    config_sha256: str
    prompt_hash: str
    schema_hash: str
    normalized_prompt_hash: str | None = None
    role_view_hash: str | None = None
    instruction_chars: int | None = Field(default=None, ge=0)
    full_prompt_chars: int | None = Field(default=None, ge=0)
    full_prompt_utf8_bytes: int | None = Field(default=None, ge=0)
    wire_schema_bytes: int | None = Field(default=None, ge=0)
    estimated_input_tokens: int | None = Field(default=None, ge=0)
    role_input_target_tokens: int | None = Field(default=None, ge=0)
    role_input_target_estimate_passed: bool | None = None
    mechanical_repair_applied: bool = False
    mechanical_repair_diff: list[dict[str, Any]] = Field(default_factory=list)
    evidence_hash: str
    input_artifact_refs: list[ArtifactRef]
    output_artifact_ref: dict[str, Any] | None
    started_at_utc: str
    ended_at_utc: str | None
    elapsed_seconds: float | None
    status: Literal["dispatching", "succeeded", "failed", "timeout", "cancelled", "invalid_output", "interrupted_unknown"]
    error_type: str | None
    usage_raw: dict[str, Any] | None
    prompt_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    usage_missing_reason: str | None
    budget_before: dict[str, Any]
    budget_after: dict[str, Any]
    reservation_tokens: int
    budget_token_charge: int | None = None
    raw_output: str | None = None
    finish_reason: str | None = None


class ExpectedHandoff(StrictModel):
    handoff_id: str
    run_id: str
    upstream_node: str
    downstream_node: str
    required_artifact_id: str
    required_artifact_version: int | None
    required_artifact_hash: str | None
    dependency_ids: list[str]
    branch_rule: str
    expected: bool
    status: Literal["pending", "succeeded", "failed", "missing", "not_applicable"]
    received_artifact_ref: ArtifactRef | None
    occurred_at_utc: str | None
    within_budget: bool | None
    failure_reason: str | None
