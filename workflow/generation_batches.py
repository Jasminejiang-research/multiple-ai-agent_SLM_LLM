"""Small generation-only schemas for full proposal and revision outputs.

The strict business models keep the complete 13-section contract. Gemini sees
four smaller schemas, each covering a fixed section batch, and the validated
batch outputs are merged deterministically before full local validation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ConfigDict, create_model

from schemas.workflow import (
    PROPOSAL_SECTION_FIELD_NAMES,
    ProposalDraft,
    RevisedProposal,
)

PROPOSAL_SECTION_BATCHES: tuple[tuple[str, ...], ...] = (
    (
        "executive_summary",
        "problem",
        "target_customer",
        "market_opportunity",
    ),
    (
        "solution",
        "value_proposition",
        "competitor_analysis",
    ),
    (
        "business_model",
        "go_to_market_strategy",
        "financial_assumptions",
    ),
    (
        "risks_and_mitigations",
        "implementation_roadmap",
        "appendix",
    ),
)

if tuple(
    field_name
    for batch in PROPOSAL_SECTION_BATCHES
    for field_name in batch
) != PROPOSAL_SECTION_FIELD_NAMES:
    raise RuntimeError("Proposal generation batches must cover all fixed sections once.")

_BATCH_CONFIG = ConfigDict(str_strip_whitespace=True, extra="forbid")


def _field_definition(model: type[BaseModel], field_name: str) -> tuple[Any, Any]:
    """Copy one strict field definition into a generation-only batch model."""
    field = model.model_fields[field_name]
    return field.annotation, deepcopy(field)


def _build_proposal_batch_model(
    batch_number: int,
    section_fields: tuple[str, ...],
) -> type[BaseModel]:
    fields = {}
    if batch_number == 1:
        fields["title"] = _field_definition(ProposalDraft, "title")
    fields.update(
        {
            field_name: _field_definition(ProposalDraft, field_name)
            for field_name in section_fields
        }
    )
    return create_model(
        f"ProposalDraftBatch{batch_number}",
        __config__=_BATCH_CONFIG,
        __module__=__name__,
        **fields,
    )


def _build_revision_batch_model(
    batch_number: int,
    section_fields: tuple[str, ...],
) -> type[BaseModel]:
    fields = {}
    if batch_number == 1:
        fields["title"] = _field_definition(ProposalDraft, "title")
    fields.update(
        {
            field_name: _field_definition(ProposalDraft, field_name)
            for field_name in section_fields
        }
    )
    if batch_number == 1:
        fields.update(
            {
                "applied_critique_summary": _field_definition(
                    RevisedProposal,
                    "applied_critique_summary",
                ),
                "unresolved_issues": _field_definition(
                    RevisedProposal,
                    "unresolved_issues",
                ),
            }
        )
    return create_model(
        f"RevisedProposalBatch{batch_number}",
        __config__=_BATCH_CONFIG,
        __module__=__name__,
        **fields,
    )


PROPOSAL_DRAFT_BATCH_MODELS: tuple[type[BaseModel], ...] = tuple(
    _build_proposal_batch_model(batch_number, section_fields)
    for batch_number, section_fields in enumerate(PROPOSAL_SECTION_BATCHES, start=1)
)

REVISED_PROPOSAL_BATCH_MODELS: tuple[type[BaseModel], ...] = tuple(
    _build_revision_batch_model(batch_number, section_fields)
    for batch_number, section_fields in enumerate(PROPOSAL_SECTION_BATCHES, start=1)
)


def _validated_batch_payloads(
    raw_batches: list[BaseModel | dict[str, Any]],
    batch_models: tuple[type[BaseModel], ...],
) -> list[dict[str, Any]]:
    if len(raw_batches) != len(batch_models):
        raise ValueError(
            f"Expected {len(batch_models)} generation batches, got {len(raw_batches)}."
        )
    return [
        model.model_validate(raw_batch).model_dump()
        for model, raw_batch in zip(batch_models, raw_batches, strict=True)
    ]


def _merge_proposal_payloads(batch_payloads: list[dict[str, Any]]) -> ProposalDraft:
    merged: dict[str, Any] = {"title": batch_payloads[0]["title"]}
    for section_fields, payload in zip(
        PROPOSAL_SECTION_BATCHES,
        batch_payloads,
        strict=True,
    ):
        for field_name in section_fields:
            merged[field_name] = payload[field_name]
    return ProposalDraft.model_validate(merged)


def merge_proposal_draft_batches(
    raw_batches: list[BaseModel | dict[str, Any]],
) -> ProposalDraft:
    """Merge four Writer batches and run the full strict business validation."""
    payloads = _validated_batch_payloads(
        raw_batches,
        PROPOSAL_DRAFT_BATCH_MODELS,
    )
    return _merge_proposal_payloads(payloads)


def merge_revised_proposal_batches(
    raw_batches: list[BaseModel | dict[str, Any]],
) -> RevisedProposal:
    """Merge four Revision batches and run full proposal/revision validation."""
    payloads = _validated_batch_payloads(
        raw_batches,
        REVISED_PROPOSAL_BATCH_MODELS,
    )
    proposal = _merge_proposal_payloads(payloads)
    return RevisedProposal.model_validate(
        {
            "proposal": proposal,
            "applied_critique_summary": payloads[0][
                "applied_critique_summary"
            ],
            "unresolved_issues": payloads[0]["unresolved_issues"],
        }
    )


# Versioned S1 contract uses these SAME group boundaries for Single and Writer,
# independently of provider. The old batch models above serve historical paths.
from schemas.contract_outputs import ContractProposal


CONTRACT_BATCH_MODELS = tuple(
    create_model(
        f"ContractProposalBatch{number}", __config__=_BATCH_CONFIG,
        **({"title": _field_definition(ContractProposal, "title")} if number == 1 else {}),
        **{field: _field_definition(ContractProposal, field) for field in section_fields},
    )
    for number, section_fields in enumerate(PROPOSAL_SECTION_BATCHES, start=1)
)


def merge_contract_batches(raw_batches) -> ContractProposal:
    payloads = _validated_batch_payloads(raw_batches, CONTRACT_BATCH_MODELS)
    merged = {}
    for payload in payloads:
        merged.update(payload)
    return ContractProposal.model_validate(merged)


def build_contract_batch_prompt(base_prompt, number, *, version=1):
    """The common, provider-neutral prompt for one 4/3/3/3 proposal batch."""
    import json
    from schemas.workflow import SECTION_FIELD_BY_TITLE
    fields = PROPOSAL_SECTION_BATCHES[number - 1]
    titles = {field: title for title, field in SECTION_FIELD_BY_TITLE.items() if field in fields}
    return (f"{base_prompt}\n\nBatch {number}/4; artifact_version={version}. "
            "Return exactly these section fields and their exact titles: " + json.dumps(titles) +
            (" Include the proposal title." if number == 1 else " Do not include a top-level title.") +
            " Keep all required provenance fields. Use [source_id] inline citations. "
            "No shortened schema, extra sections, evidence pruning or additional planning role.")
