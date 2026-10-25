import csv
import hashlib
import io
import json
from pathlib import Path

root=Path(__file__).resolve().parents[4]
ws=Path('C:/Users/86134/Documents/a_P_BIT')
work=Path(__file__).resolve().parent
def text(p,s):p.write_bytes(s.encode('utf8'))
def prepend(p,s):
    old=p.read_bytes()
    if s.encode('utf8') not in old:p.write_bytes(s.encode('utf8')+old)

entry='''## 2026-10-25 Issue95：理想读出20k的定时分层质量

用户同意等待实际比较器数据时，先用三条理想阈值读出做基线。task/95-ideal-quality-20261025，tmp/rng-ideal-quality-issue95-20261025，base d6d33995754fcdcea99286e4ce43f91647aa231a；执行本地提交 bdbab3e38ff56e267783af9ac327dbba67a0e169，冻结5文件SHA。已有ideal_and_old_20000_v1三seed32003/32009/32027，各20000bit、1us，仍带旧比较器负载；无新Spectre。216主例+9重复种子对照全完成，每端点4096帧；四个固定5000bit冷启动段，不是12独立物理轨迹，也不触发默认1e8拍/1s周期换种。

理想原始rho1 −0.0037～0.0101，V128为1.208～1.596，不能凭lag1认定IID。VN理想保留约25%；旧比较器VN保留约12%，仍负rho1 −0.236～−0.187。分发逐bit保持，仅截断包末尾；LFSR每端32状态bit，Bivium192总线bit→177状态bit/15丢弃。理想直通双端首次请求63.03us/383.08us，VN为213.03～275.03us/1461.08～1617.08us。GF64前四路q128 XOR恒0，理想直通q4恰一路命中0.685～0.706，对比IID约0.371；Bivium q13约0.362～0.396，对比约0.377。较好种子不消除固定联合关系，PRNG不增加物理熵。

6单测、8956项可复现审计、独立只读复核及1280/390浏览器检查通过。归档project_archives/rng_ideal_quality_20261025（225NPZ、完整JSON、执行bundle、源码zip）；中央run rng-ideal-quality-95-20261025，仅DESIGN_PROOF/PPA未知。报告architecture_tlm/random_service/quality/results/ideal_20261025/REPORT.html，本机远端上传/rng_ideal_quality_20261025.html。HANDOFF/PUBLICATION位于work/rayggxia/95/ideal_quality_20261025；发布状态以回执为准，未自动合并/关闭Issue95。当前在仿真的物理任务Issue184/PR185及他人Issue152只读未改；Projects待有权限者同步。

'''
prepend(root/'PROJECT_MEMORY_ZH.md',entry)
canonical=ws/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
mirror=ws/'PROJECT_MEMORY_ZH.md'
assert canonical.read_bytes()==mirror.read_bytes(), 'reconcile concurrent memory edits first'
prepend(canonical,entry)
mirror.write_bytes(canonical.read_bytes())
prepend(root/'progress/rayggxia/STATUS.md',entry)
lead='''2026-10-25 新基线：[理想读出20k的定时分层报告](results/ideal_20261025/REPORT.html)，[逐案例摘要](results/ideal_20261025/SUMMARY.json)，[输入/配置/归档索引](results/ideal_20261025/ARCHIVE_INDEX.json)。225案例、6单测、8956项核验通过；1us原始时序、四个固定冷启动窗口、不触发默认1s周期换种。执行源/输入分别按SHA冻结。理想输入不消除GF64的固定联合相关；无新模拟电路、RTL、PPA或LLM实验。旧189案例按原协议保留。

复现新协议（输出目录必须全新，Python>=3.10 + NumPy；绘图另需matplotlib）：

```powershell
python -m unittest architecture_tlm.random_service.quality.test_ideal_readout -v
python -m architecture_tlm.random_service.quality.ideal_readout --input <ideal_and_old_20000_v1目录> --out <新结果目录> --raw-out <新NPZ目录>
python -m architecture_tlm.random_service.quality.audit_ideal <新结果目录>
python architecture_tlm/random_service/quality/report_ideal.py <新结果目录>
```

'''
prepend(root/'architecture_tlm/random_service/quality/README_ZH.md',lead)
text(work/'HANDOFF.md',entry+'''恢复操作：

1. 先读最新Issue95/关联PR、PUBLICATION.json、STATUS和根记忆。PR134是已合并旧阶段，不能更新其旧分支；本轮独立task/95-ideal-quality-20261025，目标TLM集成分支。
2. 报告、源manifest及结果索引在quality/results/ideal_20261025；大RESULTS被gitignore，但稳定归档已有同字节文件，225NPZ也在稳定归档。input SHA由INPUT_MANIFEST绑定，物理原始包仍归原任务。
3. 原模型/backends/映射未改。本地执行bdbab3e通过execution.bundle保留（依赖base d6）；增强测试、审计、图文为后处理。运行命令及测试日志见VALIDATION.json/tests.log，源zip及SHA清单见SOURCE_PACKAGE_MANIFEST。
4. 不覆盖既有结果；新数据用新输出目录。不要循环有限记录、从MID筛选好bit、自动补充OS种子或把四窗口称作实际1s周期换种。
5. root中央台账比本分支含更多并行记录；本次只新增本run、保留原catalog所有ID并render，不能以本分支整目录覆盖root。根记忆只在Issue28 canonical追加本项后同步镜像，保留其他未提交内容。

疑点/后续：

- 物理源健康检测/调理、CDC尚无本次RTL实现；RandomNetwork的qualified接口是条件合同，不是熵检测结果。
- VN对相关输入不保证IID；实际比较器、并行空间相关、低频漂移仍等数据，不据当前结果定最终调理器。
- 一亿拍换种未实际触发；不使用旧1024拍加速协议替代（真实低速采种下可能导致同步端点饥饿）。
- GF64是否适合 конкрет消费者需看联合事件；本轮toy探针不能代替FFN/Attention/LLM质量。
- 本任务没有新RTL/EDA/Slurm/GPU作业。模拟器仅操作计数，面积/功耗未知。
- 本轮后处理增强测试曾因Counter字典显式0键与缺省0键格式不同失败，改为语义计数/内部状态对照后6项通过；执行源码未变。初次沙箱Edge启动受限，独立无头配置获工具批准后检查通过。

交付时保留最小PR待审目录，原始结果已稳定归档；只有本任务合并后再按恢复索引回收，不能删除其他物理任务。Projects连接器无已验证的写入能力，待有权限维护者同步。
'''.replace('конкрет','具体'))
text(work/'.gitignore','preview-*.png\nregistry_record.json\n')
for reg in (root/'digital_circuit_simulation_registry',ws/'digital_circuit_simulation_registry'):
    note='\n2026-10-25 Issue95新增 `rng-ideal-quality-95-20261025`：理想/旧比较器20k定时回放225例、6测试/8956核验；DESIGN_PROOF，无新RTL/PPA。归档和限制见对应record；并行记录保持，不能整目录覆盖其他任务增量。\n'
    p=reg/'README_ZH.md'
    if note not in p.read_text(encoding='utf8'):p.write_bytes(p.read_bytes()+note.encode('utf8'))
    p=reg/'archive_inventory.csv'
    existing=list(csv.DictReader(p.open(encoding='utf8',newline='')))
    for name in ('sources.zip','execution.bundle'):
        f=ws/'project_archives/rng_ideal_quality_20261025'/name
        if not any(x['path']==f.as_posix() for x in existing):
            buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=list(existing[0]),lineterminator='\n')
            writer.writerow(dict(path=f.as_posix(),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),
                linked_records='rng-ideal-quality-95-20261025',review_state='sha_verified_functional_only',
                note='本轮冻结执行源与后处理；无新PPA；完整NPZ见run索引'))
            with p.open('ab') as out:out.write(buf.getvalue().encode('utf8'))
print('metadata updated without replacing parallel records')
