"""Offline safety/contract tests. These never count as real Granite feasibility evidence."""
import json
from pathlib import Path
from types import SimpleNamespace
from threading import Event
import time

import pytest
import requests

from evaluation.s2_fixtures import SyntheticProvider, synthetic_artifact
from slm.granite_config import GraniteConfig
from slm.granite_provider import GranitePhysicalProvider, inspect_ollama
from slm.granite_preflight import GranitePreflight, ProbeAck, writer_probe_prompt, load_context_tokenizer
from slm.resource_monitor import GIB, SustainedResourceGate, ResourceMonitor
from slm.owned_ollama import OwnedOllama
from workflow.contract_context import ContractContext
from workflow.contract_generation import ContractGenerator
from workflow.review_events import EventJournal, replay_events
from workflow.review_runtime import PhysicalRequest, PhysicalResponse, ProviderFailure
from workflow.schema_contract import schema_enum_contract

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def config():
    return GraniteConfig.model_validate_json((ROOT / "slm/configs/granite_preflight_v1.json").read_text())


@pytest.fixture
def context():
    return ContractContext.from_case(ROOT / "docs/final_sprint/s0-v1", "ai_education", condition="D")


@pytest.mark.parametrize("change", [{"model_alias":"granite-h-1b"}, {"quantization":"Q8_0"},
    {"context_tokens":4096}, {"node_seconds":1201}, {"run_seconds":5401},
    {"endpoint":"https://cloud.example/v1"}, {"endpoint":"http://user:secret@localhost:11434"}])
def test_config_rejects_scope_changes(config, change):
    with pytest.raises(ValueError):
        GraniteConfig.model_validate({**config.model_dump(), **change})


def test_config_canonical_lease_key_and_limits(config):
    other = GraniteConfig.model_validate({**config.model_dump(), "endpoint":"http://localhost:11434/v1/"})
    assert other.endpoint == config.endpoint
    reviewed = config.review_config("preflight", model_digest="sha256:test")
    assert reviewed.max_requests == 18 and reviewed.max_output_tokens == 1024
    assert reviewed.reviewed_roles == ("research", "strategy", "finance", "final")
    assert reviewed.transport_retries == 0 and reviewed.context_tokens == 32768


class Session:
    def __init__(self, raw=None, error=None, status=200):
        self.raw, self.error, self.status = raw, error, status
        self.calls = []
    def mount(self, prefix, adapter):
        assert adapter.max_retries.total == 0
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return SimpleNamespace(status_code=self.status, json=lambda:self.raw, raise_for_status=lambda:None)


def physical():
    return PhysicalRequest("full unchanged prompt", ProbeAck, "full system", 0, 1024, 7)


def test_native_schema_and_usage(config):
    session = Session(dict(model=config.model_alias+":latest", done=True, message={"content":'{"ok":true}'},
        prompt_eval_count=120, prompt_eval_cached_count=20, prompt_eval_duration=2_000_000_000,
        eval_count=10, eval_duration=1_000_000_000, done_reason="stop"))
    response = GranitePhysicalProvider(config, model_digest="digest", session=session).invoke(physical())
    url, kwargs = session.calls[0]
    body = kwargs["json"]
    assert url.endswith("/api/chat") and body["format"] == ProbeAck.model_json_schema()
    assert body["messages"] == [dict(role="system", content="full system"), dict(role="user", content="full unchanged prompt")]
    assert body["options"] == dict(num_ctx=32768, temperature=0, num_predict=1024)
    assert response.total_tokens == 130 and response.usage_raw["prefill_tokens_per_second"] == 50
    assert response.usage_raw["generation_tokens_per_second"] == 10
    assert response.usage_raw["load_duration"] is None and not session.trust_env


