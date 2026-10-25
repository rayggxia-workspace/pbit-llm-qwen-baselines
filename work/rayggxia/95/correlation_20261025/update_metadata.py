import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];WS=Path('C:/Users/86134/Documents/a_P_BIT');WORK=Path(__file__).resolve().parent
ARC=WS/'project_archives/rng_correlation_20261025';R=ROOT/'architecture_tlm/random_service/quality/results/correlation_20261025'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def prepend(p,s):
    old=p.read_bytes()
    if s.encode('utf8') not in old:p.write_bytes(s.encode('utf8')+old)
entry='''## 2026-10-25 Issue95：全路时间／空间相关长流已完成

用户要求具体数据，接续同PR188/分支task/95-ideal-quality-20261025、tmp/rng-ideal-quality-issue95-20261025。执行源2dd9ec33fa321174f3891b0cd684bc5aac4b589a，7执行文件及本机C++二进制SHA冻结。已有三条Spectre理想阈值序列各20k/1us，raw/VN两路径、三后端、两个实例；18物理播种案例+18同形状PCG64统计对照，每路连续131072帧，100MHz约1.31072ms。只按需消费启动种子前缀，不把全20k都说成驱动输出；默认1s换种未触发。没有同时物理阵列通道，物理空间相关留空，不能把三个noise seed充作空间lane。

R8、五阈值q4/13/64/128/192、8个bitplane测全部路；时间lag1..128/256/512/1024，R8/阈值空间lag0/1/2/4/8/16/32/64/128，bitplane空间仅同拍。两个实例分别1/64/20lane，区分实例内与实例间；504组观测、3024峰值记录、17124432相关系数，具体路号/lag及短窗T8..128方差/MSE全部保留。

q128/raw三个seed总体max|rho|：LFSR时间.010121/同拍跨实例.003200/错拍.006666；GF64时间.012355/同拍.010972/错拍.013372；Bivium时间.010807/同拍.009977/错拍.012212。不同测试对数不可据max直接排名；同形状IID对照已实跑。GF64四路XOR仍恒0，稀疏命中约.69而IID约.370780；Bivium对应q13接近.377306参考。物理种子改善不消除固定联合结构。

5新增单测、22524运行时核验、6122归档/矩阵审计通过；18案例前4096帧逐字对上轮Python原件，C++中段/尾段/状态另验证。1440/390浏览器和下载链接检查通过。新报告远端上传/rng_correlation_20261025.html；完整CSV包rng_correlation_20261025_tables.zip（63284726B）；原始流/矩阵/JSON在project_archives/rng_correlation_20261025。中央run rng-correlation-95-20261025，仅DESIGN_PROOF，PPA未知。恢复work/rayggxia/95/correlation_20261025/HANDOFF.md，实际远端增量发布见PUBLICATION.json。不改旧225例、Issue184/152模拟任务；无新Spectre/RTL/EDA/LLM；Projects待权限同步。

'''
prepend(ROOT/'PROJECT_MEMORY_ZH.md',entry);prepend(ROOT/'progress/rayggxia/STATUS.md',entry)
c=WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';m=WS/'PROJECT_MEMORY_ZH.md'
assert c.read_bytes()==m.read_bytes(),'concurrent memory edits need reconciliation'
prepend(c,entry);m.write_bytes(c.read_bytes())
readme='''2026-10-25追加全路长流：[精确时间／空间相关报告](results/correlation_20261025/REPORT.html)，[逐层数据](results/correlation_20261025/LAYERS.json)，[504组精确峰值CSV](results/correlation_20261025/PEAKS.csv)，[完整CSV／原始矩阵索引](results/correlation_20261025/ARCHIVE_INDEX.json)。18物理播种+18同形状IID对照，每路131072帧；全部lane而非仅第一路，明确同实例／跨实例／错拍。细节及复现见该目录README_ZH.md。原225例不改。

'''
prepend(ROOT/'architecture_tlm/random_service/quality/README_ZH.md',readme)
notes='''# 全路长流相关性：2026-10-25

入口REPORT.html；LAYERS为核心电压、理想比较器、调理和串行打包的实际统计；SUMMARY绑定36个案例及原始数组SHA；PEAKS列每观测最差位置；CONFIG定义所有坐标轴。报告中的最大相关是带符号的绝对值最大项，不是平均值或统一验收阈值。

输入是既有模拟电路仿真的三个noise seed，各20k样本，理想阈值0.6V。不是三路同时物理测量，也不是芯片物理熵认证。数字案例每个只启动一次，seed按1us真实时间到达；本地连续输出131072帧只消费启动前缀，默认1e8拍重播种不触发。两种调理和三种后端分别运行，不把同一试验种子在替代方案之间的复用说成同时服务多个模块。

每案例2实例，words.bin为frame-major uint8、shape=(131072,2*lanes)，先a再b，lane从0编号；states为little-endian uint32、shape=(2,3,6)，依次中点/尾256帧前/最终状态。matrices.npz的*_acf轴为(CONFIG.temporal_lags,lane)；*_cross为(spatial_lag,i,j)，Pearson定义i(t)与j(t+k)；bitplane只含lag0。相关按实际配对区间分别中心化。概率阈值扫描离线作用于同一随机字，不代表硬件同时实例化五套比较器，也不据此统计五倍PPA。

时间lag1..128、256/512/1024；R8及q4/13/64/128/192空间lag0/1/2/4/8/16/32/64/128。全部8bitplane时间相同，空间只同拍。q128和bit7互为反码，同源自/互相关一致已全量核验。变概率、异阈值路对、其他lag不冒称已覆盖。各后端L不同，最大值的搜索数不同；合成同形状PCG64对照不是标准随机性认证。

复现（仓库根，Python>=3.10+NumPy；绘图另需matplotlib；新结果目录不得存在）：

```powershell
g++ -O3 -std=c++11 -mpopcnt -static-libgcc -static-libstdc++ architecture_tlm/random_service/quality/correlation_native.cpp -o <exe>
$env:RNG_CORR_EXE='<exe>'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
python -m unittest architecture_tlm.random_service.quality.test_long_correlation -v
python -m architecture_tlm.random_service.quality.long_correlation --input <ideal_and_old_20000_v1> --out <new-results> --archive <new-archive> --exe <exe>
python -m architecture_tlm.random_service.quality.audit_correlation <new-results>
python architecture_tlm/random_service/quality/report_correlation.py <new-results> --archive <new-archive>
```

审计会读取上轮225例中18个匹配原始NPZ；需按原归档索引取得，不能缺原件却宣称golden前缀核验通过。CSV保留12有效数字，NPZ为float64。ZIP放在HTML同目录即可使用下载链接；本机交付路径在远端上传/。

C++是本地仿真加速器，无新RTL。7执行文件冻结于2dd9ec33；报告/审计为后处理。长流每个样本按原整数递推生成，初始前256帧对原周期模型、中段/尾段各256帧及最终状态对Python；另18×4096帧对上轮原件。无停顿长段操作数按固定动作累计，不说成每拍都跑RTL。健康调理、CDC和物理慢漂移仍按原条件限制。
'''
(R/'README_ZH.md').write_bytes(notes.encode('utf8'));shutil.copyfile(R/'README_ZH.md',ARC/'results/README_ZH.md')
recovery=ARC/'execution_recovery.bundle'
recovery_data=dict(path=str(recovery),sha256=sha(recovery),bytes=recovery.stat().st_size,
    prerequisite='d6d33995754fcdcea99286e4ce43f91647aa231a',contains='full local execution ancestry through2dd9ec33',
    note='Prefer this recovery bundle: the smaller execution.bundle requires local parent3b878c15, whose ancestry is included here.')
