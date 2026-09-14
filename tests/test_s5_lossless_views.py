"""Lossless view compression leaves all words, claims and evidence recoverable."""
from copy import deepcopy
import json

import pytest

from workflow.compact_views import (
    CLAIM_DEFAULTS, LOSSLESS_VIEW_VERSION, compact_generation_view,
    _deduplicated_wire_claims, _wire_claims,
)


def claim(cid="CL001", **updates):
    result = dict(i=cid, t="The original exact claim with its citation [E01].",
        k="factual", d="Unchanged model explanation.", s="sourced_fact", ss="direct",
        q=.8, c="high", cr="directly_supported", **deepcopy(CLAIM_DEFAULTS))
    result.update(e=["E01"])
    result.update(updates)
    return result


def restore(view):
    result = deepcopy(view)
    metadata = result.pop("lossless_view")
    pool = metadata.get("claim_text_pool", [])
    for capsule in result.get("upstream", []):
        claims = capsule.get("claims")
        if isinstance(claims, list):
            for item in claims:
                for key in ("t", "d", "p"):
                    value = item.get(key)
                    if isinstance(value, list):
                        assert len(value) == 1 and type(value[0]) is int
                        item[key] = pool[value[0]]
        elif isinstance(claims, dict) and "groups" in claims:
            for group in claims["groups"]:
                for key, value in group.get("constant_columns", {}).items():
                    if key in ("t", "d", "p") and isinstance(value, list):
                        assert len(value) == 1 and type(value[0]) is int
                        group["constant_columns"][key] = pool[value[0]]
                for index, key in enumerate(group["columns"]):
                    if key in ("t", "d", "p"):
                        for row in group["rows"]:
                            value = row[index]
                            if isinstance(value, list):
                                assert len(value) == 1 and type(value[0]) is int
                                row[index] = pool[value[0]]
    for index in metadata["writer_claim_table_capsules"]:
        table = result["upstream"][index]["claims"]
        reconstructed = [None] * table["count"]
        for group in table["groups"]:
            for position, row in zip(group["positions"], group["rows"], strict=True):
                assert reconstructed[position] is None
                reconstructed[position] = dict(deepcopy(group.get("constant_columns", {})),
                    **dict(zip(group["columns"], row, strict=True)))
        assert all(item is not None for item in reconstructed)
        result["upstream"][index]["claims"] = reconstructed
    for item in _wire_claims(result):
        for key, value in metadata["claim_defaults"].items():
            item.setdefault(key, deepcopy(value))
    for index in metadata["critic_upstream_claims_from_reviewed_wire"]:
        result["upstream"][index]["claims"] = deepcopy(
            _deduplicated_wire_claims(result["reviewed_artifact"]["wire"]))
    return result


@pytest.mark.parametrize("role", ["writer", "finance", "strategy", "revision"])
def test_defaults_roundtrip_all_claim_fields_and_do_not_mutate_source(role):
    first = claim()
    second = claim("CL002", pi="CL001", r=.3, e=["E01", "E02"], f=["base.monthly_revenue"],
        p="This is the exact nonempty premise.", dc=True, hi=True, cf=True)
    source = {"upstream": [{"role": "research", "version": 1,
        "claims": [first, second], "unresolved": [{"claim": "CL002", "major": True}],
        "unresolved_major": True}], "brief": {"text": "All original brief words remain."}}
    before = deepcopy(source)
    result = compact_generation_view(source, role)
    assert source == before and restore(result) == source
    if role == "writer":
        second_group = [group for group in result["upstream"][0]["claims"]["groups"]
            if 1 in group["positions"]][0]
        assert second_group["rows"][second_group["positions"].index(1)] == [second[key]
            for key in second_group["columns"]]
    else:
        assert result["upstream"][0]["claims"][1] == second
    assert result["lossless_view"]["version"] == LOSSLESS_VIEW_VERSION
    assert result["lossless_view"]["field_meanings"]["r"] == "source recency 0..1/null; never revenue/result/amount"


def test_critic_removes_only_exact_recoverable_duplicate_and_retains_dispositions():
    first, second = claim(), claim("CL002", cf=True)
    capsule = dict(role="finance", version=1, claims=[first, second],
        unresolved=[dict(claim="CL002", conflict=True)], unresolved_major=True)
    source = dict(upstream=[capsule], reviewed_artifact=dict(id="finance.initial", version=1,
        wire={"revenue": [{"text": first["t"], "claims": [first]}],
              "economics": [{"text": second["t"], "claims": [second, first]}]}))
    result = compact_generation_view(source, "finance_critic")
    assert "claims" not in result["upstream"][0]
    assert result["upstream"][0]["unresolved"] == capsule["unresolved"]
    assert result["upstream"][0]["unresolved_major"] is True
    assert restore(result) == source


