"""Offline raw-wire Critic -> canonical revision acceptance regressions."""
from pathlib import Path

import pytest

from evaluation.s2_fixtures import synthetic_artifact
from schemas.compact_wire import SECTION_KEYS
from schemas.review import METRICS
from workflow.compact_protocol import (
    CRITIC_PATCH_ADAPTER_VERSION, apply_patch_wire, compact_role_output,
    expand_critic_wire, patch_view,
)
from workflow.contract_context import ContractContext, ROLE_SCHEMAS
from workflow.grounding import CitationPollutionError, claims_in


ROOT = Path(__file__).resolve().parents[1] / "docs/final_sprint/s0-v1"


def setup(role="research", *, ambiguous=False):
    context = ContractContext.from_case(ROOT, "ai_education", condition="C")
    candidate = ROLE_SCHEMAS[role].model_validate(
        synthetic_artifact(context, role, version=1, inputs={}))
    if role == "research":
        for group in (candidate.market_trends, candidate.customer_notes, candidate.competitor_assumptions):
            for note in group:
                note.rationale = "This rationale explains the scope of the frozen source excerpt."
    else:
        section = candidate.executive_summary
        claim = section.key_claims[0]
        claim.claim_id = "executive_scope"
        claim.claim_text += " " + " ".join(f"[{source}]" for source in claim.source_ids)
        claim.content_anchor = claim.claim_text
        section.content = claim.claim_text
    if ambiguous:
        candidate.market_trends[0].finding += " " + candidate.market_trends[0].finding
    previous = context.accept(role, candidate)
    wire = compact_role_output(context, role, previous.payload())
    claim = wire.market[0].claims[0] if role == "research" else wire.sections[0].claims[0]
    path = "market.0.text" if role == "research" else "sections.0.text"
    return context, previous, claim, path


def review(context, previous, claim, path, *, enabled=True):
    role = "final" if previous.role == "writer" else previous.role
    raw = {"scores": [2] * len(METRICS[role]), "status": "FAIL", "issues": [{
        "i": "issue001", "sev": "high", "criterion": METRICS[role][0],
        "claims": [claim.i], "fields": [path], "e": [], "fix": "clarify_scope",
        "note": "Clarify the limited scope of the existing statement."}]}
    return expand_critic_wire(context, previous, role, f"{previous.role}.initial", raw,
        critic_patch_adapter=enabled)


@pytest.mark.parametrize("role", ["research", "writer"])
@pytest.mark.parametrize("patch_kind", ["claim", "field"])
def test_raw_critic_patch_full_canonical_acceptance(role, patch_kind):
    context, previous, claim, path = setup(role)
    report = review(context, previous, claim, path)
    canonical_path = "market_trends.0.finding" if role == "research" else f"{SECTION_KEYS[0]}.content"
    assert report.issues[0].target_fields == [canonical_path]
    assert canonical_path in patch_view(context, previous, report)["fields"]
    # Retain every original citation and change only the model-authored sentence.
    replacement = claim.t + " This limited statement still needs human review."
    patch = ({"claims": [{"issue": "issue001", "i": claim.i, "t": replacement}]}
        if patch_kind == "claim" else
        {"fields": [{"issue": "issue001", "path": path, "value": replacement}]})
    candidate, diff = apply_patch_wire(context, previous, report, patch,
        critic_patch_adapter=True)
    accepted = context.accept(role, candidate, version=2, previous=previous,
        unresolved_major=True)
    context.verify_artifact(accepted)
    assert accepted.unresolved_major
    assert len(list(claims_in(candidate))) == len(list(claims_in(previous.payload())))
    assert report.issues[0].severity == "high" and report.revision_required
    revised = [c for c in claims_in(accepted.payload()) if c.claim_id == claim.i]
    assert revised and all(c.critic_status == "unverified_after_revision" for c in revised)
    assert all(c.confidence == "low" for c in revised)
    assert diff["critic_patch_adapter"] == CRITIC_PATCH_ADAPTER_VERSION
    assert all(change["outside_anchor_unchanged"] for change in diff["deterministic_adapter_changes"])


def test_legacy_critic_paths_remain_unchanged():
    context, previous, claim, path = setup()
    report = review(context, previous, claim, path, enabled=False)
    assert report.issues[0].target_fields == [path]
    with pytest.raises(ValueError, match="invalid patch path"):
        patch_view(context, previous, report)


@pytest.mark.parametrize("path", ["market.3.text", "sections.0.text", "market.0.claims.0.q",
    "financial_values.0.value", "invented.path"])
def test_unknown_nonprose_or_wrong_role_targets_rejected(path):
    context, previous, claim, _ = setup()
    with pytest.raises(ValueError, match="Critic field target"):
        review(context, previous, claim, path)


def test_ambiguous_parent_anchor_rejected():
    context, previous, claim, path = setup(ambiguous=True)
    report = review(context, previous, claim, path)
    with pytest.raises(ValueError, match="unambiguous parent occurrence"):
        apply_patch_wire(context, previous, report,
            {"claims": [{"issue": "issue001", "i": claim.i, "t": claim.t + " Limited scope."}]},
            critic_patch_adapter=True)


def test_unapproved_existing_field_rejected():
    context, previous, claim, path = setup()
    report = review(context, previous, claim, path)
    with pytest.raises(ValueError, match="Critic-authorized targets"):
        apply_patch_wire(context, previous, report,
            {"fields": [{"issue": "issue001", "path": "customer.0.text",
                "value": "This is a sufficiently long unauthorized replacement statement."}]},
            critic_patch_adapter=True)


@pytest.mark.parametrize("field,value,error", [
    ("t", "This invented citation is never accepted [E99].", CitationPollutionError),
    ("e", ["E99"], CitationPollutionError),
    ("f", ["invented.value"], ValueError),
])
def test_patch_cannot_introduce_unknown_evidence_or_finance(field, value, error):
    context, previous, claim, path = setup()
    report = review(context, previous, claim, path)
    with pytest.raises(error):
        apply_patch_wire(context, previous, report,
            {"claims": [{"issue": "issue001", "i": claim.i, field: value}]},
            critic_patch_adapter=True)