write(WORK/'RECOVERY_INDEX.json',recovery_data);shutil.copyfile(WORK/'RECOVERY_INDEX.json',ARC/'RECOVERY_INDEX.json')
(WORK/'HANDOFF.md').write_bytes((entry+notes+'\n远端复用PR188，当前发布前head057629881fcbf0704c87b70393bce1437edacae2；上传增量不可替换旧PR内容。ROOT中央台账比本分支多并行记录，已分别新增本run并render；只同步新record，不能整目录覆盖。新的完整执行恢复bundle见RECOVERY_INDEX；PR待审保留最小源码工作目录。MinGW32位沙箱DLL重定位失败，获工具批准后在沙箱外运行通过，算法未替换。没有subagent或远程新作业。\n').encode('utf8'))
for p in WORK.glob('preview-*.png'):shutil.copyfile(p,ARC/p.name)
for reg in [ROOT/'digital_circuit_simulation_registry',WS/'digital_circuit_simulation_registry']:
    p=reg/'records/rng-correlation-95-20261025.json';rec=json.loads(p.read_text(encoding='utf8'))
    rec['artifacts'].append(dict(path=str(recovery),role='portable_execution_recovery',required=True,present_at_registration=True,sha256=sha(recovery),bytes=recovery.stat().st_size))
    write(p,rec)
    p=reg/'archive_inventory.csv';rows=list(csv.DictReader(p.open(encoding='utf8',newline='')))
    assert not any(r['path']==recovery.as_posix() for r in rows)
    buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n')
    w.writerow(dict(path=recovery.as_posix(),bytes=recovery.stat().st_size,sha256=sha(recovery),linked_records=rec['id'],review_state='sha_verified_functional_only',note='完整本地执行提交祖先，依赖已发布d6；非新实验'))
    with p.open('ab') as out:out.write(buf.getvalue().encode('utf8'))
    note='\n2026-10-25 Issue95全路长流新增 `rng-correlation-95-20261025`，18物理播种+18同形状IID对照，每路131072帧、全路/多lag矩阵；仅DESIGN_PROOF，无新RTL/PPA。旧225例保留。\n'
    with (reg/'README_ZH.md').open('ab') as out:out.write(note.encode('utf8'))
    subprocess.run([sys.executable,str(reg/'registry.py'),'check'],check=True)
    subprocess.run([sys.executable,str(reg/'registry.py'),'render'],check=True)
print('metadata and recovery recorded; other task records preserved')
