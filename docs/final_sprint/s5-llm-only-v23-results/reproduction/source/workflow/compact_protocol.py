"""S6 compact prompt, role-view, wire expansion and bounded patch rules."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import math
import re
import unicodedata
from types import UnionType
from typing import Any, get_args, get_origin

from pydantic import BaseModel

from schemas.compact_wire import (
    ClaimWire, CriticWire, FinanceNoteWire, FinanceWire, FinanceNote8Wire, Finance8Wire,
    PatchWire, ProposalWire,
    ResearchNoteWire, ResearchWire, ROLE_WIRES, SECTION_KEYS, StrategyNoteWire,
    StrategyWire, SectionWire, WIRE_VERSION,
)
from schemas.contract_outputs import (
    ContractFinanceAssumptions, ContractFinancialSection, ContractProposal,
    ContractResearchAnalysis, ContractSection, ContractStrategyAnalysis,
    GroundedFinanceAssumption, GroundedFinding, GroundedInsight,
)
from schemas.evidence import GroundedClaim, canonical_hash
from schemas.review import ComponentCritiqueReport, METRICS, ReviewIssue, ReviewMetric
from schemas.workflow import SECTION_FIELD_BY_TITLE
from workflow.grounding import (CitationPollutionError, claims_in, walk_models, lineage_ancestor_ids,
    same_text_lineage_identity_members)

PROMPT_VERSION = "compact-generation-v13-s5-source-quality-scale"
CONTEXT_VERSION = "deterministic-role-view-v1-s6"
CONFIG_VERSION = "review-run-v2-s6-compact"
GEMINI_8192_CONFIG_VERSION = "review-run-v3-s6-compact-gemini-8192"
GEMINI_8192_MINIMAL_CONFIG_VERSION = "review-run-v4-s6-compact-gemini-8192-minimal"
GEMINI_8192_CONTRACT_CONFIG_VERSION = "review-run-v5-s6-compact-gemini-8192-contract"
GEMINI_8192_THINKING_CONFIG_VERSION = "review-run-v6-s6-compact-gemini-8192-thinking1024"
GEMINI_8192_REASON200_CONFIG_VERSION = "review-run-v7-s6-compact-gemini-8192-id3-reason200"
GEMINI_8192_REPAIR_CONFIG_VERSION = "review-run-v8-s6-compact-gemini-8192-conservative-repair"
GEMINI_8192_PUNCTUATION_REPAIR_CONFIG_VERSION = (
    "review-run-v9-s6-compact-gemini-8192-conservative-punctuation-repair")
GEMINI_8192_PREMISE_CONFIG_VERSION = (
    "review-run-v10-s6-compact-gemini-8192-punctuation-recommendation-premise")
GEMINI_8192_TEXT_EQUALS_CLAIM_CONFIG_VERSION = (
    "review-run-v11-s6-compact-gemini-8192-text-equals-claim")
GEMINI_8192_CITATION_CONTRACT_CONFIG_VERSION = (
    "review-run-v12-s6-compact-gemini-8192-inline-citation-contract")
GEMINI_8192_CITATION_FORMAT_CONFIG_VERSION = (
    "review-run-v13-s6-compact-gemini-8192-citation-bracket-format")
GEMINI_8192_GAP_COUNT_CONFIG_VERSION = (
    "review-run-v14-s6-compact-gemini-8192-gap-count-inline-citation-mirror")
GEMINI_8192_EXACT_CARDINALITY_CONFIG_VERSION = (
    "review-run-v15-s6-compact-gemini-8192-exact-array-cardinality")
GEMINI_8192_FINANCE_MARKER_CONFIG_VERSION = (
    "review-run-v16-s6-compact-gemini-8192-structured-finance-markers")
GEMINI_8192_FINANCE_MARKER_PREFIX_CONFIG_VERSION = (
    "review-run-v17-s6-compact-gemini-8192-finance-marker-prefix")
GEMINI_8192_SOURCE_QUALITY_CONFIG_VERSION = (
    "review-run-v18-s6-compact-gemini-8192-source-quality-scale")
GEMINI_8192_BODY_ASSEMBLY_CONFIG_VERSION = (
    "review-run-v19-s6-compact-gemini-8192-existing-claim-body-assembly")
GEMINI_8192_FINANCE_CAPACITY_CONFIG_VERSION = (
    "review-run-v20-s6-compact-gemini-8192-finance-claims-eight")
GEMINI_8192_FINANCE_PARTITION_CONFIG_VERSION = (
    "review-run-v21-s6-compact-gemini-8192-finance-partition-recency")
GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION = (
    "review-run-v22-s6-compact-gemini-8192-finance-assumption-notice")
GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION = (
    "review-run-v23-s6-compact-gemini-8192-repair-instruction-admission")
GEMINI_8192_LINEAGE_ID_CONFIG_VERSION = (
    "review-run-v24-s6-compact-gemini-8192-lineage-identity-continuity")
GEMINI_8192_ID_COLLISION_CONFIG_VERSION = (
    "review-run-v25-s6-compact-gemini-8192-claim-id-collision")
GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION = (
    "review-run-v26-s6-compact-gemini-8192-dual-declared-lineage")
FINANCE_CAPACITY_CONFIG_VERSIONS = (GEMINI_8192_FINANCE_CAPACITY_CONFIG_VERSION,
    GEMINI_8192_FINANCE_PARTITION_CONFIG_VERSION, GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION,
    GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION, GEMINI_8192_LINEAGE_ID_CONFIG_VERSION,
    GEMINI_8192_ID_COLLISION_CONFIG_VERSION, GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION)
DUAL_DECLARED_LINEAGE_VERSION = "dual-declared-exact-text-lineage-v1-s5"
CLAIM_ID_COLLISION_ADAPTER_VERSION = "declared-upstream-claim-id-split-v1-s5"
LINEAGE_IDENTITY_CONTINUITY_VERSION = "explicit-same-text-lineage-identity-v1-s5"
FINANCE_CAPACITY_WIRE_VERSION = "compact-finance-claims-eight-v1-s5"
EXACT_TEXT_PARENT_LINEAGE_VERSION = "exact-text-parent-lineage-v1-s5"
CANONICAL_CITATION_WIRE_ADAPTER_VERSION = "existing-anchor-citation-roundtrip-v1-s5"
SOURCE_ALIAS_SELECTION = "first_existing_selected_anchor_no_support_inference"
MECHANICAL_REPAIR_VERSION = "conservative-claim-repair-v1-s5"
MECHANICAL_PUNCTUATION_REPAIR_VERSION = "conservative-claim-repair-v2-s5-terminal-punctuation"
MECHANICAL_SOURCE_DISPOSITION_REPAIR_VERSION = "conservative-claim-repair-v3-s5-source-disposition"
MECHANICAL_CITATION_FORMAT_REPAIR_VERSION = "conservative-claim-repair-v4-s5-citation-bracket-format"
MECHANICAL_INLINE_CITATION_REPAIR_VERSION = "conservative-claim-repair-v5-s5-inline-citation-mirror"
MECHANICAL_FINANCE_MARKER_REPAIR_VERSION = "conservative-claim-repair-v6-s5-structured-finance-markers"
MECHANICAL_FINANCE_MARKER_PREFIX_REPAIR_VERSION = "conservative-claim-repair-v7-s5-finance-marker-prefix"
MECHANICAL_SOURCE_QUALITY_REPAIR_VERSION = "conservative-claim-repair-v8-s5-source-quality-scale"
MECHANICAL_BODY_ASSEMBLY_REPAIR_VERSION = "conservative-claim-repair-v9-s5-existing-claim-body-assembly"
MECHANICAL_FINANCE_PARTITION_REPAIR_VERSION = "conservative-claim-repair-v10-s5-finance-partition-recency"
MECHANICAL_FINANCE_NOTICE_REPAIR_VERSION = "conservative-claim-repair-v11-s5-finance-assumption-notice"
FINANCE_ASSUMPTION_POLICY_SENTENCE = "Figures are scenario assumptions, not forecasts."
CRITIC_PATCH_ADAPTER_VERSION = "compact-critic-patch-adapter-v1-s5"
LEGACY_PROTOCOL = "body-then-grounding-v1"
INSTRUCTION_LIMIT = 500
MVP30_SECONDS = 1800
VALID_PLAN_SECONDS = 3600

SYSTEM_INSTRUCTION = (
    "Return compact schema-valid JSON; no echo. Each note/section text=sole claim t. "
    "text/t<=100;i>=3;d<=200. p for assumption/projection/recommendation. Only e uses [E##] in text/t; "
    "put f IDs only in f, never [f] or [F-f] in text/t. e=[]: no citation. Preserve IDs/uncertainty; never browse/invent "
    "facts, evidence, finance or support."
)
ROLE_INSTRUCTIONS = {
    "research": "Exactly 1 object in each of market, customer, competition; never 2. One claim each; text=t; gaps 0..3.",
    "strategy": "Exactly 1 object in each of value, model, gtm, moat; never 2. One claim each; text=t; gaps 0..3.",
    "finance": "Exactly 1 object in each of revenue, costs, economics; never 2. One claim each; text=t; gaps 0..3. Code adds numbers.",
    "single": "13 sections in given order; one 40-100 char sentence/claim each; text=t exactly; schema enums/short IDs only.",
    "writer": "13 sections in given order; one 40-100 char sentence/claim each; text=t exactly; schema enums/short IDs only.",
    "research_critic": "Return the fixed score count; no issues for PASS, at most one shortest targeted issue for FAIL.",
    "strategy_critic": "Return the fixed score count; no issues for PASS, at most one shortest targeted issue for FAIL.",
    "finance_critic": "Return the fixed score count; no issues for PASS, at most one shortest targeted issue for FAIL.",
    "final_critic": "Return the fixed score count; no issues for PASS, at most one shortest targeted issue for FAIL.",
    "revision": "Return the smallest schema-valid patch for listed targets; add no IDs and never rewrite the whole artifact.",
}
REPAIR_INSTRUCTION = "Correct the reported structure only; return JSON. Do not add facts, IDs, support, numbers or prose."
SHORT_REPAIR_INSTRUCTION = "Repair structure only; no added content or IDs."
REPAIR_INSTRUCTION_VERSION = "compact-structure-repair-instruction-v1-s5"

CLAIM_PROMPT_CONTRACT = {
    "i": "claim ID; at least 3 chars; unique within the response",
    "t": "equal to parent text character-for-character; <=100 chars",
    "d": "brief reason; 2-200 chars",
    "k": ["factual", "assumption", "recommendation", "projection"],
    "s": ["sourced_fact", "needs_validation", "assumption", "unsupported"],
    "ss": ["direct", "partial", "contextual", "none"],
    "q": "0..1; never 1..5",
    "c": ["low", "medium", "high"],
    "cr": ["no_evidence", "partial_support", "conflict", "assumption_dominant", "pruned",
           "critic_unresolved", "directly_supported"],
    "rules": ["sourced_fact=>k=factual,e nonempty,ss=direct",
              "k assumption/projection=>s=assumption,p nonempty; recommendation=>p nonempty",
              "e uses only E## from view; mirror each e as a separate [E##] token in parent text/t; e=[]=>no citation",
              "f uses only finance value IDs from view; never put [f ID] or [F-f ID] in text/t"],
}


def prompt_contract(role: str) -> dict[str, Any]:
    if role in ("single", "writer"):
        return {"section_keys": list(SECTION_KEYS), "sections": 13,
            "each_section": "one 40-100 char sentence; claims exactly 1; text=claim t; selected e mirrored as [E##]",
            "claim": CLAIM_PROMPT_CONTRACT}
    if role == "research":
        return {"exactly_one_object_each": ["market", "customer", "competition"],
            "each_note": "one short text with one claim; text=claim t; selected e mirrored as [E##]",
            "gaps": "0..3 claims",
            "claim": CLAIM_PROMPT_CONTRACT}
    if role == "strategy":
        return {"exactly_one_object_each": ["value", "model", "gtm", "moat"],
            "each_note": "one short text with one claim; text=claim t; selected e mirrored as [E##]",
            "gaps": "0..3 claims",
            "claim": CLAIM_PROMPT_CONTRACT}
    if role == "finance":
        return {"exactly_one_object_each": ["revenue", "costs", "economics"],
            "each_note": "one short text with one claim; text=claim t; selected e mirrored as [E##]",
            "gaps": "0..3 claims",
            "claim": CLAIM_PROMPT_CONTRACT}
    if role.endswith("_critic"):
        return {"scores": "one integer 0..4 per fixed metric", "status": ["PASS", "FAIL"],
            "issues": "[] for PASS; <=1 for FAIL", "sev": ["low", "medium", "high", "critical"]}
    if role == "revision":
        return {"patch": "only listed issue IDs, claim IDs and field paths; <=1 smallest change"}
    raise ValueError("unknown compact prompt role")

ROLE_OUTPUT_TOKENS = {
    "research": 450, "research_critic": 180, "strategy": 500,
    "strategy_critic": 180, "finance": 600, "finance_critic": 180,
    "writer": 1800, "single": 1800, "final_critic": 250, "revision": 300,
}
GEMINI_8192_ROLE_OUTPUT_TOKENS = {role: 8192 for role in ROLE_OUTPUT_TOKENS}
ROLE_INPUT_TOKENS = {
    "research": 2500, "research_critic": 2000, "strategy": 2600,
    "strategy_critic": 2000, "finance": 3000, "finance_critic": 2000,
    "writer": 6500, "single": 6500, "final_critic": 3500, "revision": 1800,
}
ROLE_SECONDS = {
    "research": 240, "research_critic": 90, "strategy": 240,
    "strategy_critic": 90, "finance": 300, "finance_critic": 90,
    "writer": 420, "single": 420, "final_critic": 150, "revision": 180,
}

BRIEF_KEYS = {
    "research": ("company_or_product_name", "industry", "target_customer", "problem", "solution",
                 "stage", "known_competitors"),
    "strategy": ("company_or_product_name", "industry", "target_customer", "problem", "solution",
                 "business_model", "geography", "proposal_goal", "stage", "known_competitors",
                 "additional_context", "decision_questions", "constraints"),
    "finance": ("company_or_product_name", "business_model", "proposal_goal", "stage",
                "decision_questions", "constraints", "financial_inputs"),
    "writer": (), "single": (),
}


@dataclass(frozen=True)
class PromptEnvelope:
    prompt: str
    system_instruction: str
    view_sha256: str
    normalized_prompt_sha256: str
    wire_schema_sha256: str
    wire_schema_bytes: int
    instruction_chars: int
    full_prompt_chars: int
    full_prompt_utf8_bytes: int


def instruction_for(role: str, *, repair: bool = False, config_version: str | None = None) -> str:
    role_instruction = ROLE_INSTRUCTIONS["revision" if role == "revision" else role]
    repair_instruction = (SHORT_REPAIR_INSTRUCTION
        if config_version in (GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION,
            GEMINI_8192_LINEAGE_ID_CONFIG_VERSION, GEMINI_8192_ID_COLLISION_CONFIG_VERSION,
            GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION) else REPAIR_INSTRUCTION)
    value = SYSTEM_INSTRUCTION + " " + role_instruction + ((" " + repair_instruction) if repair else "")
    if len(value) > INSTRUCTION_LIMIT:
        raise ValueError(f"instruction limit exceeded for {role}: {len(value)} > {INSTRUCTION_LIMIT}")
    return value


def evidence_catalog(packet) -> dict[str, dict[str, Any]]:
    sources = {source.source_id: source for source in packet.sources}
    result = {}
    for index, chunk in enumerate(packet.chunks, 1):
        source = sources[chunk.source_id]
        result[f"E{index:02d}"] = {
            "source_id": source.source_id,
            "chunk_id": chunk.chunk_id,
            "line_start": chunk.line_start,
            "line_end": chunk.line_end,
            "snapshot_sha256": source.txt_sha256,
            "quote": chunk.text,
            "title": source.title,
            "limitation": source.limitation,
        }
    return result


def _short_evidence_view(packet, ids: set[str] | None = None) -> list[dict[str, Any]]:
    catalog = evidence_catalog(packet)
    selected = catalog if ids is None else {key: value for key, value in catalog.items() if key in ids}
    return [dict(id=key, text=value["quote"])
            for key, value in selected.items()]


def _finance_view(context) -> dict[str, Any]:
    spec = context.finance.prompt_spec()
    input_columns = ("value_id", "value", "unit", "currency", "period", "origin")
    result_columns = ("value_id", "value", "unit", "currency", "period", "formula_id",
                      "rounding_policy")
    values = [row.model_dump(mode="json") for row in context.finance.expected_values()]
    formula_ids = [row["formula_id"] for row in values if row.get("formula_id")]
    formula_prefix = (formula_ids[0].rsplit("/", 1)[0] + "/") if formula_ids else ""
    if any(not value.startswith(formula_prefix) for value in formula_ids):
        formula_prefix = ""
    compact_values = [dict(row, formula_id=(row.get("formula_id") or "").removeprefix(formula_prefix) or None)
                      for row in values]
    inputs = [[row.get(key) for key in input_columns] for row in spec["inputs"]]
    results = [[row.get(key) for key in result_columns] for row in compact_values]
    return {"version": spec["version"], "input_columns": input_columns, "inputs": inputs,
            "result_columns": result_columns, "formula_prefix": formula_prefix, "results": results,
            "rules": "Frozen Decimal formulas; money 2dp HALF_UP, ratios 4dp, counts exact; assumptions are not forecasts."}


def _eid_by_chunk(packet) -> dict[str, str]:
    return {entry["chunk_id"]: eid for eid, entry in evidence_catalog(packet).items()}


def _claim_citation_aliases(claims, packet):
    by_chunk = _eid_by_chunk(packet)
    aliases = {}
    for claim in claims:
        for anchor in claim.source_anchors:
            if anchor.chunk_id not in by_chunk:
                raise CitationPollutionError("canonical anchor is outside frozen compact mapping")
            eid = by_chunk[anchor.chunk_id]
            selected = aliases.setdefault(anchor.source_id, [])
            if eid not in selected:
                selected.append(eid)
    return aliases


def _compact_existing_citations(text, aliases, *, reject_ambiguous=True,
                                ordered_repeated_claim=False):
    selected = {eid for ids in aliases.values() for eid in ids}
    ordered = {source: iter(ids) for source, ids in aliases.items()
        if ordered_repeated_claim and len(ids) > 1 and text.count(f"[{source}]") == len(ids)}
    def replace(match):
        ref = match.group(1)
        if ref in selected:
            return match.group(0)
        if ref not in aliases:
            raise CitationPollutionError("canonical prose reference has no selected frozen anchor")
        ids = aliases[ref]
        if ref in ordered:
            return f"[{next(ordered[ref])}]"
        if reject_ambiguous and len(ids) != 1:
            raise CitationPollutionError("canonical body citation is ambiguous outside its claim span")
        return f"[{ids[0]}]"
    return re.sub(r"\[([A-Za-z0-9_.:-]+)\]", replace, text)


def _compact_parent_citations(text, claims, packet):
    """Reverse each exact claim span using its own selected anchors first."""
    changes = {}
    for claim in claims:
        compact = _compact_existing_citations(claim.claim_text,
            _claim_citation_aliases([claim], packet), ordered_repeated_claim=True)
        if claim.claim_text in changes and changes[claim.claim_text] != compact:
            raise CitationPollutionError("identical canonical claim spans have ambiguous selected anchors")
        changes[claim.claim_text] = compact
    # Longest spans first avoids changing a shorter embedded anchor prematurely.
    for before in sorted(changes, key=len, reverse=True):
        text = text.replace(before, changes[before])
    # A source-level marker outside exact claim spans remains source-level: the
    # first already-selected anchor is only its reversible transport alias.
    return _compact_existing_citations(text, _claim_citation_aliases(claims, packet),
        reject_ambiguous=False)


def _claim_to_wire(claim: GroundedClaim, packet, *, compact_citations=False) -> dict[str, Any]:
    by_chunk = _eid_by_chunk(packet)
    try:
        eids = [by_chunk[anchor.chunk_id] for anchor in claim.source_anchors]
    except KeyError as exc:
        raise CitationPollutionError("canonical claim anchor is outside the frozen compact mapping") from exc
    text = (_compact_existing_citations(claim.claim_text, _claim_citation_aliases([claim], packet),
        ordered_repeated_claim=True)
        if compact_citations else claim.claim_text)
    return dict(i=claim.claim_id, pi=claim.parent_claim_id, t=text, k=claim.claim_type,
        d=claim.claim_domain, s=claim.evidence_status, e=eids, f=claim.financial_value_ids,
        ss=claim.source_support, q=claim.source_quality, r=claim.source_recency, p=claim.premise,
        dc=claim.decision_critical, hi=claim.high_impact, cf=claim.conflict,
        c=claim.confidence, cr=claim.confidence_reason)


def _deduplicated_claim_wires(candidate, packet, *, compact_citations=False) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for claim in claims_in(candidate):
        wire = _claim_to_wire(claim, packet, compact_citations=compact_citations)
        prior = result.get(claim.claim_id)
        if prior is not None and prior != wire:
            raise ValueError("same canonical claim ID has conflicting compact representations")
        result[claim.claim_id] = wire
    return list(result.values())


def artifact_capsule(artifact, packet, *, compact_citations=False) -> dict[str, Any]:
    candidate = artifact.payload()
    unresolved = [{
        "claim": claim.claim_id,
        "critic_status": claim.critic_status,
        "major": claim.major_issue,
        "pruned": claim.pruned,
        "conflict": claim.conflict,
    } for claim in claims_in(candidate) if claim.major_issue or claim.pruned or claim.conflict
        or claim.critic_status in ("unresolved", "unverified_after_revision")]
    return {
        "role": artifact.role,
        "version": artifact.version,
        "claims": _deduplicated_claim_wires(candidate, packet, compact_citations=compact_citations),
        "unresolved": unresolved,
        "unresolved_major": artifact.unresolved_major,
    }


def role_wire_schema(role: str, config_version: str | None = None) -> type[BaseModel]:
    if role == "finance" and config_version in FINANCE_CAPACITY_CONFIG_VERSIONS:
        return Finance8Wire
    return ROLE_WIRES[role]


def role_view(context, role: str, *, upstream=(), previous=None, review=None,
              config_version: str | None = None) -> dict[str, Any]:
    compact_citations = config_version in FINANCE_CAPACITY_CONFIG_VERSIONS
    brief = context.brief
    keys = BRIEF_KEYS.get(role, ())
    brief_view = ({key: value for key, value in brief.items() if key != "financial_inputs"}
                  if role in ("single", "writer") else {key: brief[key] for key in keys})
    if role == "finance":
        # The finance table below is the canonical compact representation of
        # these inputs; do not transmit the verbose brief copy as well.
        brief_view.pop("financial_inputs", None)
    evidence_ids = None
    if upstream and role in ("strategy", "finance", "writer"):
        by_chunk = _eid_by_chunk(context.packet)
        evidence_ids = {by_chunk[anchor.chunk_id] for artifact in upstream
            for claim in claims_in(artifact.payload()) for anchor in claim.source_anchors}
    view = {
        "version": CONTEXT_VERSION,
        "brief": brief_view,
        "evidence": _short_evidence_view(context.packet, evidence_ids),
        "upstream": [artifact_capsule(artifact, context.packet,
            compact_citations=compact_citations) for artifact in upstream],
        "finance": _finance_view(context) if role in ("single", "finance", "writer") else None,
    }
    if role.endswith("_critic"):
        if len(upstream) != 1:
            raise ValueError("compact Critic requires exactly one reviewed artifact")
        artifact = upstream[0]
        review_role = "final" if role == "final_critic" else role.removesuffix("_critic")
        compact = compact_role_output(context, artifact.role, artifact.payload(),
            config_version=config_version).model_dump(mode="json")
        eids = {eid for claim in _deduplicated_claim_wires(artifact.payload(), context.packet,
                compact_citations=compact_citations)
                for eid in claim["e"]}
        view.update(brief={key: brief[key] for key in (
            "company_or_product_name", "target_customer", "problem", "solution", "stage",
            "decision_questions", "constraints")}, evidence=_short_evidence_view(context.packet, eids),
            reviewed_artifact={"id": f"{artifact.role}.initial", "version": artifact.version,
                "sha256": artifact.sha256, "wire": compact}, fixed_metrics=METRICS[review_role])
    if previous is not None:
        view = patch_view(context, previous, review, compact_citations=compact_citations)
    if config_version in (GEMINI_8192_FINANCE_PARTITION_CONFIG_VERSION, GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION,
            GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION, GEMINI_8192_LINEAGE_ID_CONFIG_VERSION,
            GEMINI_8192_ID_COLLISION_CONFIG_VERSION, GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION):
        from workflow.compact_views import compact_generation_view
        view = compact_generation_view(view, role)
    return view


def _issue_targets(review) -> tuple[set[str], set[str], set[str]]:
    issue_ids, claim_ids, paths = set(), set(), set()
    for issue in review.issues:
        if issue.severity not in ("high", "critical"):
            continue
        issue_ids.add(issue.issue_id)
        claim_ids.update(issue.affected_claim_ids)
        paths.update(issue.target_fields)
    return issue_ids, claim_ids, paths


def patch_view(context, previous, review, *, compact_citations=False) -> dict[str, Any]:
    if review is None:
        raise ValueError("patch view requires the triggering compact Critic report")
    issue_ids, claim_ids, paths = _issue_targets(review)
    if not issue_ids:
        raise ValueError("patch view requires a high/critical issue")
    candidate = previous.payload()
    claims = [_claim_to_wire(claim, context.packet, compact_citations=compact_citations) for claim in claims_in(candidate)
              if claim.claim_id in claim_ids]
    referenced_eids = {eid for claim in claims for eid in claim["e"]}
    issues = [{"i": issue.issue_id, "sev": issue.severity, "criterion": issue.criterion,
        "note": issue.description, "claims": issue.affected_claim_ids,
        "fields": issue.target_fields, "e": issue.evidence_ids,
        "fix": issue.fix_code or issue.suggested_fix}
        for issue in review.issues if issue.issue_id in issue_ids]
    data = candidate.model_dump(mode="json")
    fields = {}
    for path in sorted(paths):
        value = _get_path(data, path)
        if compact_citations and isinstance(value, str):
            selected_claims = list(claims_in(candidate))
            for parent_path, parent, child_claims in _patch_parent_nodes(data):
                if path.startswith(parent_path + "."):
                    selected_claims = [GroundedClaim.model_validate(claim) for claim in child_claims]
                    break
            referenced_eids.update(eid for ids in _claim_citation_aliases(selected_claims,
                context.packet).values() for eid in ids)
            value = _compact_parent_citations(value, selected_claims, context.packet)
        fields[path] = value
    return {
        "version": CONTEXT_VERSION,
        "artifact": {"role": previous.role, "version": previous.version, "sha256": previous.sha256},
        "issues": issues,
        "claims": claims,
        "fields": fields,
        "evidence": _short_evidence_view(context.packet, referenced_eids),
    }


def make_envelope(context, role: str, schema: type[BaseModel], *, upstream=(), previous=None,
                  review=None, repair=False, error_data=None,
                  config_version: str | None = None) -> PromptEnvelope:
    view = role_view(context, role, upstream=upstream, previous=previous, review=review,
        config_version=config_version)
    body = {"v": PROMPT_VERSION, "role": role, "contract": prompt_contract(role), "view": view}
    if error_data is not None:
        body["validation_error"] = error_data
    prompt = json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    system = instruction_for("revision" if previous is not None else role, repair=repair,
        config_version=config_version)
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False,
                             sort_keys=True, separators=(",", ":"), allow_nan=False)
    normalized = {"prompt": body, "system_instruction": system, "wire_schema": json.loads(schema_json)}
    return PromptEnvelope(prompt, system, canonical_hash(view), canonical_hash(normalized),
        canonical_hash(json.loads(schema_json)), len(schema_json.encode("utf-8")), len(system),
        len(prompt) + len(system), len((prompt + system).encode("utf-8")))


def _expand_text(text: str, catalog: dict[str, dict[str, Any]]) -> str:
    refs = re.findall(r"\[([A-Za-z0-9_.:-]+)\]", text)
    unknown = set(refs) - set(catalog)
    if unknown:
        raise CitationPollutionError(f"unknown compact evidence IDs in prose: {sorted(unknown)}")
    for eid in dict.fromkeys(refs):
        text = text.replace(f"[{eid}]", f"[{catalog[eid]['source_id']}]")
    return text


def _expand_claim(wire: ClaimWire, context, version: int) -> GroundedClaim:
    catalog = evidence_catalog(context.packet)
    if set(wire.e) - set(catalog):
        raise CitationPollutionError("claim uses an unknown compact evidence ID")
    if set(wire.f) - context.finance.value_ids:
        raise ValueError("claim uses an unknown financial value ID")
    anchors = [{key: catalog[eid][key] for key in (
        "source_id", "chunk_id", "line_start", "line_end", "snapshot_sha256", "quote")}
        for eid in wire.e]
    source_ids = list(dict.fromkeys(anchor["source_id"] for anchor in anchors))
    expanded_claim_text = _expand_text(wire.t, catalog)
    return GroundedClaim(claim_id=wire.i, parent_claim_id=wire.pi, claim_text=expanded_claim_text,
        claim_type=wire.k, claim_domain=wire.d, evidence_status=wire.s,
        source_ids=source_ids, source_support=wire.ss, source_quality=wire.q,
        source_recency=wire.r, support_assessed_by="model_proposed", critic_status="not_reviewed",
        decision_critical=wire.dc, high_impact=wire.hi, conflict=wire.cf, pruned=False,
        major_issue=False, confidence=wire.c, confidence_reason=wire.cr,
        content_anchor=expanded_claim_text, source_anchors=anchors, financial_value_ids=wire.f,
        premise=wire.p, artifact_version=version)


def _expand_research_note(note: ResearchNoteWire, context, version: int) -> GroundedFinding:
    if any(claim.t not in note.text for claim in note.claims):
        raise ValueError("Research claim text must be an exact sentence/span in its body")
    return GroundedFinding(topic=note.topic, finding=_expand_text(note.text, evidence_catalog(context.packet)),
        rationale=note.why, confidence=note.c, confidence_reason=note.cr,
        claims=[_expand_claim(claim, context, version) for claim in note.claims])


def _expand_strategy_note(note: StrategyNoteWire, context, version: int) -> GroundedInsight:
    if any(claim.t not in note.text for claim in note.claims):
        raise ValueError("Strategy claim text must be an exact sentence/span in its body")
    return GroundedInsight(topic=note.topic, recommendation=_expand_text(note.text, evidence_catalog(context.packet)),
        rationale=note.why, confidence=note.c, confidence_reason=note.cr,
        claims=[_expand_claim(claim, context, version) for claim in note.claims])


def _expand_finance_note(note: FinanceNoteWire, context, version: int) -> GroundedFinanceAssumption:
    if set(note.f) - context.finance.value_ids:
        raise ValueError("Finance note uses an unknown financial value ID")
    if any(claim.t not in note.text for claim in note.claims):
        raise ValueError("Finance claim text must be an exact sentence/span in its body")
    return GroundedFinanceAssumption(topic=note.topic, assumption=_expand_text(note.text, evidence_catalog(context.packet)),
        rationale=note.why, value_ids=note.f, needs_validation=[], confidence=note.c,
        confidence_reason=note.cr, claims=[_expand_claim(claim, context, version) for claim in note.claims])


def expand_role_wire(context, role: str, wire: BaseModel | dict[str, Any], *, version: int,
                     config_version: str | None = None):
    schema = role_wire_schema(role, config_version)
    wire = schema.model_validate(wire)
    if isinstance(wire, ResearchWire):
        return ContractResearchAnalysis(analysis_summary=wire.summary,
            market_trends=[_expand_research_note(item, context, version) for item in wire.market],
            customer_notes=[_expand_research_note(item, context, version) for item in wire.customer],
            competitor_assumptions=[_expand_research_note(item, context, version) for item in wire.competition],
            unsupported_claims=[_expand_claim(item, context, version) for item in wire.gaps],
            needs_human_review=wire.review)
    if isinstance(wire, StrategyWire):
        return ContractStrategyAnalysis(analysis_summary=wire.summary,
            value_proposition=[_expand_strategy_note(item, context, version) for item in wire.value],
            business_model_logic=[_expand_strategy_note(item, context, version) for item in wire.model],
            gtm_strategy=[_expand_strategy_note(item, context, version) for item in wire.gtm],
            moat_hypotheses=[_expand_strategy_note(item, context, version) for item in wire.moat],
            unsupported_market_data=[_expand_claim(item, context, version) for item in wire.gaps],
            needs_human_review=wire.review)
    if isinstance(wire, FinanceWire):
        return ContractFinanceAssumptions(analysis_summary=wire.summary,
            revenue_assumptions=[_expand_finance_note(item, context, version) for item in wire.revenue],
            cost_assumptions=[_expand_finance_note(item, context, version) for item in wire.costs],
            unit_economics_assumptions=[_expand_finance_note(item, context, version) for item in wire.economics],
            break_even_discussion=wire.break_even, assumption_notice=wire.notice,
            unsupported_financial_claims=[_expand_claim(item, context, version) for item in wire.gaps],
            needs_human_review=wire.review, financial_values=context.finance.expected_values())
    if isinstance(wire, ProposalWire):
        catalog = evidence_catalog(context.packet)
        data: dict[str, Any] = {"title": wire.title}
        titles = {field: title for title, field in SECTION_FIELD_BY_TITLE.items()}
        for section in wire.sections:
            if any(claim.t not in section.text for claim in section.claims):
                raise ValueError("proposal claim text must be an exact sentence/span in its section")
            claims = [_expand_claim(item, context, version) for item in section.claims]
            source_ids = list(dict.fromkeys(source for claim in claims for source in claim.source_ids))
            values = dict(title=titles[section.key], content=_expand_text(section.text, catalog),
                key_claims=claims, source_ids=source_ids, confidence=section.c,
                confidence_reason=section.cr)
            data[section.key] = (ContractFinancialSection(**values,
                financial_values=context.finance.expected_values()) if section.key == "financial_assumptions"
                else ContractSection(**values))
        return ContractProposal.model_validate(data)
    raise TypeError("unknown compact role wire")


def normalize_claim_id_collisions(context, wire: BaseModel, upstream=(), *, version=1,
                                 config_version: str | None = None):
    """Split colliding transport IDs without guessing semantic or evidence relations.

    Only a model-declared, unambiguous existing upstream identity may become a
    new split claim's parent. The unchanged strict canonical chain must still
    check all of that parent's evidence and unresolved-state obligations.
    """
    result = wire.model_copy(deep=True)
    if config_version not in (GEMINI_8192_ID_COLLISION_CONFIG_VERSION, GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION):
        return result, []
    dual_declared_lineage = config_version == GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION
    occurrences = [(path, item) for path, item in walk_models(result) if isinstance(item, ClaimWire)]
    groups = {}
    for path, item in occurrences:
        canonical = _expand_claim(item, context, version)
        identity = canonical_hash(canonical.model_dump(exclude={
            "content_anchor", "confidence", "confidence_reason"}))
        groups.setdefault(item.i, {}).setdefault(identity, []).append((path, item))
    collisions = {cid: identities for cid, identities in groups.items() if len(identities) > 1}
    if not collisions:
        return result, []
    source_claims = [(artifact, claim) for artifact in upstream
        for claim in claims_in(context.verify_artifact(artifact))]
    graph = [claim for _, claim in source_claims]
    known_ids = {claim.claim_id for claim in graph}
    reserved_ids = known_ids | {item.i for _, item in occurrences} | {
        item.pi for _, item in occurrences if item.pi is not None}
    changes = []
    for declared_id, identities in collisions.items():
        sources = [(artifact, claim) for artifact, claim in source_claims if claim.claim_id == declared_id]
        if not sources:
            raise ValueError("claim ID collision has no unambiguous declared upstream identity")
        # Code-owned review/version state may differ, but the identity and selected
        # evidence itself must not be inferred from contradictory upstream objects.
        upstream_identity = {canonical_hash(claim.model_dump(exclude={
            "content_anchor", "confidence", "confidence_reason", "artifact_version",
            "critic_status", "pruned", "major_issue"} | ({"parent_claim_id"}
                if dual_declared_lineage else set()))) for _, claim in sources}
        if len(upstream_identity) != 1:
            raise ValueError("claim ID collision has inconsistent declared upstream identity")
        lineage_ancestor_ids(declared_id, graph,
            dual_declared_lineage=dual_declared_lineage)  # Reject cycles/conflicting nonempty edges.
        for identity, members in list(identities.items())[1:]:
            old_parent = members[0][1].pi
            if old_parent is not None and (old_parent not in known_ids or
                    declared_id not in lineage_ancestor_ids(old_parent, graph,
                        dual_declared_lineage=dual_declared_lineage)):
                raise ValueError("claim ID split would lose declared upstream identity obligations")
            parent = old_parent if old_parent is not None else declared_id
            ordinal = 2
            while True:
                suffix = f"__{ordinal:02d}"
                new_id = declared_id[:80 - len(suffix)] + suffix
                if new_id not in reserved_ids:
                    break
                ordinal += 1
            reserved_ids.add(new_id)
            unchanged = []
            for path, item in members:
                unchanged.append({"path": path, "unchanged_fields_sha256": canonical_hash(
                    item.model_dump(mode="json", exclude={"i", "pi"}))})
                item.i, item.pi = new_id, parent
            changes.append({"op": "split_colliding_declared_upstream_claim_id",
                "version": CLAIM_ID_COLLISION_ADAPTER_VERSION,
                "from_claim_id": declared_id, "to_claim_id": new_id,
                "from_parent_claim_id": old_parent, "to_parent_claim_id": parent,
                "original_canonical_identity_sha256": identity,
                "occurrences": unchanged, "words_changed": False,
                "claims_deleted": 0, "evidence_ids_added": [], "evidence_ids_deleted": [],
                "financial_value_ids_changed": False, "semantic_relation_inferred": False,
                "parent_basis": "existing_explicit_parent" if old_parent is not None else
                    "model_declared_upstream_claim_id",
                "explicit_ancestor_chain": lineage_ancestor_ids(parent, graph,
                    dual_declared_lineage=dual_declared_lineage),
                "source_artifacts": [{"role": artifact.role, "artifact_version": artifact.version,
                    "artifact_sha256": artifact.sha256, "claim_id": claim.claim_id}
                    for artifact, claim in sources]})
    if changes:
        changes[0].update(wire_before_sha256=canonical_hash(wire.model_dump(mode="json")),
            wire_after_sha256=canonical_hash(result.model_dump(mode="json")))
    return result, changes


def normalize_exact_text_parent_lineage(candidate, upstream, *, dual_declared_lineage=False) -> list[dict[str, Any]]:
    """Identify a single existing parent for verbatim repeated model-authored text."""
    source_claims = [(artifact, claim) for artifact in upstream for claim in claims_in(artifact.payload())]
    upstream_ids = {claim.claim_id for _, claim in source_claims}
    changes = []
    for claim in claims_in(candidate):
        if claim.parent_claim_id is not None:
            continue
        declared_known = claim.claim_id in upstream_ids
        if declared_known and (not dual_declared_lineage or any(
                old.claim_id == claim.claim_id and old.claim_text == claim.claim_text for _, old in source_claims)):
            continue
        matches = [(artifact, old) for artifact, old in source_claims
            if old.claim_text == claim.claim_text]
        ids = {old.claim_id for _, old in matches}
        graph = [old for _, old in source_claims]
        descendants = [cid for cid in ids if ids <= set(lineage_ancestor_ids(cid, graph,
            dual_declared_lineage=dual_declared_lineage))]
        if len(descendants) != 1:
            continue
        parent = descendants[0]
        if dual_declared_lineage and declared_known and claim.claim_id in lineage_ancestor_ids(parent, graph,
                dual_declared_lineage=True):
            # Recording this edge would turn the existing explicit path into a cycle.
            raise ValueError("exact-text parent would create a declared claim lineage cycle")
        claim.parent_claim_id = parent
        changes.append({"op": "set_unique_exact_text_parent_claim_id",
            "version": EXACT_TEXT_PARENT_LINEAGE_VERSION, "claim_id": claim.claim_id,
            "from_parent_claim_id": None, "to_parent_claim_id": parent,
            "matched_claim_ids": sorted(ids), "explicit_ancestor_chain": lineage_ancestor_ids(parent, graph,
                dual_declared_lineage=dual_declared_lineage),
            "claim_text_sha256": canonical_hash(claim.claim_text), "words_changed": False,
            "evidence_ids_added": [], "evidence_ids_deleted": [],
            "source_artifacts": [{"role": artifact.role, "artifact_version": artifact.version,
                "artifact_sha256": artifact.sha256, "claim_id": old.claim_id}
                for artifact, old in matches]})
        if dual_declared_lineage and declared_known:
            changes[-1].update(dual_declared_lineage=DUAL_DECLARED_LINEAGE_VERSION,
                preserved_declared_claim_id=claim.claim_id, semantic_identity_inferred=False,
                source_quality_or_premise_changed=False, both_declared_lineage_obligations_retained=True)
    return changes


def preserve_upstream_dispositions(candidate, upstream, *, lineage_identity_continuity=False,
                                   dual_declared_lineage=False) -> list[dict[str, Any]]:
    """Reapply code-owned unresolved state omitted from compact role DTOs."""
    prior: dict[str, GroundedClaim] = {}
    prior_claims = []
    for artifact in upstream:
        for claim in claims_in(artifact.payload()):
            prior[claim.claim_id] = claim
            prior_claims.append(claim)
    changes: list[dict[str, Any]] = []
    for claim in claims_in(candidate):
        old = prior.get(claim.claim_id) or prior.get(claim.parent_claim_id or "")
        related = ([old] if old is not None else [])
        if dual_declared_lineage:
            ids = set()
            for start in (claim.claim_id, claim.parent_claim_id):
                if start is not None:
                    ids.update(lineage_ancestor_ids(start, prior_claims, dual_declared_lineage=True))
            related.extend(old for old in prior_claims if old.claim_id in ids)
        if lineage_identity_continuity:
            related.extend(same_text_lineage_identity_members(claim, prior_claims,
                dual_declared_lineage=dual_declared_lineage))
        if not related:
            continue
        before = {
            "conflict": claim.conflict,
            "pruned": claim.pruned,
            "major_issue": claim.major_issue,
            "critic_status": claim.critic_status,
            "confidence": claim.confidence,
            "confidence_reason": claim.confidence_reason,
        }
        for old in related:
            claim.conflict = claim.conflict or old.conflict
            claim.pruned = claim.pruned or old.pruned
            claim.major_issue = claim.major_issue or old.major_issue
            if old.critic_status in ("unresolved", "unverified_after_revision"):
                claim.critic_status = old.critic_status
            if old.confidence == "low" and claim.confidence != "low":
                claim.confidence = "low"
                claim.confidence_reason = old.confidence_reason
        after = {
            "conflict": claim.conflict,
            "pruned": claim.pruned,
            "major_issue": claim.major_issue,
            "critic_status": claim.critic_status,
            "confidence": claim.confidence,
            "confidence_reason": claim.confidence_reason,
        }
        if before != after:
            change = {"claim_id": claim.claim_id, "before": before, "after": after}
            if lineage_identity_continuity:
                change.update(lineage_identity_continuity=LINEAGE_IDENTITY_CONTINUITY_VERSION,
                    existing_identity_claim_ids=list(dict.fromkeys(old.claim_id for old in related)),
                    evidence_ids_added=[])
            if dual_declared_lineage:
                change.update(dual_declared_lineage=DUAL_DECLARED_LINEAGE_VERSION,
                    declared_claim_id=claim.claim_id, declared_parent_claim_id=claim.parent_claim_id,
                    existing_identity_claim_ids=list(dict.fromkeys(old.claim_id for old in related)),
                    evidence_ids_added=[], semantic_identity_inferred=False)
            changes.append(change)
    return changes


def _claim_list_to_wire(items, packet, *, compact_citations=False):
    return [_claim_to_wire(item, packet, compact_citations=compact_citations) for item in items]


def compact_role_output(context, role: str, candidate, *,
                        config_version: str | None = None) -> BaseModel:
    """Collapse a valid canonical object; expanding it restores the same canonical payload."""
    compact_citations = config_version in FINANCE_CAPACITY_CONFIG_VERSIONS
    claim_list = lambda items: _claim_list_to_wire(items, context.packet, compact_citations=compact_citations)
    body = lambda text, items: (_compact_parent_citations(text, items, context.packet)
        if compact_citations else text)
    if role == "research":
        note = lambda item: dict(topic=item.topic, text=body(item.finding, item.claims), why=item.rationale,
            c=item.confidence, cr=item.confidence_reason, claims=claim_list(item.claims))
        return ResearchWire(summary=candidate.analysis_summary,
            market=[note(item) for item in candidate.market_trends],
            customer=[note(item) for item in candidate.customer_notes],
            competition=[note(item) for item in candidate.competitor_assumptions],
            gaps=claim_list(candidate.unsupported_claims), review=candidate.needs_human_review)
    if role == "strategy":
        note = lambda item: dict(topic=item.topic, text=body(item.recommendation, item.claims), why=item.rationale,
            c=item.confidence, cr=item.confidence_reason, claims=claim_list(item.claims))
        return StrategyWire(summary=candidate.analysis_summary,
            value=[note(item) for item in candidate.value_proposition],
            model=[note(item) for item in candidate.business_model_logic],
            gtm=[note(item) for item in candidate.gtm_strategy], moat=[note(item) for item in candidate.moat_hypotheses],
            gaps=claim_list(candidate.unsupported_market_data), review=candidate.needs_human_review)
    if role == "finance":
        note = lambda item: dict(topic=item.topic, text=body(item.assumption, item.claims), why=item.rationale,
            f=item.value_ids, c=item.confidence, cr=item.confidence_reason,
            claims=claim_list(item.claims))
        return role_wire_schema(role, config_version)(summary=candidate.analysis_summary,
            revenue=[note(item) for item in candidate.revenue_assumptions],
            costs=[note(item) for item in candidate.cost_assumptions],
            economics=[note(item) for item in candidate.unit_economics_assumptions],
            break_even=candidate.break_even_discussion, notice=candidate.assumption_notice,
            gaps=claim_list(candidate.unsupported_financial_claims), review=candidate.needs_human_review)
    if role in ("single", "writer"):
        catalog, by_chunk = evidence_catalog(context.packet), _eid_by_chunk(context.packet)
        sections = []
        for key in SECTION_KEYS:
            section = getattr(candidate, key)
            replacements = {}
            for claim in section.key_claims:
                for anchor in claim.source_anchors:
                    replacements.setdefault(anchor.source_id, by_chunk[anchor.chunk_id])
            text = section.content
            if compact_citations:
                text = body(text, section.key_claims)
            else:
                for source_id, eid in replacements.items():
                    text = text.replace(f"[{source_id}]", f"[{eid}]")
            sections.append(dict(key=key, text=text,
                claims=claim_list(section.key_claims),
                c=section.confidence, cr=section.confidence_reason))
        return ProposalWire(title=candidate.title, sections=sections)
    raise ValueError("unknown compact role")


def _patch_field_paths(artifact) -> dict[str, str]:
    """Only existing prose exposed by the role wire is a field-patch target."""
    data = artifact.payload().model_dump(mode="json")
    paths = {}
    if artifact.role in ("single", "writer"):
        paths["title"] = "title"
        for index, key in enumerate(SECTION_KEYS):
            paths[f"sections.{index}.text"] = f"{key}.content"
    else:
        paths["summary"] = "analysis_summary"
        groups, body = {
            "research": ({"market": "market_trends", "customer": "customer_notes",
                "competition": "competitor_assumptions"}, "finding"),
            "strategy": ({"value": "value_proposition", "model": "business_model_logic",
                "gtm": "gtm_strategy", "moat": "moat_hypotheses"}, "recommendation"),
            "finance": ({"revenue": "revenue_assumptions", "costs": "cost_assumptions",
                "economics": "unit_economics_assumptions"}, "assumption"),
        }[artifact.role]
        for short, canonical in groups.items():
            for index in range(len(data[canonical])):
                for field, target in (("topic", "topic"), ("text", body), ("why", "rationale")):
                    paths[f"{short}.{index}.{field}"] = f"{canonical}.{index}.{target}"
        for index in range(len(data["needs_human_review"])):
            paths[f"review.{index}"] = f"needs_human_review.{index}"
        if artifact.role == "finance":
            paths.update(break_even="break_even_discussion", notice="assumption_notice")
    return paths


def _canonical_patch_field(artifact, path: str) -> str:
    paths = _patch_field_paths(artifact)
    canonical = paths.get(path, path)
    if canonical not in paths.values() or not isinstance(
            _get_path(artifact.payload().model_dump(mode="json"), canonical), str):
        raise ValueError(f"unknown or non-prose Critic field target: {path}")
    return canonical


def expand_critic_wire(context, artifact, role: str, artifact_id: str,
                       wire: CriticWire | dict[str, Any], *,
                       critic_patch_adapter=False) -> ComponentCritiqueReport:
    wire = CriticWire.model_validate(wire)
    metrics = METRICS[role]
    if len(wire.scores) != len(metrics) or any(score < 0 or score > 4 for score in wire.scores):
        raise ValueError("compact score vector does not match fixed metrics")
    catalog = evidence_catalog(context.packet)
    issues = []
    for item in wire.issues:
        if item.criterion not in metrics:
            raise ValueError("compact issue uses an unknown criterion")
        if set(item.e) - set(catalog):
            raise CitationPollutionError("compact Critic uses an unknown evidence ID")
        issues.append(ReviewIssue(issue_id=item.i, severity=item.sev, criterion=item.criterion,
            description=item.note, suggested_fix=item.fix, affected_claim_ids=item.claims,
            source_ids=list(dict.fromkeys(catalog[eid]["source_id"] for eid in item.e)),
            target_fields=([_canonical_patch_field(artifact, path) for path in item.fields]
                if critic_patch_adapter else item.fields), evidence_ids=item.e, fix_code=item.fix,
            artifact_version=artifact.version))
    expected = "FAIL" if any(issue.severity in ("high", "critical") for issue in issues) else "PASS"
    if wire.status != expected:
        raise ValueError("Critic PASS/FAIL conflicts with code-owned severity gate")
    report = ComponentCritiqueReport(role=role, artifact_id=artifact_id,
        artifact_version=artifact.version,
        metrics=[ReviewMetric(criterion=criterion, score=score,
            rationale="compact score vector; targeted details are stored in issues",
            evidence_anchor=artifact_id) for criterion, score in zip(metrics, wire.scores, strict=True)],
        issues=issues, provider_status=wire.status)
    context.validate_review_feedback(artifact, report)
    return report


def _get_path(value: Any, path: str):
    current = value
    for token in path.split("."):
        if isinstance(current, list):
            if not token.isdigit() or int(token) >= len(current):
                raise ValueError(f"invalid patch path: {path}")
            current = current[int(token)]
        elif isinstance(current, dict) and token in current:
            current = current[token]
        else:
            raise ValueError(f"invalid patch path: {path}")
    return deepcopy(current)


def _set_string_path(value: Any, path: str, replacement: str):
    tokens = path.split(".")
    parent = value
    for token in tokens[:-1]:
        parent = parent[int(token)] if isinstance(parent, list) and token.isdigit() else parent[token]
    key = tokens[-1]
    current = parent[int(key)] if isinstance(parent, list) and key.isdigit() else parent[key]
    if not isinstance(current, str):
        raise ValueError("field patch may replace only an existing string")
    if isinstance(parent, list):
        parent[int(key)] = replacement
    else:
        parent[key] = replacement


def _expand_patch_text(text, context):
    catalog = evidence_catalog(context.packet)
    def replace(match):
        ref = match.group(1)
        if ref in catalog:
            return f"[{catalog[ref]['source_id']}]"
        if ref in context.packet.allowlist_source_ids:
            return match.group(0)
        raise CitationPollutionError("patch prose uses an unknown evidence ID")
    return re.sub(r"\[([A-Za-z0-9_.:-]+)\]", replace, text)


def _patch_parent_nodes(data, path=""):
    if isinstance(data, dict):
        if "key_claims" in data or ("claims" in data and any(
                key in data for key in ("finding", "recommendation", "assumption"))):
            yield path, data, data.get("key_claims", data.get("claims", []))
        for key, child in data.items():
            yield from _patch_parent_nodes(child, f"{path}.{key}" if path else key)
    elif isinstance(data, list):
        for index, child in enumerate(data):
            yield from _patch_parent_nodes(child, f"{path}.{index}")


def _synchronize_patch_prose(data, text_updates):
    audit = []
    for path, parent, claims in _patch_parent_nodes(data):
        for claim in claims:
            cid = claim["claim_id"]
            if cid not in text_updates:
                continue
            old, new = claim["content_anchor"], text_updates[cid]
            if old == new:
                continue
            matches = [(key, parent[key].count(old)) for key in (
                "content", "finding", "recommendation", "assumption", "rationale")
                if isinstance(parent.get(key), str) and old in parent[key]]
            if sum(count for _, count in matches) != 1:
                raise ValueError("claim text patch requires one unambiguous parent occurrence")
            field = matches[0][0]
            before = parent[field]
            parent[field] = before.replace(old, new, 1)
            audit.append({"op": "synchronize_claim_parent_text", "path": f"{path}.{field}",
                "claim_id": cid, "from": old, "to": new,
                "before_sha256": canonical_hash(before), "after_sha256": canonical_hash(parent[field]),
                "precondition": "one_exact_existing_anchor_occurrence",
                "outside_anchor_unchanged": True, "evidence_ids_added": [], "evidence_ids_deleted": []})
    return audit


def apply_patch_wire(context, previous, review, patch: PatchWire | dict[str, Any], *,
                     critic_patch_adapter=False):
    patch = PatchWire.model_validate(patch)
    if critic_patch_adapter and any("t" in item.model_fields_set and item.t is None
            for item in patch.claims):
        raise ValueError("explicitly null claim patch text is invalid; omit unchanged text")
    issue_ids, claim_ids, paths = _issue_targets(review)
    if not issue_ids:
        raise ValueError("revision was not triggered by a high/critical issue")
    seen_issues = [item.issue for item in (*patch.claims, *patch.fields)]
    if set(seen_issues) - issue_ids or len(seen_issues) != len(set(seen_issues)):
        raise ValueError("patch issue is unknown or applied more than once")
    data = previous.payload().model_dump(mode="json")
    before = canonical_hash(data)
    adapter_audit = []
    text_updates = {item.i: _expand_patch_text(item.t, context) for item in patch.claims
        if critic_patch_adapter and "t" in item.model_fields_set and item.t is not None}
    field_updates = []
    by_issue = {issue.issue_id: issue for issue in review.issues}
    for item in patch.fields:
        path = _canonical_patch_field(previous, item.path) if critic_patch_adapter else item.path
        if path not in paths or (critic_patch_adapter and path not in by_issue[item.issue].target_fields):
            raise ValueError("field patch exceeds Critic-authorized targets")
        value = _expand_patch_text(item.value, context) if critic_patch_adapter else item.value
        if critic_patch_adapter:
            old = _get_path(data, path)
            for parent_path, parent, claims in _patch_parent_nodes(data):
                if path not in {f"{parent_path}.{key}" for key in (
                        "content", "finding", "recommendation", "assumption", "rationale")}:
                    continue
                if len(claims) == 1 and claims[0]["content_anchor"] == old and old != value:
                    cid = claims[0]["claim_id"]
                    if cid in text_updates and text_updates[cid] != value:
                        raise ValueError("field and claim patches give conflicting text")
                    text_updates[cid] = value
        field_updates.append((path, value))
    if critic_patch_adapter:
        adapter_audit = _synchronize_patch_prose(data, text_updates)
    for path, value in field_updates:
        _set_string_path(data, path, value)
    claim_updates = {item.i: item for item in patch.claims}
    if set(claim_updates) - claim_ids:
        raise ValueError("claim patch exceeds Critic-authorized targets")
    if critic_patch_adapter and any(item.i not in by_issue[item.issue].affected_claim_ids
            for item in patch.claims):
        raise ValueError("claim patch exceeds its own Critic issue targets")
    found = set()
    catalog = evidence_catalog(context.packet)
    for _, obj in walk_models(previous.payload()):
        if not isinstance(obj, GroundedClaim) or obj.claim_id not in claim_updates:
            continue
        found.add(obj.claim_id)
    if found != set(claim_updates):
        raise ValueError("patch references a missing claim")

    def update(node):
        if isinstance(node, dict):
            cid = node.get("claim_id")
            if cid in text_updates:
                node["claim_text"] = text_updates[cid]
                node["content_anchor"] = text_updates[cid]
                node["critic_status"] = "unverified_after_revision"
            if cid in claim_updates:
                item = claim_updates[cid]
                changed = item.model_fields_set
                if "t" in changed and not critic_patch_adapter:
                    node["claim_text"] = item.t
                    node["content_anchor"] = item.t
                if "s" in changed: node["evidence_status"] = item.s
                if "f" in changed:
                    if set(item.f or ()) - context.finance.value_ids: raise ValueError("unknown patched financial ID")
                    node["financial_value_ids"] = item.f
                if "ss" in changed: node["source_support"] = item.ss
                if "p" in changed: node["premise"] = item.p
                if "c" in changed: node["confidence"] = item.c
                if "cr" in changed: node["confidence_reason"] = item.cr
                if "e" in changed:
                    if set(item.e or ()) - set(catalog): raise CitationPollutionError("unknown patched evidence ID")
                    anchors = [{key: catalog[eid][key] for key in (
                        "source_id", "chunk_id", "line_start", "line_end", "snapshot_sha256", "quote")}
                        for eid in (item.e or [])]
                    node["source_anchors"] = anchors
                    node["source_ids"] = list(dict.fromkeys(anchor["source_id"] for anchor in anchors))
                node["critic_status"] = "unverified_after_revision"
            if "claim_id" in node:
                node["artifact_version"] = 2
            for child in node.values(): update(child)
        elif isinstance(node, list):
            for child in node: update(child)
    update(data)
    candidate = type(previous.payload()).model_validate(data)
    diff = {"kind": "semantic_patch", "before_sha256": before,
        "patch": patch.model_dump(mode="json", exclude_unset=True),
        "after_sha256": canonical_hash(candidate.model_dump(mode="json")),
        "authorized_issue_ids": sorted(issue_ids)}
    if critic_patch_adapter:
        diff.update(critic_patch_adapter=CRITIC_PATCH_ADAPTER_VERSION,
            deterministic_adapter_changes=adapter_audit)
    return candidate, diff


ENUM_ALIASES = {
    "k": {"fact": "factual", "recommend": "recommendation", "project": "projection"},
    "s": {"supported": "sourced_fact", "needs-validation": "needs_validation"},
    "ss": {"no_support": "none"},
    "c": {"med": "medium"},
    "cr": {"direct": "directly_supported", "partial": "partial_support"},
    "status": {"pass": "PASS", "fail": "FAIL"},
    "sev": {"crit": "critical", "med": "medium"},
}


def _model_annotation(annotation):
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    origin = get_origin(annotation)
    if origin in (list, tuple):
        args = get_args(annotation)
        return ("list", args[0]) if args else None
    if origin in (UnionType, getattr(__import__("typing"), "Union", object)):
        for arg in get_args(annotation):
            found = _model_annotation(arg)
            if found:
                return found
    return None


def _filter_and_normalize(value, annotation, path="$"):
    changes = []
    model = _model_annotation(annotation)
    if isinstance(model, tuple) and model[0] == "list" and isinstance(value, list):
        output = []
        for index, item in enumerate(value):
            child, child_changes = _filter_and_normalize(item, model[1], f"{path}.{index}")
            output.append(child); changes.extend(child_changes)
        return output, changes
    if isinstance(model, type) and issubclass(model, BaseModel) and isinstance(value, dict):
        output = {}
        for key, item in value.items():
            if key not in model.model_fields:
                changes.append({"op": "remove_extra", "path": f"{path}.{key}"})
                continue
            field = model.model_fields[key]
            normalized = ENUM_ALIASES.get(key, {}).get(item, item) if isinstance(item, str) else item
            if normalized != item:
                changes.append({"op": "normalize_enum", "path": f"{path}.{key}", "from": item, "to": normalized})
            child, child_changes = _filter_and_normalize(normalized, field.annotation, f"{path}.{key}")
            output[key] = child; changes.extend(child_changes)
        return output, changes
    return value, changes


def _typed_model_dicts(value, annotation, path="$"):
    """Yield mutable dictionaries with their declared model type and stable path."""
    model = _model_annotation(annotation)
    if isinstance(model, tuple) and model[0] == "list" and isinstance(value, list):
        for index, item in enumerate(value):
            yield from _typed_model_dicts(item, model[1], f"{path}.{index}")
    elif isinstance(model, type) and issubclass(model, BaseModel) and isinstance(value, dict):
        yield model, value, path
        for key, item in value.items():
            if key in model.model_fields:
                yield from _typed_model_dicts(item, model.model_fields[key].annotation, f"{path}.{key}")


def _zero_pad_claim_id(value: str) -> str:
    match = re.fullmatch(r"(.*?)([0-9]+)", value)
    if match:
        prefix, digits = match.groups()
        return prefix + digits.zfill(max(len(digits), 3 - len(prefix)))
    return value + "0" * max(0, 3 - len(value))


def _add_collision_zero(value: str) -> str:
    match = re.fullmatch(r"(.*?)([0-9]+)", value)
    return (match.group(1) + "0" + match.group(2)) if match else value + "0"


def _normalize_compact_citation_lists(text: str, allowed: set[str]):
    changes = []

    def replace(match):
        values = [item.strip() for item in match.group(1).split(",")]
        if (len(values) < 2 or len(values) != len(set(values)) or
                any(not re.fullmatch(r"E[0-9]{2,}", item) or item not in allowed
                    for item in values)):
            return match.group(0)
        normalized = " ".join(f"[{item}]" for item in values)
        changes.append({"from": match.group(0), "to": normalized,
            "evidence_ids": values})
        return normalized

    result = re.sub(r"\[((?:E[0-9]{2,})(?:\s*,\s*E[0-9]{2,})+)\]", replace, text)
    return result, changes


def _mirror_selected_inline_citations(text: str, evidence_ids: list[str],
                                      catalog: dict[str, dict[str, Any]]):
    """Append only already-selected, frozen E## tokens missing from equal text/t."""
    if len(evidence_ids) != len(set(evidence_ids)):
        return text, None
    if any(not re.fullmatch(r"E[0-9]{2,}", eid) or eid not in catalog
            for eid in evidence_ids):
        return text, None
    missing = [eid for eid in evidence_ids if f"[{eid}]" not in text]
    if not missing:
        return text, None
    mirrored = text + " " + " ".join(f"[{eid}]" for eid in missing)
    return mirrored, {
        "from": text,
        "to": mirrored,
        "evidence_ids_selected": list(evidence_ids),
        "evidence_ids_mirrored": missing,
        "mapped_source_ids": [catalog[eid]["source_id"] for eid in missing],
    }


