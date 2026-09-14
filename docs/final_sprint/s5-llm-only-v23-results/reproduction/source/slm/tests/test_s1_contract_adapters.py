"""SLM side of the common S1 contract, without importing SLM from core tests."""
from unittest.mock import patch
import json

from slm.factories import build_slm_contract_generator
from slm.schema_contract import schema_enum_contract
from schemas.contract_outputs import (ContractResearchAnalysis, ContractStrategyAnalysis, ContractFinanceAssumptions)
from workflow.contract_generation import ContractGenerator
from workflow.generation_batches import CONTRACT_BATCH_MODELS


def test_slm_factory_returns_exact_common_generator_without_pruning_or_nested_batches():
    client = object()
    with patch("slm.factories.PrunedAdapter", side_effect=AssertionError("pruning forbidden")), \
         patch("slm.factories.ChunkedProposalAdapter", side_effect=AssertionError("nested batches forbidden")), \
         patch("slm.factories.SLMClient", side_effect=AssertionError("implicit client forbidden")):
        generator = build_slm_contract_generator(client)
    assert type(generator) is ContractGenerator
    assert generator.client is client


def test_slm_schema_enum_contract_preserves_new_full_provenance():
    for schema in (ContractResearchAnalysis, ContractStrategyAnalysis, ContractFinanceAssumptions, *CONTRACT_BATCH_MODELS):
        text = schema_enum_contract(schema)
        assert "factual" in text
        assert "model_proposed" in json.dumps(schema.model_json_schema())
