"""Prepare reviewable recovery helpers; never start inference or grant a budget."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / '.slm-90m-fix-stage'
REPO = Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
PRIOR = REPO / 'docs/final_sprint/s3-90m-fix-v1/run_01/probe/result.json'
for name in ('freeze_bundle.py', 'install_bundle.py', 'history_inventory.py', 'cleanup_owned.py',
             'Invoke-RecoveryTrial.ps1', 'trial_config.json'):
    destination = ROOT / name
    if destination.exists():
        raise RuntimeError('Preserve existing helper: ' + name)
    text = (OLD / name).read_text(encoding='utf-8-sig')
    destination.write_text(text.replace('s3-90m-fix-v1', 's3-90m-fix-v2'), encoding='utf-8')
shutil.copytree(OLD / 'support', ROOT / 'support', ignore=shutil.ignore_patterns('__pycache__'))
(ROOT / 'PREVIOUS_STATUS.md').write_bytes((REPO / 'docs/final_sprint_status.md').read_bytes())
(ROOT / 'prior_authorization.json').write_bytes((OLD / 'authorization.json').read_bytes())
(ROOT / 'budget_carryover.json').write_text(json.dumps(dict(result_path=str(PRIOR),
    sha256=hashlib.sha256(PRIOR.read_bytes()).hexdigest()), indent=2), encoding='utf-8')
config = json.loads((ROOT / 'trial_config.json').read_text())
config['model_config_version'] = 'granite-h-micro-cpu-90m-v2'
config.pop('cumulative_trial_seconds')
(ROOT / 'trial_config.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
record = dict(scope='ai_education_slm_independent_90m_validation', approved=False,
    approved_limits={key: config[key] for key in ('run_seconds', 'node_seconds', 'request_seconds',
        'max_output_tokens', 'max_requests', 'max_total_tokens', 'max_prompt_chars')},
    reason_pending='Old aggregate four-hour allowance has only 4206.517 seconds remaining. A fresh independent validation allowance needs explicit confirmation; old usage remains recorded.',
    expected_model_digest='eec81a822241037c5d8e47a870b3d26423bfa1b010e02fcdf1b5f9f2de5c3b2b',
    expected_ollama_version='0.33.2', formal_eligible=False)
(ROOT / 'authorization.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print('Prepared helpers and pending authorization; no model calls.')
