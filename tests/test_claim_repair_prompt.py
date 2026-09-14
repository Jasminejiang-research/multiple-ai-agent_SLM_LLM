"""Repair carries the exact identity conflict; nullable rules stay consistent."""
import json
from typing import Literal

from pydantic import BaseModel

from workflow.generation_constraints import repair_feedback
from workflow.grounding import ClaimIdentityCollisionError
from workflow.schema_contract import schema_enum_contract


def test_collision_feedback_keeps_id_both_paths_and_differences_after_error_truncation():
    exc = ClaimIdentityCollisionError('b186f873c_86740511',
        'competitor_assumptions[0].claims[3]', 'competitor_assumptions[1].claims[1]',
        {'claim_text':'Content licensing requires an agreement.', 'claim_type':'assumption'},
        {'claim_text':'FERPA applies to educational records.', 'claim_type':'factual'})
    feedback = json.loads(repair_feedback(exc, '{}', []))
    issue = feedback['violations'][0]
    assert issue['claim_id'] == 'b186f873c_86740511'
    assert issue['first_path'] == 'competitor_assumptions[0].claims[3]'
    assert issue['path'] == 'competitor_assumptions[1].claims[1]'
    assert issue['differing_fields'] == ['claim_text', 'claim_type']
    assert json.loads(issue['first_values']['claim_type']) == 'assumption'
    assert json.loads(issue['current_values']['claim_type']) == 'factual'
    assert 'unchanged' in issue['expected']


def test_nested_cause_retains_collision_feedback():
    inner = ClaimIdentityCollisionError('research.c1','a','b',{'claim_text':'A'},{'claim_text':'B'})
    outer = ValueError('outer validator')
    outer.__cause__ = inner
    feedback = json.loads(repair_feedback(outer, '{}', []))
    assert feedback['violations'][0]['claim_id'] == 'research.c1'


def test_optional_parent_enum_includes_json_null_as_one_union():
    class Schema(BaseModel):
        parent_claim_id: Literal['research.c1', 'research.c2'] | None
    prompt = schema_enum_contract(Schema)
    assert '`parent_claim_id`: exactly one of "research.c1", "research.c2", null.' in prompt
    assert prompt.count('`parent_claim_id`') == 1
    assert '"None"' not in prompt


def test_unrestricted_string_branch_is_not_presented_as_closed_enum():
    class Schema(BaseModel):
        claim_id: str | Literal['old-id']
    assert schema_enum_contract(Schema) == ''


def test_fixed_numeric_boolean_and_null_use_json_literals():
    class Schema(BaseModel):
        artifact_version: Literal[2]
        flag: Literal[True]
        parent: Literal[None]
    prompt = schema_enum_contract(Schema)
    assert '`artifact_version`: exactly one of 2.' in prompt
    assert '`flag`: exactly one of true.' in prompt
    assert '`parent`: exactly one of null.' in prompt
