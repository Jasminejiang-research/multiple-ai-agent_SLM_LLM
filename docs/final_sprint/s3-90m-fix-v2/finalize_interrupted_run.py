from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, shutil
ROOT=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT=REPO/'docs/final_sprint/s3-90m-fix-v2'
def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
result=load(REPORT/'run_01/probe/result.json')
audit=load(ROOT/'validation/full_d_integrity_audit.json')
if result['complete_proposal_produced'] or result['resources']['reason']!='resource_observation_gap':
    raise RuntimeError('Unexpected result; review before writing handoff')
for row in load(REPORT/'history_inventory.json'):
    if hashlib.sha256((REPO/row['path']).read_bytes()).hexdigest()!=row['sha256']:
        raise RuntimeError('Historical file changed: '+row['path'])
for name in ('full_d_integrity_audit.json','research_body_fact_audit_v2.md','research_simplification_review.md'):
    shutil.copy2(ROOT/'validation'/name, REPORT/'validation'/name)
shutil.copy2(ROOT/'validation/audit_complete_d.py', REPORT/'validation/audit_complete_d.py')
handoff=REPORT/'HANDOFF.md'
backup=REPORT/'HANDOFF.before_real_result.md'
if backup.exists(): raise RuntimeError('Do not overwrite prior handoff')
shutil.copy2(handoff,backup)
header='''# 最新真实结果：用户手动中断，完整计划书未生成

用户明确说明本次测试由其手动中断，并要求下一步简化Research、控制在20分钟以内。
控制器在2048.078秒采样空档后按新规则停止，结果为resource_stopped；这不是一次90分钟超时，也不能归因于未知自动休眠或新的模型解码异常。

真实2请求，Research正文703输出tokens/196.359秒通过；声明阶段未返回完整响应，实际用量未知，保留85923-token预留。没有结构修复、Critic或后续角色。记录总3584.688秒（59分44.688秒，含用户中断和清理），完整D与完整计划均未完成。

已知实际4994tokens，预算扣记90917tokens；本次新90分钟池剩34请求/409083预算tokens/1815.312秒。全历史累计18请求/387486预算tokens/13778.171秒，旧消耗不退回、不混成这次新池的余额。

只读完整性审计passed但complete_d_verified=false。进程、监听端口和活动lease均为0；未知lease已逐字归档，防睡眠请求已释放。2943个历史文件hash未变。证据见run_01/probe/result.json、run_01/audit/INTERRUPTION.md、run_01/audit/external_cleanup.json和validation/full_d_integrity_audit.json。

Research正文另有年份和盈亏平衡表述错误，详见validation/research_body_fact_audit_v2.md；后续Critic未执行，不能声称已纠正。

下一入口是用户新授权的Research简化与≤1200秒组件验证（共享Research实现），使用本次获批池剩余额度；不自动重启完整D、Gemini或正式S5。15文件工程修复及782/132/26测试结果仍成立，但不能据此声称SLM完整计划成功。

---
以下是修复安装时的历史交接，预算/真实状态以本页开头为准。

'''
handoff.write_text(header+backup.read_text(encoding='utf-8'),encoding='utf-8')
status=REPO/'docs/final_sprint_status.md'
previous=status.read_bytes()
(REPORT/'STATUS.before_interruption_handoff.md').write_bytes(previous)
latest='''<!-- s3-90m-fix-v2 interrupted final -->
# 最新 S3：用户中断完整D，转入Research简化

用户确认手动中断并要求Research输出简化、时长≤20分钟。v2真实复测为2请求/3584.688秒含中断清理，Research正文703tokens/196.359秒通过；声明响应未完成，用量未知。2048.078秒采样空档触发resource_stopped，完整计划未生成、Critic及后续角色未执行。

已知4994tokens+85923未知预留=90917预算扣记；新90分钟池剩34请求/409083预算tokens/1815.312秒。全历史18请求/387486预算tokens/13778.171秒，后续正确区分新池余额与全历史，不退未知用量。

v2代码已通过782完整回归、132安装验证、26运行器验证；真实记录完整性审计passed，但完整D未通过。进程/端口/活动lease为0，2943旧历史文件未变。交接：docs/final_sprint/s3-90m-fix-v2/HANDOFF.md。

下一入口为用户已授权的Research≤1200秒简化组件验证。Gemini0、正式0/8，未自动重启完整D或下一工作包。

---
<!-- preserved previous records -->

'''
status.write_bytes(latest.encode('utf-8')+previous)
receipt=dict(recorded_at_utc=datetime.now(timezone.utc).isoformat(),status=result['status'],
    user_confirmed_manual_interruption=True,complete_plan=False,history_files_verified=2943,
    result_sha256=hashlib.sha256((REPORT/'run_01/probe/result.json').read_bytes()).hexdigest(),
    audit_sha256=hashlib.sha256((REPORT/'validation/full_d_integrity_audit.json').read_bytes()).hexdigest())
(REPORT/'final_run_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
shutil.copy2(Path(__file__), REPORT/Path(__file__).name)
print(json.dumps(receipt))
