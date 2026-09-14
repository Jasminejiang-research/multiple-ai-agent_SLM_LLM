"""Collision diagnostics preserve meaning/evidence equality and submitted data."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from evaluation.s2_fixtures import synthetic_artifact, synthetic_claim
from schemas.contract_outputs import ContractResearchAnalysis
from schemas.evidence import GroundedClaim
from workflow.contract_context import ContractContext
from workflow.grounding import ClaimIdentityCollisionError, validate_grounding


@pytest.fixture(scope="module")
def context():
    return ContractContext.from_case(Path(__file__).resolve().parents[1] / "docs/final_sprint/s0-v1",
        "ai_education", condition="D")


def test_collision_reports_id_both_locations_and_changed_values_without_mutation(context):
    data = synthetic_artifact(context, "research", version=1, inputs={})
    data["customer_notes"][0]["claims"][0]["claim_text"] = "A different assertion."
    artifact = ContractResearchAnalysis.model_validate(data)
    original = artifact.model_dump()
    with pytest.raises(ClaimIdentityCollisionError) as raised:
        validate_grounding(artifact, context.packet, version=1)
    error = raised.value
    assert isinstance(error, ValueError)
    assert error.collision_id == "research.pricing"
    assert error.first_path == "market_trends[0].claims[0]"
    assert error.current_path == "customer_notes[0].claims[0]"
    assert error.differing_fields == ["claim_text"]
    assert json.loads(error.current_values["claim_text"]) == "A different assertion."
    for expected in (error.collision_id, error.first_path, error.current_path, "claim_text", "A different assertion."):
        assert expected in str(error)
    assert artifact.model_dump() == original


def test_first_location_remains_first_after_legal_reuse(context):
    data = synthetic_artifact(context, "research", version=1, inputs={})
    data["competitor_assumptions"][0]["claims"][0]["claim_domain"] = "different-domain"
    with pytest.raises(ClaimIdentityCollisionError) as raised:
        validate_grounding(ContractResearchAnalysis.model_validate(data), context.packet, version=1)
    assert raised.value.first_path == "market_trends[0].claims[0]"
    assert raised.value.current_path == "competitor_assumptions[0].claims[0]"
    assert raised.value.differing_fields == ["claim_domain"]


def test_anchor_and_confidence_differences_remain_legal(context):
    data = synthetic_artifact(context, "research", version=1, inputs={})
    claim = data["customer_notes"][0]["claims"][0]
    claim.update(content_anchor="archived source", confidence="high", confidence_reason="directly_supported")
    artifact = ContractResearchAnalysis.model_validate(data)
    original = artifact.model_dump()
    validate_grounding(artifact, context.packet, version=1)
    assert artifact.model_dump() == original


class Claims(BaseModel):
    claims: list[GroundedClaim]


@pytest.mark.parametrize("field", ["source_ids", "source_anchors", "financial_value_ids"])
def test_list_order_is_still_part_of_identity(context, field):
    claim = synthetic_claim(context, version=1, inputs={})
    first_source = claim["source_ids"][0]
    chunk = next(c for c in context.packet.chunks if c.source_id != first_source)
    source = next(s for s in context.packet.sources if s.source_id == chunk.source_id)
    claim["source_ids"].append(source.source_id)
    claim["source_anchors"].append(dict(source_id=source.source_id, chunk_id=chunk.chunk_id,
        line_start=chunk.line_start, line_end=chunk.line_end, snapshot_sha256=source.txt_sha256, quote=chunk.text))
    claim["financial_value_ids"] = ["first-financial-reference", "second-financial-reference"]
    other = deepcopy(claim)
    other[field].reverse()
    artifact = Claims(claims=[GroundedClaim.model_validate(claim), GroundedClaim.model_validate(other)])
    with pytest.raises(ClaimIdentityCollisionError) as raised:
        validate_grounding(artifact, context.packet, version=1)
    assert raised.value.differing_fields == [field]
    assert raised.value.first_path == "claims[0]" and raised.value.current_path == "claims[1]"


def test_collision_value_excerpts_are_bounded_but_all_changed_fields_are_reported():
    first = {f"field_{n:02d}": "original-" + "x" * 10000 for n in range(12)}
    current = {key: "changed-" + "y" * 10000 for key in first}
    before = deepcopy((first, current))
    error = ClaimIdentityCollisionError("same-id", "claims[0]", "claims[1]", first, current)
    assert len(error.differing_fields) == 12
    assert len(error.first_values) == len(error.current_values) == 8
    assert error.omitted_value_fields == 4
    assert all(len(value) <= 240 for values in (error.first_values, error.current_values) for value in values.values())
    assert all(value.endswith("…") for value in error.first_values.values())
    assert len(str(error)) < 5000
    assert (first, current) == before
