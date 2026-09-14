"""Legacy import compatibility for the shared provider-neutral enum contract."""
from workflow.schema_contract import MAX_CONTRACT_MEMBERS, MAX_TRAVERSAL_DEPTH, schema_enum_contract

__all__ = ["schema_enum_contract", "MAX_CONTRACT_MEMBERS", "MAX_TRAVERSAL_DEPTH"]