@pytest.mark.parametrize("mutation", ["text", "evidence", "order", "version"])
def test_critic_does_not_remove_nonidentical_capsule(mutation):
    first, second = claim(), claim("CL002")
    source = dict(upstream=[dict(role="finance", version=1, claims=[first, second])],
        reviewed_artifact=dict(id="finance.initial", version=1,
            wire={"claims": deepcopy([first, second])}))
    if mutation == "text": source["upstream"][0]["claims"][0]["t"] += " Retain these added words."
    if mutation == "evidence": source["upstream"][0]["claims"][0]["e"] = ["E02"]
    if mutation == "order": source["upstream"][0]["claims"].reverse()
    if mutation == "version": source["upstream"][0]["version"] = 2
    result = compact_generation_view(source, "finance_critic")
    assert "claims" in result["upstream"][0]
    assert restore(result) == source


def test_default_elision_does_not_confuse_numeric_zero_with_false():
    source = {"claims": [claim(dc=0, hi=0, cf=0)]}
    result = compact_generation_view(source, "writer")
    assert all(result["claims"][0][key] == 0 for key in ("dc", "hi", "cf"))
    assert restore(result) == source


def test_writer_table_keeps_every_value_type_and_original_claim_order():
    original = [claim("CL002", cf=True, e=["E02", "E01"], r=0),
        claim("CL001", pi="CL002", f=["a", "b"], dc=True, q=0)]
    source = {"upstream": [{"claims": original}]}
    result = compact_generation_view(source, "writer")
    table = result["upstream"][0]["claims"]
    assert table["count"] == len(original)
    for group in table["groups"]:
        for position, row in zip(group["positions"], group["rows"], strict=True):
            claim_dict = original[position]
            assert len(row) == len(group["columns"])
            assert all(type(value) is type(claim_dict[key]) and value == claim_dict[key]
                for key, value in zip(group["columns"], row, strict=True))
            for key, value in group.get("constant_columns", {}).items():
                assert type(value) is type(claim_dict[key]) and value == claim_dict[key]
            for key in claim_dict.keys() - set(group["columns"]) - set(group.get("constant_columns", {})):
                assert type(claim_dict[key]) is type(CLAIM_DEFAULTS[key])
                assert claim_dict[key] == CLAIM_DEFAULTS[key]
    assert restore(result) == source


def test_writer_mismatched_claim_key_sets_are_not_table_encoded():
    original = [claim("CL001"), dict(claim("CL002"), extra="Keep this original extra field.")]
    source = {"upstream": [{"claims": original}]}
    result = compact_generation_view(source, "writer")
    assert isinstance(result["upstream"][0]["claims"], list)
    assert restore(result) == source


def test_constant_columns_require_exact_value_and_type_and_roundtrip():
    source = {"upstream": [{"claims": [claim(f"CL{i:03d}", q=.8, r=0 if i == 0 else 0.0)
        for i in range(8)]}]}
    result = compact_generation_view(source, "writer")
    groups = result["upstream"][0]["claims"]["groups"]
    assert any(group.get("constant_columns") for group in groups)
    assert all("r" not in group.get("constant_columns", {}) for group in groups)
    assert restore(result) == source


def test_duplicate_long_text_pool_is_exact_and_never_pools_evidence_or_finance_ids():
    text = "This complete original long claim text retains all its exact words and punctuation. " * 5
    premise = "This exact repeated premise remains unchanged, including its source and scope. " * 4
    source = {"upstream": [{"claims": [claim("CL001", t=text, p=premise),
        claim("CL002", t=text + " An additional original word.", p="Different premise.")]},
        {"claims": [claim("CL003", t=text, p=premise, f=[text], e=[text]),
        claim("CL004", t=text + " Different.", p="Another premise.")]}]}
    result = compact_generation_view(source, "writer")
    assert text in result["lossless_view"]["claim_text_pool"]
    assert restore(result) == source
    assert len(json.dumps(result)) < len(json.dumps(compact_generation_view(
        {"upstream": []}, "writer"))) + len(json.dumps(source))
    second_table = result["upstream"][1]["claims"]
    for group in second_table["groups"]:
        for index, key in enumerate(group["columns"]):
            if key in ("e", "f"):
                assert all(all(isinstance(value, str) for value in row[index]) for row in group["rows"])


