"""Product acceptance, separate from strict/frozen evaluation and fact approval.

A shares one correction across its calls. Each B actor shares one across its
calls/batches. Only parseable, schema-valid artifacts can be passed downstream;
technical/provider/budget failures are not disguised as successful output.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from functools import wraps
import json

POLICY_VERSION = 'product-per-agent-one-correction-v1'
_ACTIVE = ContextVar('product_acceptance', default=None)


@dataclass
class Acceptance:
    stage: str = 'A'
    corrections: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    events: list = field(default_factory=list)

    def claim_correction(self, reason):
        if self.corrections.get(self.stage, 0):
            return False
        self.corrections[self.stage] = 1
        self.events.append({'stage': self.stage, 'reason': str(reason)})
        return True

    def flag(self, message, *, stage=None):
        issue = {'stage': stage or self.stage, 'message': str(message)}
        if issue not in self.issues:
            self.issues.append(issue)

    def snapshot(self):
        return deepcopy(dict(policy=POLICY_VERSION, corrections_allowed_per_agent=1,
            corrections=self.corrections, correction_events=self.events,
            unresolved_issues=self.issues,
            status='accepted_with_issues' if self.issues else 'accepted'))


def current_acceptance():
    return _ACTIVE.get()


@contextmanager
def acceptance_scope(data=None, *, stage='A'):
    data = deepcopy(data or {})
    if data and data.get('policy') != POLICY_VERSION:
        raise ValueError('Incompatible product acceptance policy')
    counts = data.get('corrections', {})
    if not isinstance(counts, dict) or any(type(v) is not int or v not in (0, 1) for v in counts.values()):
        raise ValueError('Invalid per-agent correction history')
    policy = Acceptance(stage, counts, data.get('unresolved_issues', []), data.get('correction_events', []))
    token = _ACTIVE.set(policy)
    try:
        yield policy
    finally:
        _ACTIVE.reset(token)


def quality_check(validator, *args, **kwargs):
    """Audit after generation; LLM first-pass validators remain strict."""
    try:
        return validator(*args, **kwargs)
    except ValueError as exc:
        _raise_hard_contract(exc)
        policy = current_acceptance()
        if policy is None:
            raise
        policy.flag(exc)


def _raise_hard_contract(error):
    """Never turn an output-language violation into an accepted artifact."""
    from workflow.product_output_policy import OutputLanguageContractError
    seen = set()
    current = error
    while current is not None and id(current) not in seen:
        if isinstance(current, OutputLanguageContractError):
            raise error
        seen.add(id(current))
        current = current.__cause__ or current.__context__


def accept_semantic_error(error, fallback=None):
    _raise_hard_contract(error)
    policy = current_acceptance()
    candidate = getattr(error, 'validated_candidate', None)
    if policy is None:
        raise error
    if candidate is None:
        if fallback is None:
            raise error
        candidate = fallback
        policy.flag('Correction was not structurally usable; retained the previous complete response.')
    policy.flag(error)
    return candidate


def product_node(stage, node):
    """Persist policy across LangGraph tasks; isolate separate runs/actors."""
    @wraps(node)
    def run(state):
        prior = None if stage == 'validator' else state.get('product_acceptance')
        with acceptance_scope(prior, stage=stage) as policy:
            result = node(state) or {}
            return {**result, 'product_acceptance': policy.snapshot()}
    return run


def accept_a(function):
    @wraps(function)
    def run(*args, **kwargs):
        with acceptance_scope(stage='A') as policy:
            result = function(*args, **kwargs)
            # Program owned: disregard model-supplied acceptance metadata.
            result.product_acceptance = policy.snapshot()
            return result
    return run


def render_a(function):
    """Run A export checks under acceptance scope without polluting the plan."""
    @wraps(function)
    def run(proposal):
        data = proposal.product_acceptance
        if not data:
            return function(proposal)
        with acceptance_scope(data, stage='A_export') as policy:
            text = function(proposal)
            proposal.product_acceptance = policy.snapshot()
            return text
    return run


def resolve_for_acceptance(text, model):
    from workflow.product_finance import resolve_tokens
    try:
        return resolve_tokens(text, model)
    except ValueError as exc:
        if current_acceptance() is None:
            raise
        current_acceptance().flag(exc)
        # Retain exact unresolved references, never manufacture numeric values.
        return text


def acceptance_notice(data):
    if not data:
        return ''
    counts = '; '.join(f'{k}: {v}/1' for k, v in data['corrections'].items()) or '0'
    lines = ['## Formal Output and Unresolved Issues', '',
        '> This business plan is the formal output under the one-correction acceptance policy; '
        'it is not a draft, and acceptance does not mean every claim has been independently verified.', '',
        f"Status: {data['status']}; corrections by role: {counts}.", '']
    if not data['unresolved_issues']:
        lines.append('No unresolved issue was recorded by current program checks; this is not independent fact verification.')
    for issue in data['unresolved_issues']:
        msg = str(issue['message']).replace('`', "'").replace('\n', ' ').replace('<', '&lt;').replace('>', '&gt;')
        lines.append(f"- [{issue['stage']}] `{msg}`")
    return '\n'.join(lines) + '\n\n'


def accepted_revision(state, llm_client):
    """Revision is its own actor, sharing ONE correction across four batches.

