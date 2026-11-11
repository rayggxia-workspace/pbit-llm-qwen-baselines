from pathlib import Path
import json,hashlib,ast
H=Path(__file__).resolve().parent;ROOT=H.parents[3];WS=ROOT.parents[1];D=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump=lambda p,x:p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
r=json.loads((D/'SRAM_MIXED34_VALIDATION_20261109.json').read_bytes());assert r['status'].startswith('PASS_')
note='''## 2026-11-09 28nm混合宏默认：本地完成，待本次PR同步

Issue225/PR249，rayggxia；分支task/225-tlm-unified250-20261107，PR base task/225-norm-stream-20261106；工作目录tmp/tlm-unified250-issue225-20261107，恢复前确认PR最新head。用户决定30×8KiB＋4×4KiB CIM容量份额；两频832KiB总计30×8KiB＋148×4KiB/178真实宏，前端106共享端口、Attention72，不是独占34端口测量。55nm保持。

本机四case完成封存，250三核两层+384head 2.208844→2.211800ms(+.133826%)；500两核一层+384head .997122→.997290ms(+.016848%)。53248物理字无别名，真实端口、排空、核帧/转换/尺度/算术/采样/外存字节与地址SHA校验通过。首次混合未封存energy断言失败保留，确认binary64累计误差约3.1e-10；按N*epsilon界修复审计，调度不变。

SRAM宏2.471065→2.278958mm²(-7.77%)，条件250/500面积6.566340/6.592880mm²；S2用库面积时序漏电、动态S0_PT＋CLK库差估计，局部SRAM能量约+2.4%，不是新S2PT。新默认执行字段匹配冻结混合配置，四个说明字段纠正；208全4K/960参考保留。完整token、新PPL、nativeLPDDR、芯片PPA未重做，不用旧960时间改标签。无健康服务器任务变动。

正式process_28nm/SRAM_MIXED34_VALIDATION_20261109_ZH.md/json与DEFAULT_SRAM832；原件归档project_archives/mixed34_issue225_20261109/finite_pairs_and_failed_audit.zip/SHA见本work/ARCHIVE_INDEX.json。当前本地完成，发布结果以本work/PUBLICATION.json为准，PR待审未合并；Projects无已核实写接口，待维护者同步。下一步如需完整832 token，使用新WHOLE_CONFIG与独立输出；复现局部测试用归档冻结PLAN命令，不重写旧快照。

---

'''
status=ROOT/'progress/rayggxia/STATUS.md';old=status.read_bytes();status.write_bytes(note.encode()+old)
handoff='''# 混合宏默认与有限bank验证交接

'''+note+'''本次命令：

`python -X utf8 -B work/rayggxia/225/mixed34_20261109/run_pairs.py --run-dir work/rayggxia/225/mixed34_20261109/revision2 --reuse-base work/rayggxia/225/mixed34_20261109`

随后执行同目录collect.py、finalize.py。finalize是一次性验收/默认切换工具；证据已归档，不能覆写zip。run_pairs读取旧默认的冻结工具，在默认改为混合宏后不要直接重复；从zip恢复execution目录和冻结PLAN，改命令最后--out为新的绝对目录即可重放。

本次冻结六源码和两频绑定/旧默认的SHA见revision2/PLAN，源身份见机器报告sources；p250_base来自首次已封存快照，仅mixed_budget舍入审计发生变化。当前默认四个描述字段已更正S2为估价，执行参数不变。无需tokenizer/权重/语料：这是相同冻结事务地址的TLM验证，不是数值模型评测；Qwen形状、fixture/host manifest和seed已绑定。原ZIP不含工艺库。

首次失败日志和返回码保留；额外SRAM-only probe未完成并已停止，不作为结果或验收依据。全部本轮配对执行已结束，无新增Slurm作业。
'''
(H/'HANDOFF.md').write_bytes(handoff.encode())
root_handoff=ROOT/'work/rayggxia/225/HANDOFF.md'
assert not root_handoff.exists(),'preserve existing task root handoff'
root_handoff.write_bytes(('''# Issue225最新恢复入口

当前阶段：28nm832KiB混合宏默认，PR249待审；详见[mixed34交接](mixed34_20261109/HANDOFF.md)。持续任务此前的55nm250、统一时钟、DMA16KiB、SRAM表征与832容量回放交接保留在各有日期子目录；不要只依据早期默认恢复。正式配置以architecture_tlm/process_28nm/{250,500}MHz/WHOLE_CONFIG.json为准，55nm不变。开始或发布前核实最新Issue225/PR249、本人STATUS和本次PUBLICATION回执。
''').encode())
files=['candidate_sram.py','mixed_sram.py','whole_model.py','sram_characterization.py','whole_pricing.py','run_whole.py',
    '250MHz/WHOLE_CONFIG.json','500MHz/WHOLE_CONFIG.json',
    '250MHz/WHOLE_CONFIG_832_ALL4K_REFERENCE.json','500MHz/WHOLE_CONFIG_832_ALL4K_REFERENCE.json',
    'DEFAULT_SRAM832_20261109.json','DEFAULT_SRAM832_20261109_ZH.md',
    'SRAM_MIXED34_VALIDATION_20261109.json','SRAM_MIXED34_VALIDATION_20261109_ZH.md','README_ZH.md','WHOLE_MODEL_ZH.md']
paths=['architecture_tlm/process_28nm/'+n for n in files]
paths+=['architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md','progress/rayggxia/STATUS.md','work/rayggxia/225/HANDOFF.md']
paths+=['work/rayggxia/225/mixed34_20261109/'+n for n in ('run_pairs.py','collect.py','finalize.py','prepare_delivery.py','HANDOFF.md','ARCHIVE_INDEX.json')]
for path in paths:
    if path.startswith('architecture_tlm/'):
        target=WS/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/path).read_bytes())
        assert sha(target)==sha(ROOT/path)
payload=[]
for path in paths:
    p=ROOT/path
    if p.suffix=='.py':ast.parse(p.read_text(encoding='utf8'),filename=path)
    if p.suffix=='.json':json.loads(p.read_bytes())
    payload.append(dict(path=path,sha256=sha(p),content=p.read_text(encoding='utf8')))
dump(H/'PUBLIC_FILES.json',payload)
test=dict(status='PASS_MIXED_DEFAULT_DELIVERY',public_files=len(payload),same_byte_mirrors=True,
    four_completed_seals=True,physical_words_unique=53248,default_actual_macros=178,
    clocks=[250,500],new_PPA=False,scope='finite reference transaction replay,not PPL or fulltoken')
dump(H/'VALIDATION.json',test)
print(json.dumps(dict(**test,payload_bytes=(H/'PUBLIC_FILES.json').stat().st_size)))