def _remove_selected_financial_markers(text: str, financial_ids: list[str],
                                       allowed_financial_ids: set[str]):
    """Remove only bracketed IDs already retained in claim.f and frozen inputs."""
    if (len(financial_ids) != len(set(financial_ids)) or
            any(not isinstance(fid, str) or fid not in allowed_financial_ids
                for fid in financial_ids)):
        return text, None
    output = text
    removed = []
    removed_tokens = []
    for fid in financial_ids:
        for token in (f"[{fid}]", f"[F-{fid}]"):
            count = output.count(token)
            if not count:
                continue
            output = output.replace(" " + token, "")
            output = output.replace(token + " ", "")
            output = output.replace(token, "")
            removed.extend([fid] * count)
            removed_tokens.extend([token] * count)
    if not removed:
        return text, None
    return output, {"from": text, "to": output,
        "financial_value_ids_selected": list(financial_ids),
        "financial_markers_removed": removed,
        "financial_marker_tokens_removed": removed_tokens}


def _repair_claim_wires(value, schema: type[BaseModel], *, terminal_punctuation=False,
                        source_disposition=False, citation_list_format=False,
                        inline_citation_mirror=False,
                        financial_marker=False,
                        source_quality_scale_5=False,
                        invalid_source_recency=False,
                        existing_claim_body_assembly=False,
                        repair_evidence_catalog: dict[str, dict[str, Any]] | None = None,
                        repair_financial_ids: set[str] | None = None,
                        ) -> list[dict[str, Any]]:
    """Apply only user-approved, evidence-conservative claim repairs."""
    typed_nodes = list(_typed_model_dicts(value, schema))
    nodes = [(path, item) for model, item, path in typed_nodes
        if model is ClaimWire]
    parent_texts: dict[str, tuple[str, str, dict[str, Any]]] = {}
    if (terminal_punctuation or citation_list_format or inline_citation_mirror or
            financial_marker):
        for model, item, path in typed_nodes:
            if model not in (ResearchNoteWire, StrategyNoteWire, FinanceNoteWire, FinanceNote8Wire, SectionWire):
                continue
            parent_text = item.get("text")
            claims = item.get("claims")
            if not isinstance(parent_text, str) or not isinstance(claims, list):
                continue
            for index, claim in enumerate(claims):
                if isinstance(claim, dict):
                    parent_texts[f"{path}.claims.{index}"] = (parent_text, path, item)
    reserved = {item.get("i") for _, item in nodes
        if isinstance(item.get("i"), str) and len(item["i"]) >= 3}
    used = set(reserved)
    short_id_map: dict[str, list[str]] = {}
    changes: list[dict[str, Any]] = []
    for path, item in nodes:
        recency = item.get("r")
        if (invalid_source_recency and type(recency) in (int, float)
                and math.isfinite(recency) and not 0 <= recency <= 1):
            item["r"] = None
            changes.append({"op": "discard_invalid_source_recency_score", "path": f"{path}.r",
                "from": recency, "to": None, "precondition": "finite_numeric_outside_unit_interval",
                "score_inferred": False, "words_changed": False, "evidence_ids_added": [],
                "financial_value_ids_added": [], "financial_value_ids_deleted": []})
        quality = item.get("q")
        if (source_quality_scale_5 and type(quality) is int and
                2 <= quality <= 5):
            normalized_quality = quality / 5
            item["q"] = normalized_quality
            changes.append({"op": "normalize_source_quality_scale_5_to_unit",
                "path": f"{path}.q", "from": quality, "to": normalized_quality,
                "precondition": "integer_2_through_5_only", "words_changed": False,
                "evidence_ids_added": [], "evidence_ids_deleted": []})
        claim_id = item.get("i")
        if isinstance(claim_id, str) and len(claim_id) < 3:
            padded = _zero_pad_claim_id(claim_id)
            while padded in used:
                padded = _add_collision_zero(padded)
            item["i"] = padded
            used.add(padded)
            short_id_map.setdefault(claim_id, []).append(padded)
            changes.append({"op": "pad_claim_id", "path": f"{path}.i",
                "from": claim_id, "to": padded})
        if item.get("s") == "sourced_fact" and not item.get("e"):
            before = {key: item.get(key) for key in ("s", "ss", "cr")}
            item.update(s="unsupported", ss="none", cr="no_evidence")
            changes.append({"op": "downgrade_unsubstantiated_source", "path": path,
                "from": before, "to": {"s": "unsupported", "ss": "none", "cr": "no_evidence"},
                "evidence_ids_added": []})
        elif (source_disposition and item.get("s") == "sourced_fact" and
                (item.get("k") != "factual" or item.get("ss") != "direct")):
            before = {key: item.get(key) for key in ("k", "s", "ss", "e")}
            target = ("assumption" if item.get("k") in ("assumption", "projection")
                else "needs_validation")
            item["s"] = target
            changes.append({"op": "downgrade_invalid_sourced_fact_disposition", "path": path,
                "from": before, "to": {**before, "s": target},
                "evidence_ids_preserved": list(item.get("e") or []),
                "evidence_ids_added": [], "words_changed": False})
        if citation_list_format and path in parent_texts:
            parent_text, parent_path, parent_item = parent_texts[path]
            claim_text = item.get("t")
            if isinstance(claim_text, str) and claim_text == parent_text:
                normalized, format_changes = _normalize_compact_citation_lists(
                    claim_text, set(item.get("e") or []))
                if normalized != claim_text:
                    item["t"] = normalized
                    parent_item["text"] = normalized
                    for change in format_changes:
                        changes.append({"op": "split_compact_citation_bracket_list",
                            "path": f"{path}.t", "parent_path": f"{parent_path}.text",
                            **change, "evidence_ids_added": [],
                            "evidence_ids_reordered": False, "words_changed": False})
        if inline_citation_mirror and path in parent_texts:
            _, parent_path, parent_item = parent_texts[path]
            parent_text = parent_item.get("text")
            claim_text = item.get("t")
            if (isinstance(claim_text, str) and claim_text == parent_text and
                    isinstance(repair_evidence_catalog, dict)):
                mirrored, mirror_change = _mirror_selected_inline_citations(
                    claim_text, list(item.get("e") or []), repair_evidence_catalog)
                if mirror_change is not None:
                    item["t"] = mirrored
                    parent_item["text"] = mirrored
                    changes.append({"op": "mirror_selected_evidence_ids_inline",
                        "path": f"{path}.t", "parent_path": f"{parent_path}.text",
                        **mirror_change, "evidence_ids_added": [],
                        "evidence_ids_deleted": [], "evidence_ids_reordered": False,
                        "words_changed": False})
        if financial_marker and path in parent_texts:
            _, parent_path, parent_item = parent_texts[path]
            parent_text = parent_item.get("text")
            claim_text = item.get("t")
            if (isinstance(claim_text, str) and claim_text == parent_text and
                    isinstance(repair_financial_ids, set)):
                cleaned, marker_change = _remove_selected_financial_markers(
                    claim_text, list(item.get("f") or []), repair_financial_ids)
                if marker_change is not None:
                    item["t"] = cleaned
                    parent_item["text"] = cleaned
                    changes.append({"op": "remove_structured_financial_marker_from_prose",
                        "path": f"{path}.t", "parent_path": f"{parent_path}.text",
                        **marker_change, "financial_value_ids_added": [],
                        "financial_value_ids_deleted": [], "evidence_ids_added": [],
                        "evidence_ids_deleted": [], "words_changed": False})
        if terminal_punctuation and path in parent_texts:
            parent_text, parent_path, _ = parent_texts[path]
            claim_text = item.get("t")
            if (isinstance(claim_text, str) and claim_text not in parent_text and
                    len(claim_text) > 3 and unicodedata.category(claim_text[-1]).startswith("P")):
                without_terminal_punctuation = claim_text[:-1]
                if without_terminal_punctuation in parent_text:
                    item["t"] = without_terminal_punctuation
                    changes.append({"op": "delete_terminal_claim_punctuation", "path": f"{path}.t",
                        "from": claim_text, "to": without_terminal_punctuation,
                        "removed": claim_text[-1], "removed_codepoint": f"U+{ord(claim_text[-1]):04X}",
                        "parent_path": f"{parent_path}.text",
                        "parent_text_sha256": canonical_hash(parent_text),
                        "precondition": "claim_not_substring_and_without_one_terminal_punctuation_is_substring",
                        "words_changed": False})
    for path, item in nodes:
        parent = item.get("pi")
        replacements = short_id_map.get(parent, []) if isinstance(parent, str) else []
        if isinstance(parent, str) and len(parent) < 3 and len(replacements) == 1:
            item["pi"] = replacements[0]
            changes.append({"op": "pad_parent_claim_id", "path": f"{path}.pi",
                "from": parent, "to": replacements[0]})
    if existing_claim_body_assembly:
        changes.extend(_assemble_existing_claim_bodies(typed_nodes,
            repair_evidence_catalog=repair_evidence_catalog,
            repair_financial_ids=repair_financial_ids))
    return changes