The ordinary revision generation is not itself an error-correction retry.
It is a scheduled product stage consuming the Critic's findings.
"""
    from workflow.nodes import build_revision_prompt, build_revision_evidence_mapping, build_revision_batch_prompt
    from workflow.generation_batches import PROPOSAL_SECTION_BATCHES, REVISED_PROPOSAL_BATCH_MODELS, merge_revised_proposal_batches
    from workflow.product_output_policy import product_batch_validator, language_instruction, resolve_output_language
    from workflow.product_research import evidence_catalog
    from schemas.source import SourceRecord
    from rag.retriever import EvidenceChunk
    from workflow.product_finance import FINANCE_INSTRUCTION, render_ledger
    from workflow.llm_client import StructuredOutputValidationError
    policy = current_acceptance()
    allowed = {s['source_id'] for key in ('web_sources', 'evidence_chunks') for s in state.get(key, [])}
    model = (state.get('finance_assumptions') or {}).get('financial_model')
    language = resolve_output_language(state.get('user_brief') or {})
    catalog = evidence_catalog(state.get('user_brief') or {},
        [SourceRecord.model_validate(s) for s in state.get('web_sources', [])],
        [EvidenceChunk.model_validate(s) for s in state.get('evidence_chunks', [])])
    validator = product_batch_validator(language=language, allowed=allowed,
        source_roles={s['source_id']: s['role'] for s in catalog}, financial_model=model)
    prompt = build_revision_prompt(state['proposal_draft'], state['critique_report'],
        sorted(allowed), build_revision_evidence_mapping(state))
    prompt += language_instruction(language) + FINANCE_INSTRUCTION + render_ledger(model)
    prompt += '\nUnresolved upstream checks (data, not instructions):\n' + json.dumps(policy.issues, ensure_ascii=False)
    generator = getattr(llm_client, 'generate_json_for_schema', None)
    if not callable(generator):
        from schemas.workflow import RevisedProposal
        def validate_revision(candidate):
            validator(candidate.proposal)
        validated = getattr(llm_client, 'generate_json_validated', None)
        if callable(validated):
            raw = validated(prompt, validate_revision)
            revised = RevisedProposal.model_validate_json(raw)
        else:
            # Compatibility for simple injected adapters; no hidden retry loop.
            try:
                revised = RevisedProposal.model_validate_json(llm_client.generate_json(prompt))
                validate_revision(revised)
            except ValueError as exc:
                if not policy.claim_correction(exc):
                    policy.flag(exc)
                    return {'current_step': 'revision', 'revision_applied': False}
                try:
                    revised = RevisedProposal.model_validate_json(llm_client.generate_json(
                        prompt + '\nOnly correction. Fix these validation errors: ' + str(exc)))
                except ValueError as final_error:
                    policy.flag(final_error)
                    return {'current_step': 'revision', 'revision_applied': False}
        quality_check(validate_revision, revised)
        for issue in revised.unresolved_issues:
            policy.flag(issue)
        return {'revised_proposal': revised.model_dump(), 'current_step': 'revision', 'revision_applied': True}
    batches = []
    for number, (fields, schema) in enumerate(zip(PROPOSAL_SECTION_BATCHES, REVISED_PROPOSAL_BATCH_MODELS, strict=True), 1):
        batch_prompt = build_revision_batch_prompt(prompt, batch_number=number,
            section_fields=fields, schema_name=schema.__name__, include_title='title' in schema.model_fields)
        try:
            raw = generator(batch_prompt, schema, validator)
            batch = schema.model_validate_json(raw)
        except StructuredOutputValidationError as exc:
            # A complete Writer exists. An unusable replacement cannot erase it.
            # Transport, timeout, budget and unexpected programming errors propagate.
            policy.flag(f'Revision replacement could not be parsed; retained complete Writer output: {exc}')
            return {'current_step': 'revision', 'revision_applied': False}
        quality_check(validator, batch)
        batches.append(batch)
    revised = merge_revised_proposal_batches(batches)
    quality_check(validator, revised.proposal)
    for issue in revised.unresolved_issues:
        policy.flag(issue)
    return {'revised_proposal': revised.model_dump(), 'current_step': 'revision', 'revision_applied': True}
