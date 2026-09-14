from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT=REPO/'docs/final_sprint/s3-research-20m-v1'
for name in ('slm_amended.log',): shutil.copy2(ROOT/'validation'/name,REPORT/'validation'/name)
shutil.copy2(ROOT/'inspect_research.py',REPORT/'inspect_research.py')
note='''
## Final pre-probe amendment

Before any real call, removed generic nonempty financial-reference examples from brief Research body, grounding and repair feedback. All three use the empty allowed set; normalized score guidance remains. The amendment's previous files and manifests are preserved in `pre_probe_amendment/`.

Final source verification: `tests/` **613 passed, 25 deselected, 3 subtests, 274.37s**; `slm/tests/` **211 passed, 25.31s**, totaling **824 passed** across the full offline suite. The default pytest testpaths omits slm/tests, so both directories were explicitly covered. Final installed amendment **53 passed, 6.38s**, prior installed profile/deadline checks **83 passed, 9.13s**, installed runner **27 passed, 2.35s**. No model call occurred during these tests.
'''
for name in ('IMPLEMENTATION.md','HANDOFF.md'):
    path=REPORT/name
    path.write_text(path.read_text(encoding='utf-8')+note,encoding='utf-8')
status=REPO/'docs/final_sprint_status.md'
before=(REPORT/'STATUS_AT_PROBE_START.md').read_bytes()
if status.read_bytes()!=before: raise RuntimeError('Concurrent status change')
prefix='''<!-- s3-research-20m-v1 final-preflight -->
Research最终版本已消除非空财务引用示例冲突；完整离线824通过（主tests613 + slm/tests211），最终增量安装53通过。前阶段安装83及运行器27通过。准备执行唯一Research生成组件实测，最多1200秒，使用已批准90分钟池剩余额度。完整D/Critic尚未复测。以下保留先前准备和历史记录。

---
'''
status.write_bytes(prefix.encode('utf-8')+before)
(REPORT/'STATUS_AT_PROBE_START.md').write_bytes(status.read_bytes())
shutil.copy2(__file__,REPORT/'record_final_preflight.py')
print('Final preflight evidence recorded.')
