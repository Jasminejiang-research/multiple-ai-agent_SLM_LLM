"""Explicit evidence access policy. Model-provider transport remains permitted."""
from contextlib import contextmanager
from contextvars import ContextVar

_FROZEN = ContextVar("frozen_evidence_access", default=False)


class FrozenEvidenceAccessError(RuntimeError):
    pass


def require_live_evidence_access():
    if _FROZEN.get():
        raise FrozenEvidenceAccessError("Live Web/RAG access is prohibited in frozen evidence mode")


@contextmanager
def frozen_evidence_scope():
    token = _FROZEN.set(True)
    try:
        yield
    finally:
        _FROZEN.reset(token)
