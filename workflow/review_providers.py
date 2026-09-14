"""Gemini's explicit single physical call adapter for the common S2 controller."""
from __future__ import annotations

import os

from google import genai
from google.genai import types
from httpx import TimeoutException
from workflow.gemini_schema import relaxed_response_schema
from workflow.review_runtime import PhysicalResponse, ProviderFailure


def resolve_gemini_credential(*, expected_source=None, environment=None):
    """Select one named Gemini credential without exposing its value.

    Google SDK precedence is explicit: GOOGLE_API_KEY wins when both supported
    variables are present. Equal duplicate values are accepted, then the unused
    name is removed from this process so the physical client has one source.
    """
    values = os.environ if environment is None else environment
    google_key = values.get("GOOGLE_API_KEY")
    gemini_key = values.get("GEMINI_API_KEY")
    if google_key and gemini_key and google_key != gemini_key:
        raise ValueError("conflicting Gemini credential variables")
    if google_key:
        key, source, other = google_key, "GOOGLE_API_KEY", "GEMINI_API_KEY"
    elif gemini_key:
        key, source, other = gemini_key, "GEMINI_API_KEY", "GOOGLE_API_KEY"
    else:
        raise ValueError("Gemini API credential missing")
    if expected_source is not None and source != expected_source:
        raise ValueError("Gemini credential source changed from frozen selection")
    if environment is None:
        os.environ.pop(other, None)
    return key, source


class GeminiPhysicalProvider:
    provider = "gemini"

    def __init__(self, *, api_key, model_exact_id="gemini-2.5-flash", sdk_client=None):
        self.model_exact_id = model_exact_id
        self.client = sdk_client if sdk_client is not None else genai.Client(api_key=api_key,
            http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)))

    def invoke(self, request):
        try:
            thinking_config = (None if request.thinking_budget is None else
                types.ThinkingConfig(thinking_budget=request.thinking_budget, include_thoughts=False))
            response = self.client.models.generate_content(model=self.model_exact_id, contents=request.prompt,
                config=types.GenerateContentConfig(system_instruction=request.system_instruction,
                    response_mime_type="application/json", response_schema=relaxed_response_schema(request.schema),
                    temperature=request.temperature, max_output_tokens=request.max_output_tokens,
                    thinking_config=thinking_config,
                    http_options=types.HttpOptions(timeout=max(1, int(request.timeout_seconds * 1000)),
                        retry_options=types.HttpRetryOptions(attempts=1))))
        except TimeoutException as exc:
            raise TimeoutError("Gemini HTTP timeout; physical dispatch outcome may be unknown") from exc
        except Exception as exc:
            status = getattr(exc, "code", None)
            raise ProviderFailure(type(exc).__name__, retryable=status in (429, 500, 502, 503),
                request_finished=isinstance(status, int)) from exc
        usage = response.usage_metadata
        raw = usage.model_dump(mode="json") if usage is not None else None
        candidates = response.candidates or []
        finish = getattr(candidates[0], "finish_reason", None) if candidates else None
        return PhysicalResponse(response.text or "", raw,
            getattr(usage, "prompt_token_count", None), getattr(usage, "candidates_token_count", None),
            getattr(usage, "total_token_count", None), getattr(finish, "value", finish))
