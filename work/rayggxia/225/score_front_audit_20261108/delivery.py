from pathlib import Path
import hashlib,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PROJECT=ROOT.parents[1]
FORMAL=ROOT/'architecture_tlm/module_handoff/attention_score_front_compare_20261108'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=True)+'\n').encode())
for row in json.loads((FORMAL/'SOURCE_INDEX.json').read_bytes())['sources'].values():assert sha(Path(row['path']))==row['sha256']
for p in FORMAL.iterdir():assert p.read_bytes()==(PROJECT/p.relative_to(ROOT)).read_bytes()
(HERE/'HANDOFF.md').write_bytes('''# Attention分数前端成本审计交接

2026-11-08，Issue225 / PR249，rayggxia，task/225-tlm-unified250-20261107，base task/225-norm-stream-20261106；关联Issue198/PR199，只读owner源码/结果，不接管或修改其文件。

用户要求把S12先量化与FP32先差的功耗面积区别写一份文件给其他对话。正式入口architecture_tlm/module_handoff/attention_score_front_compare_20261108/HANDOFF_ZH.md；13来源SHA、机读事实与单位核验随同目录，根阅读镜像同字节。

结论：A第二步只是整数饱和，不是二次浮点转换。已有S12独立SS100前布局面积.015050059mm²、.166291667nJ/query/65拍；不含LUT/随机/输入SRAM。B是宏，并非已测FP32前端；FP32比较不能套ADD，FP32差→U8可做融合专用实现但需核数值等价。两者存储组织/流水/原准备资源/多份proxy价卡/采样轨迹还未公平拆清。当前同宽前端预算复用不能证明同成本。文档给出对方最小配对工作，无新硬件/模型仿真。

仅分析建议保留S12证据参考，用户未在本轮授权切换默认。本轮没有改当前100/250或28nm准备profile、38629485/38631668冻结快照/健康任务；没有新TLM/RTL/PT/GPU/PPL，不新增虚构电路run。未来若写新RTL/PT交由Attention任务，台账登记对应实测边界。

公开范围：正式四文件、本交接、构建/交付辅助和本人STATUS；私有源码/报告/PDK仅留SHA索引。发布/回读以PUBLICATION.json为准，PR249保持draft/open/unmerged，Issue225/PR199同步关联；Projects待维护者同步。本地Git HEAD可能落后连接器发布的远端头，先核PR249，禁止reset或覆盖其它staging。
'''.encode())
p=ROOT/'progress/rayggxia/STATUS.md';p.write_bytes(('''## 2026-11-08 Issue225：Attention分数前端成本审计已整理

用户要求给其他对话的文件已写：module_handoff/attention_score_front_compare_20261108/HANDOFF_ZH.md。关键：S12后整数差转U8只是clip；已有A的SS100独立PPA为.015050059mm²/.166291667nJ/65拍；B仍宏价，比较／减法／专用转换／存储组织／旧准备资源／代理价卡未配对。FP32差→U8可专用融合，不能直接断言需完整FPU或固定面积倍率。四正式文件、13来源SHA及单位校验通过，根同字节镜像；发布见本任务PUBLICATION。

没有改默认/冻结任务/owner源码，没有新TLM/RTL/PT/GPU/PPL；保留S12为参考是建议，非用户已授权切回。Issue225/PR249接续，关联198/199；PR不合并，Projects待维护者同步。

''').encode()+p.read_bytes())
canonical=PROJECT/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=PROJECT/'PROJECT_MEMORY_ZH.md'
raw=canonical.read_bytes();assert raw==mirror.read_bytes()
note='''## 2026-11-08：S12与FP32 max-gap电路成本审计

用户要求写文件给其他对话，Issue225/PR249沿用，关联198/199。入口architecture_tlm/module_handoff/attention_score_front_compare_20261108/HANDOFF_ZH.md，13来源SHA/机读事实/单位校验。A为FP32→S12/F4→整数max/13bit差→clipU8，第二步不再FP量化；S12独立SS100面积.015050059mm²/gross.166291667nJ/query/65拍已有DC/STA/PT，不含LUT/RNG/输入SRAM，极小setup裕量和告警保留。B最新TLM仍FP32max-gap宏，4ADD面积组合约.0481955mm²/实例、算术价约1.61985nJ/query只是代理，不是实测对比倍率。有限FP32比较不等于ADD；差值转U8可做融合单元，不必通用FPU，但须区分FP32中间舍入和精确差一次舍入。

真实未分清：A本地192B DFF与B512B FP32 SRAM/两遍1024B读、流式max融合机会、共同128B阈值、流水/ICG/回压、旧sampler准备资源、同wide_front_reserve预算复用及不同整机proxy价卡、旧S12采样轨迹与新阈值非同一闭环。不能因旧／新总面积能量相近称B免费，也不能将gross/idle一般账本误说全重复。短PPL13.9546→13.7394只1024目标，完整PPL不能继承。

本轮仅分析/文档，建议保留A证据参考不等于用户授权切回；没有改默认、28准备、owner/冻结源或健康任务，没有新仿真/电路run。发布看work/rayggxia/225/score_front_audit_20261108/PUBLICATION.json，PR待审不合并，Projects待同步。

---

'''.encode()
assert note not in raw and canonical.read_bytes()==raw and mirror.read_bytes()==raw
canonical.write_bytes(note+raw);mirror.write_bytes(note+raw)
paths=list(FORMAL.iterdir())+[HERE/'HANDOFF.md',HERE/'build.py',HERE/'delivery.py',p]
files=[dict(path=p.relative_to(ROOT).as_posix(),content=p.read_bytes().decode(),sha256=sha(p)) for p in paths]
save(HERE/'PUBLIC_FILES.json',files)
subprocess.run(['git','-c','core.autocrlf=false','add','--sparse','--']+[x['path'] for x in files],cwd=ROOT,check=True)
for x in files:assert hashlib.sha256(subprocess.check_output(['git','show',':'+x['path']],cwd=ROOT)).hexdigest()==x['sha256']
subprocess.run(['git','-c','core.whitespace=cr-at-eol,-blank-at-eof','diff','--cached','--check'],cwd=ROOT,check=True)
print(json.dumps(dict(public_files=len(files),sources_verified=13,root_reading_mirror=True,no_simulation=True)))