def _assemble_existing_claim_bodies(typed_nodes, *, repair_evidence_catalog,
                                  repair_financial_ids):
    """Append only same-parent model-authored whole claims after all older repairs."""
    changes = []
    for model, parent, path in typed_nodes:
        if model not in (ResearchNoteWire, StrategyNoteWire, FinanceNoteWire, FinanceNote8Wire, SectionWire):
            continue
        original = parent.get("text")
        claims = parent.get("claims")
        if not isinstance(original, str) or not isinstance(claims, list):
            continue  # The unchanged DTO rejects malformed field types.
        body = original
        for index, claim in enumerate(claims):
            if not isinstance(claim, dict) or not isinstance(claim.get("t"), str):
                continue
            text = claim["t"]
            if not text or text in body:
                continue
            if not isinstance(repair_evidence_catalog, dict) or not isinstance(repair_financial_ids, set):
                raise ValueError("existing-claim body assembly requires frozen evidence and financial IDs")
            evidence, financial = claim.get("e", []), claim.get("f", [])
            if not isinstance(evidence, list) or not isinstance(financial, list):
                raise ValueError("body assembly requires structured reference lists")
            if any(not isinstance(eid, str) or eid not in repair_evidence_catalog for eid in evidence):
                raise CitationPollutionError("body assembly claim contains unknown evidence ID")
            if any(not isinstance(fid, str) or fid not in repair_financial_ids for fid in financial):
                raise ValueError("body assembly claim contains unknown financial ID")
            before = body
            body += " " + text
            changes.append({"op": "append_existing_same_parent_claim_text",
                "path": f"{path}.text", "source_claim_path": f"{path}.claims.{index}.t",
                "source_claim_id": claim.get("i"), "appended_text": text, "separator": " ",
                "original_parent_sha256": canonical_hash(original),
                "before_sha256": canonical_hash(before), "after_sha256": canonical_hash(body),
                "precondition": "same_parent_whole_claim_text_not_in_current_body",
                "original_parent_preserved_verbatim": True, "novel_content_added": False,
                "source_claim_text_changed": False, "evidence_ids_preserved": evidence.copy(),
                "financial_ids_preserved": financial.copy(), "evidence_ids_added": [],
                "evidence_ids_deleted": [], "financial_value_ids_added": [],
                "financial_value_ids_deleted": []})
        parent["text"] = body
    return changes