def test_raw_context_counts_exact_sent_text_and_preserves_missing_usage(config):
    texts = []
    tokenizer = SimpleNamespace(encode=lambda text, **kwargs: texts.append(text) or SimpleNamespace(ids=list(range(5))))
    session = Session(dict(model=config.model_alias, done=True, response='{"ok":true}', prompt_eval_count=6))
    response = GranitePhysicalProvider(config, model_digest="d", session=session, context_tokenizer=tokenizer).invoke(physical())
    body = session.calls[0][1]["json"]
    assert session.calls[0][0].endswith("/api/generate") and body["raw"]
    assert texts == [body["prompt"]] and "messages" not in body
    assert response.usage_raw["context_probe_token_count_delta"] == 1
    assert response.total_tokens is None and response.output_tokens is None


def test_cpu_candidate_preserves_scope_and_explicitly_disables_gpu(config):
    cpu=GraniteConfig.model_validate_json((ROOT/'slm/configs/granite_preflight_cpu_v2.json').read_text())
    changed={k for k,v in cpu.model_dump().items() if v!=config.model_dump()[k]}
    assert changed=={'gpu_layers','context_probe_mode','model_config_version'}
    session=Session(dict(model=cpu.model_alias,done=True,message={'content':'{"ok":true}'}))
    provider=GranitePhysicalProvider(cpu,model_digest='d',session=session)
    response=provider.invoke(physical())
    assert session.calls[0][1]['json']['options']['num_gpu']==0
    assert response.text=='{"ok":true}' and response.usage_raw['requested_gpu_layers']==0


def test_cpu_context_counts_the_official_chat_pair_without_raw_bypass(config):
    cpu=config.model_copy(update=dict(gpu_layers=0,context_probe_mode='chat'))
    texts=[]
    tokenizer=SimpleNamespace(encode=lambda text,**kw:texts.append(text) or SimpleNamespace(ids=[1]*8))
    session=Session(dict(model=cpu.model_alias,done=True,message={'content':'{"ok":true}'},prompt_eval_count=8))
    response=GranitePhysicalProvider(cpu,model_digest='d',session=session,context_tokenizer=tokenizer).invoke(physical())
    url,kwargs=session.calls[0]
    assert url.endswith('/api/chat') and 'raw' not in kwargs['json']
    assert kwargs['json']['options']['num_gpu']==0
    assert texts==['<|start_of_role|>system<|end_of_role|>full system<|end_of_text|>\n'
                  '<|start_of_role|>user<|end_of_role|>full unchanged prompt<|end_of_text|>\n'
                  '<|start_of_role|>assistant<|end_of_role|>']
    assert response.text=='{"ok":true}' and response.usage_raw['context_probe_token_count_delta']==0
    assert response.usage_raw['request_mode']=='chat_context_probe'


@pytest.mark.parametrize("session,error", [(Session(error=requests.Timeout()), TimeoutError),
    (Session(error=requests.ConnectionError()), ProviderFailure), (Session(status=500), ProviderFailure),
    (Session({"done":False}), ProviderFailure), (Session({"done":True,"model":"wrong"}), ProviderFailure)])
def test_transport_never_retries_or_falls_back(config, session, error):
    with pytest.raises(error):
        GranitePhysicalProvider(config, model_digest="d", session=session).invoke(physical())
    assert len(session.calls) == 1


def test_http_200_generation_error_is_preserved_and_not_repaired(config):
    raw={"error":"got exception: Unexpected empty grammar stack after accepting piece: @ (31)"}
    session=Session(raw)
    provider=GranitePhysicalProvider(config,model_digest="d",session=session)
    with pytest.raises(ProviderFailure) as failure:
        provider.invoke(physical())
    assert failure.value.error_type=="OllamaGenerationError"
    assert not failure.value.request_finished and not failure.value.retryable
    assert provider.last_diagnostic["response"]==raw
    assert provider.last_diagnostic["http_status"]==200 and len(session.calls)==1


