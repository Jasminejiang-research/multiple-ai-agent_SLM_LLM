"""Explicit S3 H Micro configuration, independent of legacy hosted/Qwen defaults."""
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field, field_validator
from schemas.evidence import StrictModel
from workflow.review_config import ReviewRunConfig
from schemas.compact_wire import WIRE_VERSION
from workflow.compact_protocol import CONFIG_VERSION, LEGACY_PROTOCOL, MVP30_SECONDS

GRANITE_SOURCE = "hf.co/ibm-granite/granite-4.0-h-micro-GGUF:Q4_K_M"
GRANITE_ALIAS = "granite-h-micro-32k"


class GraniteConfig(StrictModel):
    endpoint: str = "http://127.0.0.1:11434"
    model_alias: Literal["granite-h-micro-32k"] = GRANITE_ALIAS
    source_model: Literal["hf.co/ibm-granite/granite-4.0-h-micro-GGUF:Q4_K_M"] = GRANITE_SOURCE
    quantization: Literal["Q4_K_M"] = "Q4_K_M"
    context_tokens: Literal[32768] = 32768
    model_config_version: str = "granite-h-micro-q4km-32k-s3-v1"
    # Legacy files keep auto offload/raw diagnostics for faithful reproduction.
    gpu_layers: Literal[-1, 0] = -1
    context_probe_mode: Literal["legacy_raw", "chat"] = "legacy_raw"
    protocol_version: Literal["body-then-grounding-v1", "compact-json-wire-v1-s6"] = LEGACY_PROTOCOL
    max_requests: int = Field(ge=1)
    max_total_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    max_prompt_chars: int = Field(ge=1)
    node_seconds: float = Field(default=1200, gt=0, le=1200)
    run_seconds: float = Field(default=5400, gt=0, le=5400)
    request_seconds: float = Field(default=1200, gt=0, le=1200)
    sample_seconds: float = Field(default=5, gt=0, le=10)
    status: Literal["preflight_candidate_not_frozen"] = "preflight_candidate_not_frozen"

    @field_validator("endpoint")
    @classmethod
    def local_only(cls, value):
        url = urlsplit(value)
        if url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost", "::1") or url.username or url.password or url.query or url.fragment:
            raise ValueError("Granite must use an explicit local loopback HTTP endpoint")
        if url.path.rstrip("/") not in ("", "/v1"):
            raise ValueError("expected Ollama root or /v1 endpoint")
        # One canonical key prevents localhost/127.0.0.1 or /v1 from bypassing the lease.
        return f"http://127.0.0.1:{url.port or 80}"

    def review_config(self, run_kind, *, model_digest):
        if not model_digest:
            raise ValueError("verified model digest required")
        return ReviewRunConfig(condition="D", run_kind=run_kind, provider="local",
            model_exact_id=f"{self.model_alias}@{model_digest}", model_config_version=self.model_config_version,
            max_requests=self.max_requests, max_total_tokens=self.max_total_tokens,
            max_output_tokens=self.max_output_tokens, max_prompt_chars=self.max_prompt_chars,
            node_seconds=self.node_seconds, run_seconds=self.run_seconds, request_seconds=self.request_seconds,
            transport_retries=0, protocol_version=self.protocol_version,
            mvp_seconds=MVP30_SECONDS,
            config_version=CONFIG_VERSION if self.protocol_version == WIRE_VERSION else "review-run-v1-s2")
