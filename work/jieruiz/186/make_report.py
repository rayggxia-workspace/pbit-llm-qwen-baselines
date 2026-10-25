"""Generate the auditable main report from immutable summaries, no fitted timing."""
import json,statistics,csv,hashlib,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[3];BASE=ROOT/'architecture_tlm/unified_v6/results/scheduling_20261025'
r=json.loads((BASE/'COMPARISON.json').read_text(encoding='utf-8'));rows=r['rows'];by={x['case']['name']:x for x in rows}
if '--require-complete' in sys.argv:assert len(rows)==45 and not r['missing']
def get(name,key='TPOT_ms'):return by[name][key]
def stats(names,key='TPOT_ms'):
 xs=[get(n,key) for n in names if n in by]
 if len(xs)!=len(names):return '待封存'
 return ('%.3f'%xs[0]) if len(xs)==1 else '%.3f ± %.3f'%(statistics.mean(xs),statistics.stdev(xs))
def mean(names,key='TPOT_ms'):return statistics.mean(get(n,key) for n in names)
def seeds(prefix):return [prefix+str(i) for i in range(3)]
groups=[('BF16数字 FFN＋准确Attention',['common_bf16'],['8k_bf16']),('W8数字 FFN＋准确Attention',['corrected_common_w8'],['corrected_8k_w8']),('随机FFN＋准确Attention',seeds('common_sc_exact_s'),seeds('8k_sc_exact_s')),('W8数字 FFN＋筛选/PV',seeds('w8_pv_2k_s'),seeds('w8_pv_8k_s')),('随机FFN＋筛选/PV',seeds('common_sc_screen_pv_s'),seeds('8k_sc_screen_pv_s')),('随机FFN＋筛选/校正拒绝',seeds('common_sc_rejection_s'),[])]
table='| FFN与Attention组合 | 2K，ms/token | 8K，ms/token |\n|---|---:|---:|\n'
for label,n2,n8 in groups:table+=f'| {label} | {stats(n2)} | {stats(n8) if n8 else "未测"} |\n'
s2=mean(seeds('common_sc_screen_pv_s'));s8=mean(seeds('8k_sc_screen_pv_s'))
conclusion=f'''当前固定资源下，随机FFN＋筛选/PV比BF16准确参考减少约{100*(1-s2/get('common_bf16')):.1f}%（2K）和{100*(1-s8/get('8k_bf16')):.1f}%（8K）的时间；对更有针对性的W8数字准确参考，2K仍慢{100*(s2/get('corrected_common_w8')-1):.1f}%，8K快{100*(1-s8/get('corrected_8k_w8')):.1f}%。这不是“随机乘法全面加速”的证据。'''
if all(n in by for n in seeds('w8_pv_8k_s')):
 a2=mean(seeds('w8_pv_2k_s'));a8=mean(seeds('w8_pv_8k_s'))
 conclusion+=f'同样采用筛选/PV时，W8数字FFN分别为{a2:.3f}/{a8:.3f} ms；随机FFN组合慢{100*(s2/a2-1):.1f}%/{100*(s8/a8-1):.1f}%。因此当前速度收益主要来自Attention，随机FFN仍需降低恢复/搬运成本，能耗面积优势也尚未完成验证。'