def test_failed_transport_does_not_reuse_previous_native_response(config):
    session=Session(dict(model=config.model_alias,done=True,message={"content":'{"ok":true}'}))
    provider=GranitePhysicalProvider(config,model_digest="d",session=session)
    provider.invoke(physical())
    session.error=requests.ConnectionError()
    with pytest.raises(ProviderFailure): provider.invoke(physical())
    assert provider.last_raw is None and provider.last_diagnostic["response"] is None
    assert provider.last_diagnostic["transport_error_type"]=="ConnectionError"


def test_actual_partial_200_response_retains_generated_prefix(config):
    raw=dict(model=config.model_alias,message={"role":"assistant","content":"{\n"},done=False)
    provider=GranitePhysicalProvider(config,model_digest="d",session=Session(raw))
    with pytest.raises(ProviderFailure) as failure: provider.invoke(physical())
    assert failure.value.error_type=="OllamaMissingCompletion"
    assert not failure.value.request_finished
    assert provider.last_diagnostic["response"]["message"]["content"]=="{\n"
    assert provider.last_diagnostic["http_status"]==200


def test_non_json_http_failure_keeps_http_status(config):
    session=Session(status=503)
    def post(*args, **kwargs):
        def invalid_json(): raise ValueError("not JSON")
        return SimpleNamespace(status_code=503,json=invalid_json)
    session.post=post
    provider=GranitePhysicalProvider(config,model_digest="d",session=session)
    with pytest.raises(ProviderFailure) as failure: provider.invoke(physical())
    assert failure.value.error_type=="OllamaHTTP503"
    assert provider.last_diagnostic["http_status"]==503
    assert provider.last_diagnostic["response"] is None


def sample(ram=6*GIB, page=GIB):
    return dict(ram_total_bytes=16*GIB, ram_available_bytes=ram, pagefile_used_bytes=page,
        gpu_used_bytes=None, gpu_total_bytes=None, loaded_models=[], missing={"gpu":"unavailable_test"})


@pytest.mark.parametrize("measurement,reason", [(sample(ram=GIB), "available_ram_below_2gib"),
    (sample(page=3*GIB+1), "pagefile_growth_above_2gib")])
def test_sustained_resource_gate_requires_continuous_60_seconds(measurement, reason):
    clock = [0.]
    gate = SustainedResourceGate(sample(), clock=lambda:clock[0])
    assert gate.observe(measurement) is None
    clock[0] = 59.9
    assert gate.observe(measurement) is None
    clock[0] = 60
    assert gate.observe(measurement) == reason
    assert gate.observe(sample()) == reason


def test_transient_breach_resets_and_thresholds_are_strict():
    clock = [0]
    gate = SustainedResourceGate(sample(), clock=lambda:clock[0])
    gate.observe(sample(ram=GIB))
    clock[0] = 59
    assert gate.observe(sample(ram=2*GIB, page=3*GIB)) is None
    clock[0] = 60
    gate.observe(sample(ram=GIB))
    clock[0] = 100
    assert gate.observe(sample(ram=GIB)) is None


@pytest.mark.parametrize("baseline", [sample(ram=None), sample(page=None), sample(ram=GIB)])
def test_missing_or_unsafe_baseline_is_not_zero(baseline):
    with pytest.raises(ValueError): SustainedResourceGate(baseline)


def test_monitor_missing_telemetry_cancels_and_retains_peaks(tmp_path):
    cancel, aborted = Event(), []
    monitor = ResourceMonitor(lambda:sample(), EventJournal(tmp_path/"telemetry", "test"), cancel, abort=lambda:aborted.append(True))
    monitor._record(sample(page=None))
    result = monitor.close()
    assert cancel.is_set() and aborted and result["reason"] == "required_resource_telemetry_missing"
    assert result["peak_gpu_used_bytes"] is None and result["peak_pagefile_delta_bytes"] == 0


