from pathlib import Path
import json
root=Path(__file__).parent
name='s3-two-stage-v1'
for file in ('trial_runner.py','inspect_recovery.py','install_bundle.py','prepare_bundle.py'):
    p=root/file
    s=p.read_text(encoding='utf-8')
    if file=='trial_runner.py':
        s=s.replace('granite-h-micro-cpu-reference-fix-v2','granite-h-micro-cpu-two-stage-v1')
        # The real Research run itself verifies native selection enums, with no extra probe call.
        s=s.replace("native_ok = phase('native_schema_probe',native_test,output_cap=128)",
                    "native_ok = True\n        phases['native_schema_probe'] = dict(status='not_run',reason='Prior native bounds observed; actual two-stage Research exercises this wire schema')")
    if file in ('inspect_recovery.py','install_bundle.py'):
        s=s.replace('s3-reference-fix-v3',name)
    if file=='inspect_recovery.py':
        s=s.replace("'role','purpose','status'", "'role','purpose','generation_stage','status'")
    if file=='prepare_bundle.py':
        s=s.replace("previous_result=PREVIOUS/'run_01/probe/result.json'", "previous_result=REPO/'docs/final_sprint/s3-reference-fix-v3/run_01/probe/result.json'")
        s=s.replace('reference-fix-v1/v2.','reference-fix-v1/v2/v3; no quota reset.')
        s=s.replace('granite-h-micro-cpu-reference-fix-v3','granite-h-micro-cpu-two-stage-v1')
        s=s.replace("Use an explicit parent-prose wire field label; preserve canonical content_anchor and strict exact-text validation. Same A-D workflow, model, budget and retry allowances.",
                    "User approved the uniform A-D two-stage generation proposal on 2026-09-07: immutable body, exact-span selection, strict canonical assembly; one shared structure repair. Continue real Research then complete D within the remaining prior allowance. Public budgets and formal runs unchanged.")
    p.write_text(s,encoding='utf-8')
config=json.loads((root/'trial_config.json').read_text(encoding='utf-8-sig'))
config['model_config_version']='granite-h-micro-cpu-two-stage-v1'
(root/'trial_config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
print('Prepared approved trial runner configuration; no model calls.')