text='''# 成熟调度借鉴与数字／概率架构对照

Issue186 / [PR190](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/190)，2026-10-25。依赖PR183；本报告是可复现的架构探索，PR不自动合并。

## 先看结论

**可以借鉴成熟模拟器的存储调度来搭建我们自己的模型，且本轮已经实现并运行。** 保留统一 `unified_v6`，让数字矩阵和随机FFN使用共同的有限预取、存储槽和释放规则，Attention的稀疏地址进入真实DRAMSys队列。没有把整个Qwen伪装成已经在ONNXim原生执行。

以下全部是Qwen3-4B后训练模型形状、36层、batch=1、单token decode的条件时延。2K/8K是包含当前query的总因果长度；开始时有L−1条KV，**不含prefill/TTFT**。单位为ms/token，越低越好；概率主配置是三seed均值±样本标准差，数字确定参考只需一次。

'''+table+'\n'+conclusion+'''

这里的“共同资源”指相同外存、共享SRAM、时钟和调度政策；数字MAC与SC阵列的本地状态和电路不同，**不是已证明同面积比较，也不是GPU实测**。W8只量化FFN权重，QKV/O/lm_head等保持原数字路径；不等于全模型W8A8。

## 具体借鉴和实现了什么

| 来源／已有工作 | 本轮落实的机制 | 实际验证边界 |
|---|---|---|
| ONNXim Core / GemmWS | 输入有效后执行、有限tile入口、双缓冲、结果就绪才写回 | 原生Core/WS/Sram小探针25情景；本模型中独立实现共同生命周期 |
| LLMCompass、Timeloop与既有ZigZag探索 | 分块候选必须满足容量，再在同一执行器计时 | 两侧均扫32/64/128/256KiB，另做64项静态容量检查；不是全局搜索 |
| 既有DRAMSys + DRAMPower | 标准DRAM命令/刷新/行bank时序与回压 | 本轮全部完整对照实际调用DRAMSys；不使用带宽公式替代完整执行 |
| 本项目Attention | 采样完成后生成真实地址，去重、保留重数、按GQA组复用V | SG只合并提交，不删必需突发；采样失败及随机服务等待保留 |

来源版本、许可、之前GitHub结果和不宜直接移植的代码详见[调研说明](SCHEDULER_RESEARCH_ZH.md)和[SOURCES](SCHEDULER_SOURCES.json)。ONNXim的固定版本是8599bee46b311fb267ac34b0677ad7db3d8a8ccd。其Qwen head_dim推导、混合数制、SWISH和部分SRAM/NoC实现仍需适配，所以本轮提取可验证机制，而不是只改模型名称就运行。

### 同一个tile怎样执行

```mermaid
flowchart LR
    D[DRAMSys：32个burst信用] --> R[一个有界DMA响应缓存]
    R --> S[共享SRAM ping / pong]
    S --> L[本地权重或operand tile]
    L --> C[数字MAC / SC采样与计数]
    C --> F[恢复 / 累加 / 写回]
    F --> X[retire释放槽]
    C -.下一tile的DMA可重叠.-> D
    A[筛选与采样完成] --> G[去重排序 / 有界SG描述符]
    G --> D
```

1. 检查下一tile的容量、槽所有权和代次；最多一个待接收DMA。
2. DRAM完整返回后才能填共享SRAM，局部权重装载后才能计算。下一DMA可覆盖当前计算。
3. **当前实现仅重叠下一DMA**；下一SRAM填充和本地编程仍等当前tile恢复/退役。响应缓存是有限宏，不能无限保存未来数据。
4. SC同一波的8个64×64阵列并行；本地权重保持32KiB，每层FFN权重71.25MiB，需2280波。不是整个FFN常驻，也不是8个阵列串行运行。
5. 普通数字路径采用相同预取生命周期，同时显式记录64KiB本地operand、激活、W8块部分和容量；这些本地成本未标定，不是免费存储。
6. 资源时钟只向前推进。尚未实现跨全部层、head和算子的任意乱序调度，也没有把已完成的同步DRAM请求回填到过去。

### 最新FFN和Attention保持哪些边界

- 随机FFN：固定W8；x固定四档、共享64输入、T=K=64分层；g/u各四档P8＋符号，sigmoid独立定点码/LUT，三流AND的32联合分层、T64；流直接进入Wd，最后桶归约、系数恢复、宽累加、BF16接口。没有连续z落盘再编码。
- GU定点系数编译/舍入仍是**待bit-exact验证的宏**；本次是调度仿真，不继承训练或PPL结论。
- Attention准确参考采用分块online softmax与PV；筛选采用摘要/max4＋保留概率、固定预算修补，每query最多8个64-token块。它不是密集耦合网络退火。
- PV采用systematic采样/CDF，S=ceil(L/16)，2K为128、8K为512。去重后的V只读一次，重复次数仍进入累加；GQA组内合并后共享读取。
- 本轮Ising方向是**校正拒绝式并行采样模块**：真实统计proposals、拒绝和最终地址，不是旧逐节点Gibbs，也不是赢家保持；8K该路线未测，不能借2K外推。
- 原Attention随机服务按真实接口执行；新三路非线性的独立随机带宽仍使用有限宏（II=2、重放/种子/状态显式计数），不能说已经全部完成物理源接合。随机比特流不放SRAM，不代表端点状态面积为零。

## 资源与时序参数

| 项目 | 本轮统一设置 | 证据／假设 |
|---|---|---|
| 核心 | 100MHz | 条件时钟；完整布局/STA未完成 |
| DRAM | Micron DDR4-1866，2通道×2rank，16GiB，64B burst、32在途 | 真实DRAMSys5.6 / SystemC3.0.2；理论29.851GB/s |
| 共享SRAM | 8MiB、64bank、64GB/s fabric | 55nm SS宏表征；80MHz宏，互连与CDC为显式假设 |
| DMA响应／双槽 | 默认响应上限64KiB；两个64KiB共享槽 | 容量/所有权已计，本地缓存PPA未知 |
| SG | 每批最多256个地址span，描述符16B/项、形成1核心拍/span | 4KiB控制存储；实际DRAM滚动处理，控制电路未STA |
| 数字 | 512 MAC/拍、64路向量、16路非线性 | 宏吞吐；不是最佳ASIC或GPU的标定值 |
| SC | 8×64×64阵列；GU采样II1，非线性直连Wd源II2 | 原有限宏；计数器、恢复、局部宽端口PPA仍有缺项 |

完整时延包含这些假设下的存储等待；真实DRAM模型不能代替数字MAC、SC阵列和片上互连的时序标定。

## 存储调度带来的变化

相同地址与数据量的真实DRAM微基准：

| 访问 | 串行span，ns | SG，ns | 宏请求数量变化 |
|---|---:|---:|---:|
| 连续64KiB | 2234.048 | 2234.048 | 1→1 |
| 64个分散span | 1729.136 | 716.096 | 64→1 |
| 1024个分散span | 29668.672 | 12116.816 | 1024→4 |
| 128个写span | 2388.416 | 767.552 | 128→1 |

这只说明合并请求减少人为排空，并不等于整机2～3倍加速。微基准隔离DRAM服务；整机另计描述符生成、SRAM与计算。

'''
text+='| 2K调度对照 | W8数字FFN＋准确Attention，ms | 随机FFN＋准确Attention，ms |\n|---|---:|---:|\n'
text+=f"| 共同tile，但每个span仍串行 | {get('corrected_shared_serial_w8'):.3f} | {get('shared_serial_sc'):.3f} |\n| 共同tile＋SG | {get('corrected_common_w8'):.3f} | {get('common_sc_exact_s0'):.3f} |\n| 之前PR183策略 | {get('corrected_previous_w8_check'):.3f} | 516.979（历史已封存） |\n"
text+='''
前两行采用相同描述符计费，隔离SG的贡献。PR183行仍有旧数字调度/计费边界，SC数字是该任务原结果，因此不能把所有差异都归于某一项机制。旧数字W8只做整行一次scale，遗漏K64独立尺度；本轮7个W8参考已独立修正重跑，旧原件保留，不作为最终W8表。正确路径每tile有nG次scale、n(G−1)次归约和4nG B FP32部分和，其中G=ceil(K/64)。修正动作数很多但时间增加很小，是因为部分工作被DMA等待覆盖，不能不计成本。

### 有限搜索结果

同样扫描数字tile粒度，SC的64×64物理tile不变；此处也影响SC整机的普通QKV/O/lm_head投影。

| 数字tile | W8准确，ms | SC准确，ms |
|---|---:|---:|
'''
for k,w,s in [(32,'corrected_chunk32k_w8','chunk32k_sc'),(64,'corrected_common_w8','common_sc_exact_s0'),(128,'corrected_chunk128k_w8','chunk128k_sc'),(256,'corrected_chunk256k_w8','chunk256k_sc')]:text+=f'| {k}KiB | {get(w):.3f} | {get(s):.3f} |\n'
text+='''
更大tile会增加operand/响应/部分和容量，不是完全同面积。数字参考也能受益；不能只优化SC。固定共同表仍使用64KiB。

| SC阵列数 | 2K准确Attention，ms | 本地权重容量 | 比较限制 |
|---|---:|---:|---|
'''
for e,n in [(8,'common_sc_exact_s0'),(16,'engines16_sc'),(64,'engines64_sc')]:text+=f'| {e} | {get(n):.3f} | {e*4}KiB | 增加阵列／计数器／供数资源，非同面积 |\n'
text+=f"\nSG深度16/64/256的2K筛选PV单seed分别{get('sg16_sc_pv'):.3f}/{get('sg64_sc_pv'):.3f}/{get('common_sc_screen_pv_s0'):.3f} ms。收益已趋于平缓。这些资源扫描为单seed架构试探，不能作为质量结论。\n"
text+='''
### SRAM容量可以减少，但不能忽略端口

静态64候选中62合法；8K/256KiB tile的两个1MiB候选容量不够。默认64KiB下，最坏筛选/采样合同预留795,776B共享SRAM；单列本地权重、数字operand、随机端点等不包含在这个数内。历史KV及绝大部分权重仍在DRAM。

| 容量 | bank数 | bank峰值GB/s | 已表征宏面积合计mm² |
|---|---:|---:|---:|
| 1MiB | 16 | 20.48 | 4.995 |
| 2MiB | 32 | 40.96 | 9.989 |
| 4MiB | 64 | 81.92 | 19.978 |
| 8MiB | 64 | 81.92 | 39.957 |

4MiB/64bank值得作为下一配置：在当前映射地址、bank和端口不变时，服务公式不变，宏数量与漏电项减半。**这是结构性推断，45项正式时延仍统一用8MiB**；不是已经重跑4MiB或找到全局最优。增加容量必须通过实际驻留/缓存/更大tile才能换来性能。

## 读写与能耗：现在能够比较什么

以下取seed0；GB为十进制、跨36层全token，SRAM含读和写，同一权重经过两级存储会被多次计数。

| 2K方案 | DRAM流量GB | SRAM流量GB | DRAM core模型J | SRAM内部动态＋漏电mJ |
|---|---:|---:|---:|---:|
'''
for label,n in [('BF16准确','common_bf16'),('W8数字准确','corrected_common_w8'),('随机FFN＋准确','common_sc_exact_s0'),('随机FFN＋筛选PV','common_sc_screen_pv_s0'),('随机FFN＋校正拒绝','common_sc_rejection_s0')]:
 x=by[n];text+=f"| {label} | {x['DRAM_bytes']/1e9:.3f} | {x['SRAM_bytes']/1e9:.3f} | {x['DRAM_core_J']:.4f} | {1000*(x['SRAM_internal_J']+x['SRAM_leakage_J']):.3f} |\n"