def test_owned_server_refuses_reused_pid_and_does_not_unlock(tmp_path, monkeypatch):
    import slm.owned_ollama as module
    path = tmp_path/"owner.json"
    path.write_text(json.dumps(dict(endpoint="http://127.0.0.1:11434", num_parallel=1,max_loaded_models=1,
        context_length=32768,pid=12,started_at_utc="2026-09-06T20:00:00Z")))
    calls=[]
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout=json.dumps(dict(Name="ollama.exe", CommandLine="ollama serve",
            CreatedUtc="2026-09-06T21:00:00Z")))
    monkeypatch.setattr(module,"hidden_run",run)
    owner=OwnedOllama(path,journal=EventJournal(tmp_path/"journal","test"),endpoint="http://127.0.0.1:11434")
    result=owner.stop()
    assert result["status"] == "termination_unconfirmed" and not result["lease_released"]
    assert len(calls)==1 and calls[0][0]!="taskkill"


class FakeOwner:
    def __init__(self, *args, **kwargs): self.proof=None
    def validate(self): pass
    def stop(self):
        self.proof={"status":"test_abort_only", "lease_released":False}
        return self.proof


def make_runner(tmp_path, monkeypatch, config, context, *, before=None, probe=None):
    import slm.granite_preflight as module
    monkeypatch.setattr(module,"load_context_tokenizer",lambda *args:object())
    monkeypatch.setattr(module,"inspect_ollama",lambda config:dict(loaded_models=[dict(context_length=32768)]))
    provenance=tmp_path/"provenance.json"
    provenance.write_text('{}')
    providers=[]
    def factory(config, *, model_digest, context_tokenizer=None):
        provider=SyntheticProvider(context, before=before)
        provider.provider="local"
        provider.model_exact_id=f"{config.model_alias}@{model_digest}"
        original=provider.invoke
        def invoke(request):
            if request.schema is ProbeAck and before is None:
                return PhysicalResponse('{"ok":true}',dict(prompt_eval_count=31000,
                    context_probe_expected_tokens=31000,context_probe_token_count_delta=0),31000,4,31004)
            return original(request)
        provider.invoke=invoke
        providers.append(provider)
        return provider
    runner=GranitePreflight(config=config, context=context, output_dir=tmp_path/"run", owner_path="unused",
        tokenizer_path="unused",tokenizer_provenance=provenance,probe=probe or (lambda:sample()),
        metadata={"model_digest":"test-digest"},provider_factory=factory,owner_factory=FakeOwner)
    runner.lease_dir=tmp_path/"leases"
    return runner, providers


def test_all_phases_and_complete_common_graph_offline(tmp_path, monkeypatch, config, context):
    # Larger *offline test* envelope is never written to the real candidate config.
    cfg=config.model_copy(update=dict(max_total_tokens=20_000_000,max_prompt_chars=1_000_000))
    runner, providers=make_runner(tmp_path,monkeypatch,cfg,context)
    result=runner.run()
    assert result["status"]=="go",result
    assert all(v["status"]=="passed" for v in result["phases"].values())
    assert len(providers[-1].calls)==18
    assert len(result["phases"]["smoke"]["result"]["reports"])==4
    assert result["formal_runs_started"]==0


def test_warmup_timeout_skips_dependents_and_quarantines_lease(tmp_path,monkeypatch,config,context):
    def slow(*args):
        time.sleep(.1)
        return PhysicalResponse('{"ok":true}', {}, 1,1,2)
    cfg=config.model_copy(update={"node_seconds":.025,"request_seconds":.025})
    runner, _=make_runner(tmp_path,monkeypatch,cfg,context,before=slow)
    result=runner.run()
    assert result["status"]=="no_go" and result["phases"]["warmup"]["status"]=="failed"
    assert all(result["phases"][p]["status"]=="not_run" for p in ("context","components","smoke"))
    assert result["server_stop"]["status"]=="test_abort_only"
    assert list(runner.lease_dir.glob("*.lease.json"))
    time.sleep(.11)
    assert list(runner.lease_dir.glob("*.lease.json"))


