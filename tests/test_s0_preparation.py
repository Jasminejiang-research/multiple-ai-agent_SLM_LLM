"""Meaningful offline checks of the S0 preparation and refusal-to-freeze guard."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from evaluation.s0 import canonical_hash, local_path, request_requirements, validate_bundle, validate_packet

ROOT = Path(__file__).resolve().parents[1]/'docs/final_sprint/s0-v1'


def packet():
    return json.loads((ROOT/'cases/ai_education/packet.json').read_text(encoding='utf-8'))


def rehash(value):
    value['packet_sha256'] = canonical_hash({k:v for k,v in value.items() if k!='packet_sha256'})
    return value


def test_complete_real_bundle_is_valid_but_not_frozen():
    result=validate_bundle(ROOT,require_frozen=True)
    assert result['errors']==[]
    assert not result['formal_execution_allowed']
    assert any('ai_education' in p for p in result['pending'])
    assert any('intelligent_ring' in p for p in result['pending'])
    assert any('S3_D_preflight' in p for p in result['pending'])


def test_budget_accounts_for_all_roles_and_branches():
    requirements=request_requirements()
    assert [requirements[a]['minimum'] for a in 'ABCD']==[4,8,11,11]
    assert [requirements[a]['all_semantic_revisions'] for a in 'ABCD']==[4,12,18,18]
    assert [requirements[a]['with_one_structure_repair_per_task'] for a in 'ABCD']==[8,24,36,36]
    assert 2*sum(requirements[a]['minimum'] for a in 'ABCD')==68


@pytest.mark.parametrize('batches',[0,-1,True,1.5])
def test_invalid_batch_count_rejected(batches):
    with pytest.raises(ValueError):
        request_requirements(batches)


def test_packet_tampering_is_detected():
    value=packet()
    value['chunks'][0]['text']='invented evidence'
    errors=validate_packet(ROOT,value)
    assert 'packet hash mismatch' in errors
    assert 'chunk content differs from snapshot' in errors


def test_unknown_source_not_fixed_by_rehash():
    value=packet()
    value['chunks'][0]['source_id']='MADE-UP'
    assert 'chunk has unknown source ID' in validate_packet(ROOT,rehash(value))


def test_source_url_allowlist_is_enforced():
    value=packet()
    value['sources'][0]['url']='https://unapproved.example/evidence'
    assert any('URL outside allowlist' in e for e in validate_packet(ROOT,rehash(value)))


def test_duplicate_source_id_rejected():
    value=packet()
    value['sources'].append(deepcopy(value['sources'][0]))
    assert 'source IDs must be nonempty and unique' in validate_packet(ROOT,rehash(value))


def test_snapshot_hash_change_detected():
    value=packet()
    value['sources'][0]['html_sha256']='0'*64
    assert any('html hash mismatch' in e for e in validate_packet(ROOT,rehash(value)))


def test_approval_is_not_inferred_from_hash():
    value=packet()
    value['review_status']='approved'
    assert 'approval requires an explicit user record' in validate_packet(ROOT,rehash(value))


def test_path_escape_rejected():
    with pytest.raises(ValueError,match='escapes'):
        local_path(ROOT,'../outside.txt')


def test_empty_evidence_cannot_be_frozen():
    value=packet()
    value['chunks']=[]
    assert 'packet must contain fixed evidence chunks' in validate_packet(ROOT,rehash(value))