text+='''
**这些J值是内存子项模型输出，不是整芯片能量。** DRAMPower6.3.1的core-current限值组合含已知负ACT增量，原值保留，不能当物理负能量；它不反馈时序。其数量占比不是总误差界。I/O/PHY、控制器、互连、本地权重保持和部分随机/恢复电路未完整定价，full physical energy/area继续为null。已有通用数字算子单价也不是测量值；不同覆盖范围的priced subtotal不得直接算整机节能倍数。

校正拒绝减少了流量，但更多等待延长DRAM背景活动，core模型能量反而升高。这个现象来自显式执行时间，不能用“字节减少”直接推断总能量减少。

## 当前瓶颈与优先改进

SC准确路径的FFN约274.75ms，修正W8数字约191.69ms。SC阵列本身约77.98ms忙时；桶移位归约、系数恢复、跨tile宽累加三个资源约34.47＋30.37＋13.69ms，恢复后还串行释放权重槽。**资源忙时可互相重叠，不能把所有busy相加充当总时间。** 这说明“采样64次”不是唯一瓶颈，单纯扩大阵列或换模拟器名字都不能消掉后处理。

下一步按以下顺序更有价值：

1. 做恢复/累加与下一波计算重叠的有限流水线：需要双份计数/系数状态、端口与回压，明确归约依赖，不能在表中直接删掉78ms。数字参考也应采用在线分块归约等相应优化。
2. 以4MiB/64bank和更大数字tile作为候选，确认实际访问映射与局部缓存；扩大阵列单列面积与能量，避免用8倍硬件换速度后称为同面积收益。
3. 校正拒绝先查随机配置/读出、proposal与合法性归约/仲裁周期；本轮2K慢的结果不支持把它当默认最快Attention。seed0的sampler资源忙时约207.49ms，440,305次proposal得到147,456个地址，平均约2.99次；这已经是并行宏，不是把每个候选逐个更新。其他并行采样机制另做同质量比较。
4. 将GU整数恢复与训练前向逐位对齐，做当前Qwen3-4B Instruct的质量闭环；本TLM使用合成logit，三seed时延稳定不是PPL稳定。
5. 仅在结论对这些机制敏感时增加beat级bank仲裁、跨KV head流水和更细互连；普通规则算子仍可保留校准后的宏。不要为了“周期精确”重写全部系统而忽略局部电路证据。

## 验证与复现

- 110项Python机制/回归通过；覆盖容量、尾tile、单/双缓冲、旧SC合同保持、W8块恢复、所有权、SG和时间因果负例。
- 实际DRAMSys十项小整机门禁通过；第一版fixture候选预算不足的失败保留，生产默认未改。
- ONNXim固定版本原生Core/WS/Sram实现字节不变，25情景覆盖2/1 tile入口、有限外部请求、bank地址服务、SC显式忙时8/32/64/128；官方WS无payload夹具39/47拍复现。正常双tile的native WS为121拍，单tile221；SC64为282/329拍。**这不是等工作量数字/SC性能比较**，只验证延迟接口、依赖和回压。外部内存是合成有限服务，未把整个Qwen接到ONNXim。
- 原生构建的HTTP超时、fmt链接失败与成功版本各自保留；编译器告警及后续sanitizer状态见[native说明](probes/onnxim_native/README_ZH.md)，没有隐藏失败。
- 45个全模型配置由31主项＋7个修正W8＋1个8K BF16＋6个同Attention消融组成；每项必须有completed MANIFEST、原始RESULT与summary SHA、source/config/bridge SHA。原始trace在本人服务器，Git仅必要汇总与索引。

| 结果组 | 冻结执行源码 | 远端Slurm |
|---|---|---|
| 31主配置 | bab9721d629df643e4096f5111a0a4ac5722ed3e | 2943 |
| 7修正W8 | 6b0df70b43055fa235fb34a9933ba20f4d394895 | 2976 |
| 8K BF16 | bab9721d；配置73727073 | 2984 |
| W8＋同样筛选/PV | 6b0df70b；配置ae89e9fe | 2987 |
| 原生ONNXim成功probe | 4c51dae18aaa26f6723483e4d821b9bdb9a80f2d | 2986 |

统一运行：

```sh
# 先按 probes/dramsys_bridge/README_ZH.md 构建真实桥接器
export PBIT_DRAMSYS_BRIDGE=/absolute/path/to/pbit_dram_bridge_sg_v6_audit
python -m architecture_tlm --model qwen3_4b --memory-profile mature_ddr4 --ffn w8 --attention exact --context 2048 --output output/w8_exact
python -m architecture_tlm --model qwen3_4b --memory-profile mature_ddr4 --ffn sc --attention screen_pv --context 8192 --seed 0 --output output/sc_pv_s0
```

正式运行前提交代码，输出目录必须不存在；概率主要配置另跑seed1/2。默认入口已切到mature_ddr4，旧balanced_ddr4/legacy保留用于明确对照。复算本表使用 `work/jieruiz/186/collect_schedule.py`（四组）、`analyze_schedule.py --require-complete`、`make_report.py --require-complete`；远端原件路径和SHA见各SUBMISSION、EXECUTION、MANIFEST和HANDOFF。大文件访问需已有服务器权限，不宣称公开Git读者已能访问私人存储。
'''
(ROOT/'architecture_tlm/unified_v6/MATURE_SCHEDULING_ZH.md').write_text(text,encoding='utf-8',newline='\n')
with (BASE/'COMPARISON.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f,lineterminator="\n");w.writerow(['case','context','seed','TPOT_ms','core_cycles','FFN_ms','attention_core_ms','DRAM_bytes','SRAM_bytes','DRAM_core_model_J','SRAM_internal_J','SRAM_leakage_J','full_physical_energy_J','execution_commit','raw_result_sha256'])
 for x in rows:w.writerow([x['case']['name'],x['case']['context'],x['case']['seed']]+[x[k] for k in ['TPOT_ms','cycles','FFN_ms','attention_core_ms','DRAM_bytes','SRAM_bytes','DRAM_core_J','SRAM_internal_J','SRAM_leakage_J','full_physical_energy_J','execution_commit','result_sha256']])
agg={label:{str(ctx):dict(n=len(names),mean_ms=mean(names),stdev_ms=statistics.stdev(get(n) for n in names) if len(names)>1 else 0,minimum_ms=min(get(n) for n in names),maximum_ms=max(get(n) for n in names)) for ctx,names in [(2048,n2),(8192,n8)] if names and all(n in by for n in names)} for label,n2,n8 in groups}
(BASE/'AGGREGATE.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256((BASE/'COMPARISON.json').read_bytes()).hexdigest(),verified=len(rows),expected=45,missing=r['missing'],groups=agg),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'report_generated':True,'verified':len(rows),'expected':45}))