def test_partial_response_failure_is_durable_and_blocks_dependents(tmp_path,monkeypatch,config,context):
    raw=dict(model=config.model_alias,message={"content":"{\n"},done=False)
    def incomplete(request,index):
        providers[0].last_diagnostic=dict(http_status=200,response=raw,endpoint="/api/chat")
        raise ProviderFailure("OllamaMissingCompletion",request_finished=False)
    runner,providers=make_runner(tmp_path,monkeypatch,config,context,before=incomplete)
    result=runner.run()
    assert result["status"]=="no_go" and result["model_calls"]==1
    assert result["phases"]["warmup"]["error_type"]=="OllamaMissingCompletion"
    events=replay_events(tmp_path/"run/warmup/events.jsonl")["events"]
    diagnostics=[e["payload"] for e in events if e["kind"]=="native_provider_diagnostic"]
    assert diagnostics==[dict(http_status=200,response=raw,endpoint="/api/chat")]
    assert result["phases"]["smoke"]["status"]=="not_run"
    assert list(runner.lease_dir.glob("*.lease.json"))


def test_initialization_failure_is_durable_and_calls_no_model(tmp_path,monkeypatch,config,context):
    with pytest.raises(ValueError):
        make_runner(tmp_path,monkeypatch,config,context,probe=lambda:sample(page=None))
    result=json.loads((tmp_path/"run/result.json").read_text())
    assert result["model_calls"]==0 and result["status"]=="no_go"
    events=replay_events(tmp_path/"run/events.jsonl")["events"]
    assert any(e["kind"]=="resource_baseline" and e["payload"]["pagefile_used_bytes"] is None for e in events)


def test_writer_probe_is_exact_common_first_batch(context):
    research=context.accept("research",synthetic_artifact(context,"research",version=1,inputs={}))
    strategy=context.accept("strategy",synthetic_artifact(context,"strategy",version=1,inputs={}),upstream=(research,))
    finance=context.accept("finance",synthetic_artifact(context,"finance",version=1,inputs={}),upstream=(research,strategy))
    captured=[]
    class Capture:
        def generate_structured_once(self,prompt,schema,**kwargs):
            captured.append((prompt,schema))
            raise RuntimeError("capture only")
    with pytest.raises(RuntimeError):
        ContractGenerator(Capture()).generate(context,"writer",upstream=(research,strategy,finance))
    from workflow.llm_client import schema_cardinality_contract
    from workflow.generation_constraints import financial_reference_contract
    from workflow.two_stage_generation import BODY_INSTRUCTION
    assert captured[0][0] == (writer_probe_prompt(context,(research,strategy,finance))+"\n\n"+BODY_INSTRUCTION+"\n\n"+
        schema_enum_contract(captured[0][1])+"\n\n"+schema_cardinality_contract(captured[0][1])+"\n\n"+
        financial_reference_contract(context.finance.value_ids))


def test_context_tokenizer_hash_rejects_changed_bytes(tmp_path):
    path=tmp_path/"tokenizer.json"
    path.write_text('{}')
    provenance=tmp_path/"provenance.json"
    provenance.write_text(json.dumps(dict(model="ibm-granite/granite-4.0-h-micro",tokenizer_sha256="wrong")))
    with pytest.raises(ValueError,match="hash"):
        load_context_tokenizer(path,provenance)