def _partition_finance_note_claims(value, schema):
    """Preserve complete notes and ordered claims within the existing 2-by-8 limits."""
    if schema is not Finance8Wire:
        return []
    changes = []
    for field in ("revenue", "costs", "economics"):
        notes = value.get(field)
        if not isinstance(notes, list):
            continue
        partitioned = []
        pending = []
        for source_index, note in enumerate(notes):
            if not isinstance(note, dict) or not isinstance(note.get("claims"), list) or len(note["claims"]) <= 8:
                partitioned.append(note)
                continue
            original_claims = note["claims"]
            targets = []
            for start in range(0, len(original_claims), 8):
                copy = deepcopy(note)
                copy["claims"] = deepcopy(original_claims[start:start + 8])
                target_index = len(partitioned)
                partitioned.append(copy)
                targets.append({"path": f"$.{field}.{target_index}",
                    "source_claim_indices": list(range(start, min(start + 8, len(original_claims))))})
            pending.append({"op": "partition_existing_finance_note_claims",
                "source_path": f"$.{field}.{source_index}", "source_note_sha256": canonical_hash(note),
                "source_claim_count": len(original_claims), "target_groups": targets,
                "claim_order_preserved": True, "original_body_copied_verbatim": True,
                "other_note_fields_unchanged": True, "claims_added": [], "claims_deleted": [],
                "evidence_ids_added": [], "financial_value_ids_added": [],
                "financial_value_ids_deleted": [], "capacity": {"claims_per_note": 8, "notes_per_array": 2}})
        if len(partitioned) > 2:
            raise ValueError("finance claim partition exceeds existing two-note array limit")
        value[field] = partitioned
        changes.extend(pending)
    return changes


