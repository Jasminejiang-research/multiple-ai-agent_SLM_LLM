"""Synthetic engineering responses only. Never use as candidate-model or Gold evidence."""
from copy import deepcopy
import json

from schemas.workflow import PROPOSAL_SECTION_FIELD_NAMES, PROPOSAL_SECTION_TITLES
from schemas.review import METRICS, ComponentCritiqueReport
from workflow.contract_context import ROLE_SCHEMAS
from workflow.review_runtime import PhysicalResponse


def request_payload(prompt):
    decoder = json.JSONDecoder()
    for index, char in enumerate(prompt):
        if char == "{":
            try:
                data, _ = decoder.raw_decode(prompt[index:])
                if isinstance(data, dict) and "user_brief" in data:
                    return data
            except json.JSONDecodeError:
                continue
    raise ValueError("mock request has no contract input")


def synthetic_claim(context, *, version, inputs):
    chunk = context.packet.chunks[0]
    source = next(s for s in context.packet.sources if s.source_id == chunk.source_id)
    text = "The archived source includes the quoted pricing excerpt."
    result = dict(claim_id="research.pricing", parent_claim_id=None, claim_text=text,
        claim_type="factual", claim_domain="competitor", evidence_status="sourced_fact",
        source_ids=[source.source_id], source_support="direct", source_quality=.9, source_recency=None,
        support_assessed_by="model_proposed", critic_status="not_reviewed", decision_critical=True,
        high_impact=False, conflict=False, pruned=False, major_issue=False,
        confidence="low", confidence_reason="no_evidence", content_anchor=text,
        source_anchors=[dict(source_id=source.source_id, chunk_id=chunk.chunk_id,
            line_start=chunk.line_start, line_end=chunk.line_end, snapshot_sha256=source.txt_sha256, quote=chunk.text)],
        financial_value_ids=[], premise="", artifact_version=version)
    def inherit(obj):
        if isinstance(obj, dict):
            if obj.get("claim_id") == result["claim_id"]:
                for key in ("major_issue", "conflict", "pruned"):
                    result[key] = result[key] or obj.get(key, False)
                if obj.get("critic_status") in ("unresolved", "unverified_after_revision"):
                    result["critic_status"] = obj["critic_status"]
            for item in obj.values():
                inherit(item)
        elif isinstance(obj, list):
            for item in obj:
                inherit(item)
    inherit(inputs)
    return result


def synthetic_artifact(context, role, *, version, inputs):
    c = synthetic_claim(context, version=version, inputs=inputs)
    financial = [v.model_dump(mode="json") for v in context.finance.expected_values()]
    if role in ("writer", "single"):
        result = {"title": "SYNTHETIC S2 engineering fixture; not a model result"}
        for key, title in zip(PROPOSAL_SECTION_FIELD_NAMES, PROPOSAL_SECTION_TITLES, strict=True):
            result[key] = dict(title=title, content=c["claim_text"] + f" [{c['source_ids'][0]}] Synthetic engineering fixture only.",
                key_claims=[deepcopy(c)], source_ids=c["source_ids"], confidence="low", confidence_reason="no_evidence")
        result["financial_assumptions"]["financial_values"] = financial
        return result
    item = dict(topic="Synthetic pricing evidence", rationale=c["claim_text"], confidence="low",
        confidence_reason="no_evidence", claims=[c])
    result = dict(analysis_summary="Synthetic analysis for offline S2 control-flow checks only.", needs_human_review=[])
    if role == "research":
        item["finding"] = c["claim_text"]
        result.update({key: [deepcopy(item)] for key in ("market_trends", "customer_notes", "competitor_assumptions")})
        result["unsupported_claims"] = []
    elif role == "strategy":
        item["recommendation"] = c["claim_text"]
        result.update({key: [deepcopy(item)] for key in ("value_proposition", "business_model_logic", "gtm_strategy", "moat_hypotheses")})
        result["unsupported_market_data"] = []
    else:
        item.update(assumption=c["claim_text"], value_ids=[financial[0]["value_id"]], needs_validation=[])
        result.update({key: [deepcopy(item)] for key in ("revenue_assumptions", "cost_assumptions", "unit_economics_assumptions")})
        result.update(break_even_discussion="All financial results describe assumptions in an offline scenario.",
            assumption_notice="These are scenario assumptions, not forecasts or observed outcomes.",
            unsupported_financial_claims=[], financial_values=financial)
    return result


def synthetic_report(role, *, score=3, severity=None):
    artifact_role = "writer" if role == "final" else role
    return dict(role=role, artifact_id=f"{artifact_role}.initial", artifact_version=1,
        metrics=[dict(criterion=key, score=score, rationale="Synthetic deterministic gate fixture.",
            evidence_anchor="The archived source includes the quoted pricing excerpt.") for key in METRICS[role]],
        issues=[] if severity is None else [dict(issue_id=f"{role}.issue1", severity=severity,
            criterion=METRICS[role][0], description="Synthetic issue; support still needs human verification.",
            suggested_fix="Disclose the evidence limitation and keep the source and claim identity.",
            affected_claim_ids=["research.pricing"], source_ids=[], artifact_version=1)])


class SyntheticProvider:
    provider = "mock"
    model_exact_id = "synthetic-s2-no-model"

    def __init__(self, context, *, fail_roles=(), severity="high", score=3, before=None):
        self.context, self.fail_roles, self.severity, self.score = context, set(fail_roles), severity, score
        self.calls = []
        self.before = before

    def invoke(self, request):
        self.calls.append(request)
        if self.before:
            replacement = self.before(request, len(self.calls))
            if replacement is not None:
                return replacement
        inputs = request_payload(request.prompt)
        if issubclass(request.schema, ComponentCritiqueReport):
            role = inputs["review_role"]
            data = synthetic_report(role, score=self.score if role in self.fail_roles else 3,
                                    severity=self.severity if role in self.fail_roles else None)
        else:
            canonical = getattr(request.schema, "__canonical_schema__", request.schema)
            role = next((r for r in ("research", "strategy", "finance") if issubclass(canonical, ROLE_SCHEMAS[r])),
                        "single" if self.context.condition == "A" else "writer")
            version = 2 if inputs["previous_artifact"] else 1
            data = synthetic_artifact(self.context, role, version=version, inputs=inputs)
            from evaluation.two_stage_fixtures import synthetic_stage_payload
            data = synthetic_stage_payload(request.schema, data)
        return PhysicalResponse(json.dumps(data), dict(synthetic=True, prompt=10, output=5, total=15), 10, 5, 15)
