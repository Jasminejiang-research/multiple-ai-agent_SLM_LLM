"""Native Ollama transport: full shared schemas, exact usage and one physical call."""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from workflow.review_runtime import PhysicalResponse, ProviderFailure


def render_granite_pair(messages):
    """Official H Micro template for plain system/user text, without tools/images.

    Used only to count the context probe. The server applies its real template,
    and the preflight compares the returned count rather than trusting this count.
    """
    return "".join(f"<|start_of_role|>{m['role']}<|end_of_role|>{m['content']}<|end_of_text|>\n"
                   for m in messages) + "<|start_of_role|>assistant<|end_of_role|>"


class GranitePhysicalProvider:
    provider = "local"

    def __init__(self, config, *, model_digest, session=None, context_tokenizer=None):
        self.config = config
        self.model_exact_id = f"{config.model_alias}@{model_digest}"
        self.session = session if session is not None else requests.Session()
        self.session.trust_env = False
        self.session.mount("http://", HTTPAdapter(max_retries=0))
        self.last_raw = None
        self.last_diagnostic = None
        self.context_tokenizer = context_tokenizer

    def invoke(self, request):
        self.last_raw = None
        self.last_diagnostic = None
        messages = []
        if request.system_instruction:
            messages.append(dict(role="system", content=request.system_instruction))
        messages.append(dict(role="user", content=request.prompt))
        payload = dict(model=self.config.model_alias, messages=messages, stream=False,
            format=request.schema.model_json_schema(), keep_alive="5m",
            options=dict(num_ctx=32768, temperature=0, num_predict=request.max_output_tokens))
        if self.config.gpu_layers == 0:
            payload["options"]["num_gpu"] = 0
        endpoint = "/api/chat"
        expected_tokens = None
        request_mode = "chat"
        if self.context_tokenizer is not None:
            if self.config.context_probe_mode == "legacy_raw":
                # Keep the original failure reproducible through the unchanged v1 config.
                endpoint = "/api/generate"
                payload.pop("messages")
                payload.update(raw=True, prompt=(request.system_instruction or "") + "\n" + request.prompt)
                expected_text, request_mode = payload["prompt"], "raw_context_probe"
            else:
                expected_text, request_mode = render_granite_pair(messages), "chat_context_probe"
            expected_tokens = len(self.context_tokenizer.encode(expected_text, add_special_tokens=False).ids)
        self.last_diagnostic = dict(endpoint=endpoint, expected_input_tokens=expected_tokens,
            request_mode=request_mode, gpu_layers=self.config.gpu_layers, http_status=None, response=None)
        try:
            response = self.session.post(self.config.endpoint + endpoint, json=payload,
                timeout=(min(5, request.timeout_seconds), request.timeout_seconds))
        except requests.Timeout as exc:
            self.last_diagnostic["transport_error_type"] = type(exc).__name__
            raise TimeoutError("Ollama response timeout; local lease remains quarantined") from exc
        except requests.RequestException as exc:
            self.last_diagnostic["transport_error_type"] = type(exc).__name__
            raise ProviderFailure(type(exc).__name__, request_finished=False) from exc
        self.last_diagnostic["http_status"] = response.status_code
        try:
            raw = response.json()
        except ValueError as exc:
            self.last_diagnostic["response_parse_error"] = type(exc).__name__
            if response.status_code != 200:
                raise ProviderFailure(f"OllamaHTTP{response.status_code}", request_finished=False) from exc
            raise ProviderFailure("OllamaInvalidResponse", request_finished=False) from exc
        self.last_raw = raw
        self.last_diagnostic["response"] = raw
        if response.status_code != 200:
            # A local server error does not prove its runner has stopped.
            raise ProviderFailure(f"OllamaHTTP{response.status_code}", request_finished=False)
        if not isinstance(raw, dict):
            raise ProviderFailure("OllamaInvalidResponse", request_finished=False)
        # Ollama can write an error object after the HTTP 200 headers have been sent.
        if raw.get("error"):
            raise ProviderFailure("OllamaGenerationError", request_finished=False)
        if raw.get("done") is not True:
            raise ProviderFailure("OllamaMissingCompletion", request_finished=False)
        if raw.get("model", "").removesuffix(":latest") != self.config.model_alias:
            raise ProviderFailure("OllamaModelIdentityMismatch", request_finished=True)
        prompt, output = raw.get("prompt_eval_count"), raw.get("eval_count")
        total = prompt + output if type(prompt) is int and type(output) is int else None
        usage = {k: raw.get(k) for k in ("model", "created_at", "done", "done_reason", "total_duration", "load_duration",
            "prompt_eval_count", "prompt_eval_cached_count", "prompt_eval_duration", "eval_count", "eval_duration")}
        usage["timing_unit"] = "nanoseconds"
        usage["requested_gpu_layers"] = self.config.gpu_layers
        cached = raw.get("prompt_eval_cached_count")
        prefill_count = prompt-cached if type(prompt) is int and type(cached) is int else prompt
        usage["prefill_rate_basis"] = "uncached_tokens" if type(cached) is int else "all_input_tokens_cache_count_unavailable"
        if expected_tokens is not None:
            usage.update(context_probe_expected_tokens=expected_tokens,
                         context_probe_token_count_delta=None if prompt is None else prompt-expected_tokens,
                         request_mode=request_mode)
        for prefix, count, duration in (("prefill", prefill_count, raw.get("prompt_eval_duration")),
                                        ("generation", output, raw.get("eval_duration"))):
            usage[prefix + "_tokens_per_second"] = count / (duration / 1e9) if type(count) is int and type(duration) is int and duration > 0 else None
        text = raw.get("response", "") if endpoint == "/api/generate" else raw.get("message", {}).get("content", "")
        return PhysicalResponse(text, usage, prompt, output, total, raw.get("done_reason"))