def _append_finance_assumption_notice(value, schema):
    if schema is not Finance8Wire or not isinstance(value.get("notice"), str):
        return []
    original = value["notice"]
    if "assumption" in original.lower() and "forecast" in original.lower():
        return []
    value["notice"] = original + " " + FINANCE_ASSUMPTION_POLICY_SENTENCE
    return [{"op": "append_code_owned_finance_assumption_disclosure", "path": "$.notice",
        "code_owned_disclosure": True, "appended_text": FINANCE_ASSUMPTION_POLICY_SENTENCE,
        "separator": " ", "original_notice_sha256": canonical_hash(original),
        "before_sha256": canonical_hash(original), "after_sha256": canonical_hash(value["notice"]),
        "original_notice_preserved_verbatim": True,
        "policy_basis": "frozen_finance_policy_assumptions_not_forecasts",
        "business_facts_added": False, "financial_values_changed": False, "evidence_ids_added": []}]


def mechanical_repair_json(raw: str, schema: type[BaseModel], *, conservative_claim_repair=False,
                           terminal_punctuation_claim_repair=False,
                           source_disposition_claim_repair=False,
                           citation_list_format_claim_repair=False,
                           inline_citation_mirror_claim_repair=False,
                           financial_marker_claim_repair=False,
                           source_quality_scale_5_claim_repair=False,
                           existing_claim_body_assembly_claim_repair=False,
                           invalid_source_recency_claim_repair=False,
                           finance_note_partition_repair=False,
                           finance_assumption_notice_repair=False,
                           repair_evidence_catalog: dict[str, dict[str, Any]] | None = None,
                           repair_financial_ids: set[str] | None = None):
    """Apply only approved extraction, normalization, and conservative claim repairs."""
    decoder = json.JSONDecoder()
    extracted = False
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        objects = []
        for index, char in enumerate(raw):
            if char != "{":
                continue
            try:
                value, end = decoder.raw_decode(raw[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                objects.append((value, index, index + end))
        unique = {(start, end) for _, start, end in objects}
        if len(unique) != 1:
            raise
        value = objects[0][0]
        extracted = True
    if not isinstance(value, dict):
        raise ValueError("compact response must contain one JSON object")
    filtered, changes = _filter_and_normalize(value, schema)
    if conservative_claim_repair:
        if finance_assumption_notice_repair:
            changes.extend(_append_finance_assumption_notice(filtered, schema))
        if finance_note_partition_repair:
            changes.extend(_partition_finance_note_claims(filtered, schema))
        changes.extend(_repair_claim_wires(filtered, schema,
            terminal_punctuation=terminal_punctuation_claim_repair,
            source_disposition=source_disposition_claim_repair,
            citation_list_format=citation_list_format_claim_repair,
            inline_citation_mirror=inline_citation_mirror_claim_repair,
            financial_marker=financial_marker_claim_repair,
            source_quality_scale_5=source_quality_scale_5_claim_repair,
            invalid_source_recency=invalid_source_recency_claim_repair,
            existing_claim_body_assembly=existing_claim_body_assembly_claim_repair,
            repair_evidence_catalog=repair_evidence_catalog,
            repair_financial_ids=repair_financial_ids))
    elif (terminal_punctuation_claim_repair or source_disposition_claim_repair or
            citation_list_format_claim_repair or inline_citation_mirror_claim_repair or
            financial_marker_claim_repair or source_quality_scale_5_claim_repair or
            existing_claim_body_assembly_claim_repair or invalid_source_recency_claim_repair or
            finance_note_partition_repair or finance_assumption_notice_repair):
        raise ValueError("extended claim repair requires conservative claim repair")
    if extracted:
        changes.insert(0, {"op": "extract_unique_json", "path": "$"})
    candidate = schema.model_validate(filtered)
    return candidate, changes


def role_output_tokens(config_version: str) -> dict[str, int]:
    if config_version == CONFIG_VERSION:
        return dict(ROLE_OUTPUT_TOKENS)
    if config_version in (GEMINI_8192_CONFIG_VERSION, GEMINI_8192_MINIMAL_CONFIG_VERSION,
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
                          GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION,
                          GEMINI_8192_LINEAGE_ID_CONFIG_VERSION, GEMINI_8192_ID_COLLISION_CONFIG_VERSION,
                          GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION):
        return dict(GEMINI_8192_ROLE_OUTPUT_TOKENS)
    raise ValueError("unknown compact output-cap configuration")


def protocol_manifest(config_version: str = CONFIG_VERSION) -> dict[str, Any]:
    role_schemas = {role: role_wire_schema(role, config_version) for role in ROLE_WIRES}
    schemas = {name: schema.model_json_schema() for name, schema in {
        **role_schemas, "critic": CriticWire, "patch": PatchWire}.items()}
    return {
        "prompt_version": PROMPT_VERSION,
        "wire_version": WIRE_VERSION,
        "context_version": CONTEXT_VERSION,
        "config_version": config_version,
        "instruction_limit": INSTRUCTION_LIMIT,
        "instructions": {role: {"chars": len(instruction_for(role, config_version=config_version)),
            "utf8_bytes": len(instruction_for(role, config_version=config_version).encode("utf-8"))} for role in ROLE_INSTRUCTIONS},
        "repair_instruction_version": (REPAIR_INSTRUCTION_VERSION
            if config_version in (GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION,
                GEMINI_8192_LINEAGE_ID_CONFIG_VERSION, GEMINI_8192_ID_COLLISION_CONFIG_VERSION,
                GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION) else None),
        "repair_instructions": ({role: {"chars": len(instruction_for(role, repair=True, config_version=config_version)),
            "utf8_bytes": len(instruction_for(role, repair=True, config_version=config_version).encode("utf-8"))}
            for role in ROLE_INSTRUCTIONS} if config_version in (GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION,
                GEMINI_8192_LINEAGE_ID_CONFIG_VERSION, GEMINI_8192_ID_COLLISION_CONFIG_VERSION,
                GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION) else None),
        "wire_schemas": {name: {"sha256": canonical_hash(schema),
            "utf8_bytes": len(json.dumps(schema, ensure_ascii=False, sort_keys=True,
                separators=(",", ":")).encode("utf-8"))} for name, schema in schemas.items()},
        "role_input_tokens": ROLE_INPUT_TOKENS,
        "role_output_tokens": role_output_tokens(config_version),
        "finance_capacity_wire": (FINANCE_CAPACITY_WIRE_VERSION
            if config_version in FINANCE_CAPACITY_CONFIG_VERSIONS else None),
        "exact_text_parent_lineage": (EXACT_TEXT_PARENT_LINEAGE_VERSION
            if config_version in FINANCE_CAPACITY_CONFIG_VERSIONS else None),
        "lineage_identity_continuity": (LINEAGE_IDENTITY_CONTINUITY_VERSION
            if config_version in (GEMINI_8192_LINEAGE_ID_CONFIG_VERSION,
                GEMINI_8192_ID_COLLISION_CONFIG_VERSION, GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION) else None),
        "dual_declared_lineage": (DUAL_DECLARED_LINEAGE_VERSION
            if config_version == GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION else None),
        "claim_id_collision_adapter": (CLAIM_ID_COLLISION_ADAPTER_VERSION
            if config_version in (GEMINI_8192_ID_COLLISION_CONFIG_VERSION,
                GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION) else None),
        "canonical_citation_wire_adapter": (CANONICAL_CITATION_WIRE_ADAPTER_VERSION
            if config_version in FINANCE_CAPACITY_CONFIG_VERSIONS else None),
        "source_alias_selection": (SOURCE_ALIAS_SELECTION
            if config_version in FINANCE_CAPACITY_CONFIG_VERSIONS else None),
        "lossless_view_compression": ("lossless-default-view-v3-s5"
            if config_version in (GEMINI_8192_FINANCE_PARTITION_CONFIG_VERSION,
                GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION, GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION,
                GEMINI_8192_LINEAGE_ID_CONFIG_VERSION, GEMINI_8192_ID_COLLISION_CONFIG_VERSION,
                GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION) else None),
        "critic_patch_adapter": (CRITIC_PATCH_ADAPTER_VERSION
            if config_version in (GEMINI_8192_SOURCE_QUALITY_CONFIG_VERSION,
                GEMINI_8192_BODY_ASSEMBLY_CONFIG_VERSION,
                GEMINI_8192_FINANCE_CAPACITY_CONFIG_VERSION,
                GEMINI_8192_FINANCE_PARTITION_CONFIG_VERSION,
                GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION,
                GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION, GEMINI_8192_LINEAGE_ID_CONFIG_VERSION,
                GEMINI_8192_ID_COLLISION_CONFIG_VERSION, GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION) else None),
        "mechanical_claim_repair": (
            MECHANICAL_FINANCE_NOTICE_REPAIR_VERSION
            if config_version in (GEMINI_8192_FINANCE_NOTICE_CONFIG_VERSION,
                GEMINI_8192_REPAIR_INSTRUCTION_CONFIG_VERSION, GEMINI_8192_LINEAGE_ID_CONFIG_VERSION,
                GEMINI_8192_ID_COLLISION_CONFIG_VERSION, GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION) else
            MECHANICAL_FINANCE_PARTITION_REPAIR_VERSION
            if config_version == GEMINI_8192_FINANCE_PARTITION_CONFIG_VERSION else
            MECHANICAL_BODY_ASSEMBLY_REPAIR_VERSION
            if config_version in (GEMINI_8192_BODY_ASSEMBLY_CONFIG_VERSION,
                GEMINI_8192_FINANCE_CAPACITY_CONFIG_VERSION) else
            MECHANICAL_SOURCE_QUALITY_REPAIR_VERSION
            if config_version == GEMINI_8192_SOURCE_QUALITY_CONFIG_VERSION else
            MECHANICAL_FINANCE_MARKER_PREFIX_REPAIR_VERSION
            if config_version == GEMINI_8192_FINANCE_MARKER_PREFIX_CONFIG_VERSION else
            MECHANICAL_FINANCE_MARKER_REPAIR_VERSION
            if config_version == GEMINI_8192_FINANCE_MARKER_CONFIG_VERSION else
            MECHANICAL_INLINE_CITATION_REPAIR_VERSION
            if config_version in (GEMINI_8192_GAP_COUNT_CONFIG_VERSION,
                GEMINI_8192_EXACT_CARDINALITY_CONFIG_VERSION) else
            MECHANICAL_CITATION_FORMAT_REPAIR_VERSION
            if config_version == GEMINI_8192_CITATION_FORMAT_CONFIG_VERSION else
            MECHANICAL_SOURCE_DISPOSITION_REPAIR_VERSION
            if config_version == GEMINI_8192_CITATION_CONTRACT_CONFIG_VERSION else
            MECHANICAL_PUNCTUATION_REPAIR_VERSION
            if config_version in (GEMINI_8192_PUNCTUATION_REPAIR_CONFIG_VERSION,
                GEMINI_8192_PREMISE_CONFIG_VERSION,
                GEMINI_8192_TEXT_EQUALS_CLAIM_CONFIG_VERSION) else
            MECHANICAL_REPAIR_VERSION if config_version == GEMINI_8192_REPAIR_CONFIG_VERSION else None),
        "role_seconds": ROLE_SECONDS,
        "mvp30_seconds": MVP30_SECONDS,
        "valid_plan_seconds": VALID_PLAN_SECONDS,
        "finance_rows": {"ai_education": 21, "intelligent_ring": 27,
            "basis": "user-confirmed case-specific frozen formulas"},
    }