@pytest.mark.parametrize("mutation", ["source", "quant", "count", "context", "other_loaded"])
def test_metadata_rejects_wrong_model_or_implicit_context(config, mutation):
    show=dict(details=dict(parent_model=config.source_model, quantization_level="Q4_K_M",family="granitehybrid"),
        model_info={"general.parameter_count":3191396096},parameters="num_ctx 32768\ntemperature 0")
    loaded=[]
    if mutation=="source": show["details"]["parent_model"]="another-model"
    if mutation=="quant": show["details"]["quantization_level"]="Q8_0"
    if mutation=="count": show["model_info"]["general.parameter_count"]=1_000_000_000
    if mutation=="context": show["parameters"]="temperature 0"
    if mutation=="other_loaded": loaded=[{"name":"other-model"}]
    session=Session(show)
    def get(url,**kwargs):
        data={"/api/version":{"version":"test"},"/api/tags":{"models":[dict(name=config.model_alias,digest="d")]},
              "/api/ps":{"models":loaded}}[url.removeprefix(config.endpoint)]
        return SimpleNamespace(json=lambda:data,raise_for_status=lambda:None)
    session.get=get
    with pytest.raises(ValueError): inspect_ollama(config,session=session)


@pytest.mark.parametrize("listener_pids", [[12],12])
def test_owned_server_terminates_only_verified_tree_once(tmp_path,monkeypatch,listener_pids):
    import slm.owned_ollama as module
    path=tmp_path/"owner.json"
    path.write_text(json.dumps(dict(endpoint="http://127.0.0.1:11434", num_parallel=1,max_loaded_models=1,
        context_length=32768,pid=12,started_at_utc="2026-09-06T20:00:00Z")))
    process=dict(Name="ollama.exe",CommandLine="ollama serve",CreatedUtc="2026-09-06T20:00:00Z",ListenerPids=listener_pids)
    replies=iter([json.dumps(process),json.dumps(process),"terminated",""])
    calls=[]
    def run(args,**kwargs):
        calls.append(args)
        return SimpleNamespace(stdout=next(replies))
    monkeypatch.setattr(module,"hidden_run",run)
    owner=OwnedOllama(path,journal=EventJournal(tmp_path/"journal","test"),endpoint="http://127.0.0.1:11434")
    owner.validate()
    assert owner.stop()["status"]=="owned_process_tree_terminated"
    owner.stop()
    assert len(calls)==4 and calls[2]==["taskkill","/PID","12","/T","/F"]


def test_absent_owned_process_is_a_clear_startup_failure():
    with pytest.raises(ValueError,match="no longer running"):
        OwnedOllama._verify_process(SimpleNamespace(),None)


def test_structure_failure_keeps_independent_probes_but_blocks_smoke(tmp_path,monkeypatch,config,context):
    def malformed(request,index): return PhysicalResponse('{}',{},1,1,2)
    runner,_=make_runner(tmp_path,monkeypatch,config,context,before=malformed)
    result=runner.run("components")
    assert result["status"]=="no_go"
    assert all(v["status"]=="failed" for v in result["phases"]["components"]["probes"].values())
    assert result["model_calls"]==8  # one repair each, no hidden repair/retry loop


def test_context_acceptance_failure_blocks_dependent_work(tmp_path,monkeypatch,config,context):
    import slm.granite_preflight as module
    runner,_=make_runner(tmp_path,monkeypatch,config,context)
    monkeypatch.setattr(module,"inspect_ollama",lambda config:dict(loaded_models=[dict(context_length=4096)]))
    result=runner.run()
    assert result["status"]=="no_go" and not result["phases"]["context"]["allocation_verified"]
    assert result["phases"]["components"]["status"]=="not_run" and result["phases"]["smoke"]["status"]=="not_run"


@pytest.mark.parametrize('vram',[0,100,None])
def test_cpu_context_requires_observed_zero_vram(tmp_path,monkeypatch,config,context,vram):
    import slm.granite_preflight as module
    cfg=config.model_copy(update=dict(gpu_layers=0,context_probe_mode='chat'))
    runner,_=make_runner(tmp_path,monkeypatch,cfg,context)
    monkeypatch.setattr(module,'inspect_ollama',lambda _:dict(loaded_models=[dict(context_length=32768,size_vram=vram)]))
    result=runner.run('context')
    assert result['phases']['context']['cpu_only_verified']==(vram==0)
    assert (result['status']=='phase_passed')==(vram==0)
