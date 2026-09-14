"""Lossless prompt/schema compaction, without provider calls or quality shortcuts."""
from copy import deepcopy
import json
from pathlib import Path

from evaluation.s2_fixtures import synthetic_artifact
from evaluation.two_stage_fixtures import synthetic_stage_payload
from schemas.contract_outputs import CONTRACT_VERSION, ContractResearchAnalysis
from workflow.contract_context import ContractContext
from workflow.contract_generation import COMMON_INSTRUCTION, ContractGenerator, PROMPT_VERSION
from workflow.generation_constraints import bounded_response_model
from workflow.two_stage_generation import BODY_INSTRUCTION, SelectionPlan, _at, project_body


ROOT = Path(__file__).resolve().parents[1] / 'docs/final_sprint/s0-v1'


def context():
    return ContractContext.from_case(ROOT, 'ai_education', condition='D')


def selection_plan():
    ctx = context()
    data = synthetic_artifact(ctx, 'research', version=1, inputs={})
    return ctx, data, SelectionPlan(ContractResearchAnalysis,
                                  project_body(ContractResearchAnalysis, data), ctx)


class RecordingClient:
    def __init__(self, ctx):
        self.ctx, self.calls = ctx, []

    def generate_structured_once(self, prompt, schema, **kwargs):
        self.calls.append((prompt, schema, kwargs))
        data = synthetic_artifact(self.ctx, 'research', version=1, inputs={})
        return schema.model_validate(synthetic_stage_payload(schema, data))


def test_two_stages_share_system_and_complete_frozen_prefix():
    ctx = context()
    client = RecordingClient(ctx)
    generator = ContractGenerator(client)
    generator.generate(ctx, 'research')
    assert len(client.calls) == 2
    systems = [kwargs['system_instruction'] for _, _, kwargs in client.calls]
    assert systems == [COMMON_INSTRUCTION, COMMON_INSTRUCTION]
    assert BODY_INSTRUCTION not in systems[0]
    body_prompt, grounding_prompt = [call[0] for call in client.calls]
    assert body_prompt.count(BODY_INSTRUCTION) == 1
    prefixes = [prompt.split('\n\nGENERATION_INSTRUCTIONS:\n', 1)[0]
                for prompt in (body_prompt, grounding_prompt)]
    assert prefixes[0] == prefixes[1]
    assert prefixes[0].startswith(PROMPT_VERSION + '\nFROZEN_INPUT_DATA:\n')
    payload = json.loads(prefixes[0].split('\nFROZEN_INPUT_DATA:\n', 1)[1])
    assert payload == ctx.input_payload('research')
    assert generator.tasks[0].completed
    assert generator.tasks[0].first_output_passed
    assert CONTRACT_VERSION == 'proposal-grounding-v5-two-stage'


def test_body_positions_reconstruct_every_original_candidate_without_mutating_audit():
    _, _, plan = selection_plan()
    before = deepcopy(plan.catalog())
    display = json.loads(plan.prompt().split('FROZEN_DRAFT_AND_SELECTIONS:\n', 1)[1])
    assert display['draft'] == plan.body
    assert display['catalog']['groups'] == plan.groups
    assert set(display['catalog']['body_spans']) == set(plan.body_spans)
    for span_id, compact in display['catalog']['body_spans'].items():
        assert set(compact) == {'path', 'start', 'end'}
        exact = _at(display['draft'], compact['path'])[compact['start']:compact['end']]
        assert exact == plan.body_spans[span_id]['text']
    assert plan.catalog() == before
    assert len(json.dumps(display['catalog']['body_spans'])) < len(json.dumps(plan.body_spans))


def test_body_offsets_are_unicode_characters_and_end_exclusive():
    ctx, data, _ = selection_plan()
    data['market_trends'][0]['finding'] = '教育辅助需要检验。第二句保留完整内容，包括 emoji 🧠。'
    plan = SelectionPlan(ContractResearchAnalysis, project_body(ContractResearchAnalysis, data), ctx)
    display = json.loads(plan.prompt().split('FROZEN_DRAFT_AND_SELECTIONS:\n', 1)[1])
    spans = display['catalog']['body_spans']
    for span_id, span in spans.items():
        assert _at(display['draft'], span['path'])[span['start']:span['end']] == plan.body_spans[span_id]['text']
    assert any('🧠' in span['text'] for span in plan.body_spans.values())


