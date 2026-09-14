"""Prepare unique recovery records without touching the target installation."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json

ROOT = Path(__file__).resolve().parent
REPO = Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
PRIOR = REPO/'docs/final_sprint/s3-two-stage-v1/run_01/probe/result.json'

def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

config = load(ROOT/'trial_config.json')
config.update(model_config_version='granite-h-micro-cpu-90m-v1',
              node_seconds=5400.0, run_seconds=5400.0, request_seconds=5400.0,
              cumulative_trial_seconds=14400)
save(ROOT/'trial_config.json', config)
previous = load(ROOT/'authorization.json')
save(ROOT/'prior_authorization.json', previous)
record = dict(scope='ai_education_slm_nonformal_90m_recovery', approved=True,
    approved_limits={key:config[key] for key in ('run_seconds','node_seconds','request_seconds',
        'max_output_tokens','max_requests','max_total_tokens','max_prompt_chars','cumulative_trial_seconds')},
    user_instruction='我需要你为我诊断 - 定位 - 修复这个问题，我能够接受的LLM 和 SLM生成一份完整的计划书的所需最长时间长度为 1.5 hours - 注意：是各自1.5h，而不是加总 1.5h',
    interpretation='Each fresh plan has an independent 5400-second cap. This SLM recovery includes its Research prerequisite within that cap. Previous cumulative request/token/4h allowance remains charged; no reset or increase. No Gemini calls or formal S5 rows authorized by this helper.',
    approved_two_stage_scope='Uniform A-D body then grounded-claim selection; strict complete canonical contract and one shared structure repair remain.',
    previous_authorization_path='prior_authorization.json',
    recorded_at_utc=datetime.now(timezone.utc).isoformat(),
    expected_model_digest=previous['expected_model_digest'], expected_ollama_version=previous['expected_ollama_version'])
save(ROOT/'authorization.json', record)
save(ROOT/'budget_carryover.json', dict(result_path=str(PRIOR), sha256=hashlib.sha256(PRIOR.read_bytes()).hexdigest()))
for name in ('install_bundle.py','inspect_recovery.py','history_inventory.py','audit_assembly.py'):
    path=ROOT/name
    path.write_text(path.read_text(encoding='utf-8').replace('s3-two-stage-v1','s3-90m-fix-v1'),encoding='utf-8')
print('Prepared 90-minute recovery; previous request/token/time consumption retained.')