def inspect_ollama(config, *, session=None):
    """Read metadata without loading a model; reject mismatched or implicit context."""
    session = session if session is not None else requests.Session()
    session.trust_env = False
    def get(path):
        response = session.get(config.endpoint + path, timeout=5)
        response.raise_for_status()
        return response.json()
    version, tags, running = get("/api/version"), get("/api/tags"), get("/api/ps")
    aliases = {m["name"].removesuffix(":latest"): m for m in tags.get("models", [])}
    if config.model_alias not in aliases:
        raise ValueError("explicit Granite 32K alias is missing")
    model = aliases[config.model_alias]
    response = session.post(config.endpoint + "/api/show", json={"model": config.model_alias}, timeout=5)
    response.raise_for_status()
    show = response.json()
    details = show.get("details", {})
    if details.get("parent_model") != config.source_model:
        raise ValueError("alias does not derive from the planned official IBM H Micro source")
    if details.get("quantization_level") != "Q4_K_M" or details.get("family") != "granitehybrid":
        raise ValueError("model is not the planned Granite hybrid Q4_K_M")
    info = show.get("model_info", {})
    count = info.get("general.parameter_count", 0)
    if not 2_500_000_000 <= count <= 4_000_000_000:
        raise ValueError("model parameter count is not H Micro; no implicit H 1B substitution")
    params = dict(line.split(None, 1) for line in show.get("parameters", "").splitlines() if len(line.split(None, 1)) == 2)
    if params.get("num_ctx") != "32768" or float(params.get("temperature", "nan")) != 0:
        raise ValueError("alias lacks explicit 32768 context / zero temperature")
    for loaded in running.get("models", []):
        if loaded["name"].removesuffix(":latest") != config.model_alias:
            raise ValueError("another model is already loaded; cannot run a comparable single-model preflight")
    return dict(ollama_version=version.get("version"), model_digest=model["digest"], model_metadata=model,
        parameters=params, model_info=info, details=details, loaded_models=running.get("models", []),
        context_status="configured_not_yet_measured")