def test_shared_native_evidence_enum_retains_full_closed_set_and_canonical_output():
    ctx, data, plan = selection_plan()
    bounded = bounded_response_model(plan.schema, ctx.finance.value_ids, packet=ctx.packet)
    raw = bounded.model_json_schema()
    enum_schema = raw['$defs']['EvidenceSpanId']
    assert enum_schema['type'] == 'string'
    assert enum_schema['enum'] == list(plan.evidence_spans)
    selected = [definition for name, definition in raw['$defs'].items()
                if name.startswith('SelectedClaim')]
    assert len(selected) == len(plan.groups)
    for definition in selected:
        field = definition['properties']['evidence_span_ids']
        assert field['items'] == {'$ref': '#/$defs/EvidenceSpanId'}
        assert field['maxItems'] == len(plan.evidence_spans)
        assert field['uniqueItems'] is True
    selection = synthetic_stage_payload(plan.schema, data)
    candidate, mapping = plan.assemble(selection)
    assert candidate.model_dump(mode='json') == ContractResearchAnalysis.model_validate(data).model_dump(mode='json')
    assert mapping
    ctx.validate(candidate, version=1)


def test_shared_enum_reduces_native_schema_without_changing_values():
    _, _, plan = selection_plan()
    compact = plan.schema.model_json_schema()
    expanded = deepcopy(compact)
    enum = expanded['$defs'].pop('EvidenceSpanId')
    for name, definition in expanded['$defs'].items():
        if name.startswith('SelectedClaim'):
            definition['properties']['evidence_span_ids']['items'] = deepcopy(enum)
    assert len(json.dumps(compact)) < len(json.dumps(expanded))


def test_inherited_lookup_preserves_original_anchors_without_selecting_new_evidence():
    ctx, data, _ = selection_plan()
    upstream = ctx.accept('research', data)
    body = project_body(ContractResearchAnalysis, data)
    plan = SelectionPlan(ContractResearchAnalysis, body, ctx, upstream=(upstream,))
    before = deepcopy(plan.catalog())
    selection = synthetic_stage_payload(plan.schema, data)
    original_selection = deepcopy(selection)
    from workflow.grounding import claims_in
    for claim in claims_in(upstream.payload()):
        entries = plan.inherited_claim_evidence[claim.claim_id]
        assert len(entries) == 1
        assert entries[0]['upstream_role'] == 'research'
        assert entries[0]['upstream_version'] == 1
        exact = [plan.evidence_spans[key] for key in entries[0]['evidence_span_ids']]
        assert exact == [anchor.model_dump(mode='json') for anchor in claim.source_anchors]
    displayed = json.loads(plan.prompt().split('FROZEN_DRAFT_AND_SELECTIONS:\n', 1)[1])['catalog']
    assert displayed['inherited_claim_evidence'] == plan.inherited_claim_evidence
    assert plan.catalog() == before
    candidate, _ = plan.assemble(selection)
    assert selection == original_selection
    assert candidate.model_dump(mode='json') == ContractResearchAnalysis.model_validate(data).model_dump(mode='json')
    # The lookup cannot populate a missing selection or override model choices.
    removed = deepcopy(selection)
    first_claim = removed['g1']['claims'][0]
    for annotation in removed.values():
        for claim in annotation['claims']:
            if claim['claim_id'] == first_claim['claim_id']:
                claim.update(evidence_span_ids=[], evidence_status='unsupported', source_support='none')
    unsupported, _ = plan.assemble(removed)
    assert unsupported.market_trends[0].claims[0].source_anchors == []
    import pytest
    with pytest.raises(ValueError, match='lost upstream sources or anchors'):
        ctx.validate(unsupported, version=1, upstream=(upstream,))
