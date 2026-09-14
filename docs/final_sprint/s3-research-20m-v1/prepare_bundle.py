from pathlib import Path
import hashlib, json, shutil
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'.slm-claim-id-fix-stage'
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
PRIOR=REPO/'docs/final_sprint/s3-90m-fix-v2'
for name in ('freeze_bundle.py','install_bundle.py','history_inventory.py','cleanup_owned.py','Invoke-RecoveryTrial.ps1'):
    path=ROOT/name
    if path.exists(): raise RuntimeError('Preserve existing helper: '+name)
    text=(OLD/name).read_text(encoding='utf-8-sig').replace('s3-90m-fix-v2','s3-research-20m-v1')
    path.write_text(text.replace('trial_runner.py','research_runner.py'),encoding='utf-8')
shutil.copytree(OLD/'support',ROOT/'support',ignore=shutil.ignore_patterns('__pycache__'))
config=json.loads((PRIOR/'trial_config.json').read_text(encoding='utf-8-sig'))
config.update(model_config_version='granite-h-micro-cpu-research-20m-v1',run_seconds=1200.,node_seconds=1200.,request_seconds=1200.)
(ROOT/'trial_config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
record=dict(scope='ai_education_research_20m',approved=True,
    user_instruction='现在，我需要你简化 research 的输出，将其时长控制在20分钟之内',
    interpretation='Implement shared concise Research; validate only its generated artifact within 1200 seconds using the remainder of the already approved independent 90-minute pool. No complete D restart.',
    approved_limits={key:config[key] for key in ('run_seconds','node_seconds','request_seconds','max_output_tokens','max_requests','max_total_tokens','max_prompt_chars')},
    research_effective_output_caps={'body':640,'grounding':2304,'single':2304},
    parent_authorization_path=str(PRIOR/'authorization.json'),
    parent_authorization_sha256=hashlib.sha256((PRIOR/'authorization.json').read_bytes()).hexdigest(),
    expected_model_digest='eec81a822241037c5d8e47a870b3d26423bfa1b010e02fcdf1b5f9f2de5c3b2b',
    expected_ollama_version='0.33.2',formal_eligible=False)
(ROOT/'authorization.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
result=PRIOR/'run_01/probe/result.json'
(ROOT/'budget_carryover.json').write_text(json.dumps(dict(result_path=str(result),
    sha256=hashlib.sha256(result.read_bytes()).hexdigest()),indent=2),encoding='utf-8')
(ROOT/'PREVIOUS_STATUS.md').write_bytes((REPO/'docs/final_sprint_status.md').read_bytes())
shutil.copy2(PRIOR/'authorization.json',ROOT/'parent_authorization.json')
shutil.copy2(PRIOR/'validation/research_simplification_review.md',ROOT/'validation/research_simplification_review.md')
print('Research-only setup ready; previous pool remains charged; no inference.')