def test_pool_not_used_when_no_exact_duplicate_string_can_reduce_full_view():
    source = {"upstream": [{"claims": [claim("CL001", t="A" * 50),
        claim("CL002", t="B" * 50, d="Unique explanation.")]}]}
    result = compact_generation_view(source, "writer")
    assert "claim_text_pool" not in result["lossless_view"]
    assert restore(result) == source


def test_v17_actual_finance_view_roundtrip_and_measured_prompt_size():
    from pathlib import Path
    from schemas.compact_wire import Finance8Wire, ProposalWire, CriticWire
    from workflow.contract_context import ContractContext, ContractArtifact
    from workflow.compact_protocol import (
        GEMINI_8192_FINANCE_CAPACITY_CONFIG_VERSION as config_version,
        GEMINI_8192_FINANCE_PARTITION_CONFIG_VERSION as connected_config_version,
        mechanical_repair_json, evidence_catalog, expand_role_wire,
        normalize_exact_text_parent_lineage, preserve_upstream_dispositions, make_envelope,
    )
    folder = Path(__file__).resolve().parents[1] / "docs/final_sprint/s5-llm-only-v17"
    context = ContractContext.from_case(folder / "frozen_inputs", "ai_education", condition="B")
    events = [json.loads(line) for line in (folder / "smokes/ai_education-B/events.jsonl").read_text(
        encoding="utf-8").splitlines()]
    raw = json.loads([e["payload"]["raw_output"] for e in events if e["kind"] == "call"
        and e["payload"]["task_role"] == "finance" and e["payload"].get("raw_output")][-1])
    # In-memory simulation of the separately authorized v18 repair; source bytes stay untouched.
    for key in ("revenue", "costs", "economics"):
        for note in raw[key]:
            for item in note["claims"]:
                if type(item.get("r")) in (int, float) and not 0 <= item["r"] <= 1:
                    item["r"] = None
    note = raw["economics"][0]
    raw["economics"] = [dict(deepcopy(note), claims=deepcopy(note["claims"][i:i + 8]))
        for i in range(0, len(note["claims"]), 8)]
    wire, _ = mechanical_repair_json(json.dumps(raw), Finance8Wire,
        conservative_claim_repair=True, terminal_punctuation_claim_repair=True,
        source_disposition_claim_repair=True, citation_list_format_claim_repair=True,
        inline_citation_mirror_claim_repair=True, financial_marker_claim_repair=True,
        source_quality_scale_5_claim_repair=True, existing_claim_body_assembly_claim_repair=True,
        repair_evidence_catalog=evidence_catalog(context.packet),
        repair_financial_ids=set(context.finance.value_ids))
    records = [e["payload"]["artifact"] for e in events if e["kind"] == "artifact"
        and e["payload"]["stage"] == "effective"]
    upstream = tuple(ContractArtifact(item["role"], item["artifact_version"], item["case_id"],
        item["packet_sha256"], item["brief_sha256"], json.dumps(item["payload"]),
        json.dumps(item["confidence_changes"]), item["pruned"], item["unresolved_major"])
        for item in records)
    candidate = expand_role_wire(context, "finance", wire, version=1, config_version=config_version)
    normalize_exact_text_parent_lineage(candidate, upstream)
    preserve_upstream_dispositions(candidate, upstream)
    artifact = context.accept("finance", candidate, upstream=upstream, transitive_lineage=True)
    for role, schema, artifacts in (("writer", ProposalWire, upstream + (artifact,)),
            ("finance_critic", CriticWire, (artifact,))):
        envelope = make_envelope(context, role, schema, upstream=artifacts, config_version=config_version)
        body = json.loads(envelope.prompt)
        original = deepcopy(body["view"])
        body["view"] = compact_generation_view(original, role)
        assert restore(body["view"]) == original
        before = len(envelope.prompt + envelope.system_instruction)
        after = len(json.dumps(body, ensure_ascii=False, separators=(",", ":"))) + len(envelope.system_instruction)
        assert after < before
        assert after <= 26000
        connected = make_envelope(context, role, schema, upstream=artifacts,
            config_version=connected_config_version)
        connected_body = json.loads(connected.prompt)
        assert connected_body["view"]["lossless_view"]["version"] == LOSSLESS_VIEW_VERSION
        assert restore(connected_body["view"]) == original
        assert len(connected.prompt + connected.system_instruction) <= 26000
        print(json.dumps(dict(role=role, before_chars=before, after_chars=after,
            within_26000=after <= 26000)))
