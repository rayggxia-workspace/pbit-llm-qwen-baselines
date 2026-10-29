"""Conditional sampling-subsystem budget from existing PT/library/TLM evidence.

Usage: python derive.py WORKSPACE_ROOT MODEL_RECALIBRATION_RESULTS_JSON
The model input is the byte-exact file at public commit 91f68416acad0e8306b920b1b8ac779f3d24ad98,
architecture_tlm/ppa_recalibration_20261027/RESULTS.json. No new simulation.
"""
from pathlib import Path
import hashlib
import json
import math
import statistics as st
import sys

ROOT = Path(sys.argv[1])
MODEL = Path(sys.argv[2])
OUT = Path(__file__).resolve().parent
BASE = OUT.parent
inputs = []


def read(p):
    b = p.read_bytes()
    inputs.append(dict(path=p.as_posix(), sha256=hashlib.sha256(b).hexdigest()))
    return json.loads(b)


def save(name, value):
    (OUT / name).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


model_bytes = MODEL.read_bytes()
assert hashlib.sha1(b'blob ' + str(len(model_bytes)).encode() + b'\0' + model_bytes).hexdigest() == 'a475740319d29ae80cf5c463380dfb124ac8fab4'
model = read(MODEL)
means = model['optimized_three_seed_means']
ref = means['counter_ICG_plus_digital_gate_candidate']
T = ref['elapsed_ms'] / 1000
old = ref['modules']['Attention_existing_PRNG_endpoints']
anchor = dict(
    repository='rayggxia-workspace/pbit-llm-qwen-baselines',
    commit='91f68416acad0e8306b920b1b8ac779f3d24ad98',
    path='architecture_tlm/ppa_recalibration_20261027/RESULTS.json',
    git_blob='a475740319d29ae80cf5c463380dfb124ac8fab4',
    input_sha256=hashlib.sha256(model_bytes).hexdigest(),
    elapsed_s=T, raw_area_mm2=ref['covered_area_mm2'], area55_mm2=ref['covered_area_mm2'] * .81,
    onchip_J=ref['covered_onchip_J'], onchip_W=ref['covered_onchip_J'] / T,
    external_proxy_J=ref['legacy_external_budget_J'],
    external_proxy_W=ref['legacy_external_budget_J'] / T,
    other_area55_mm2=(ref['covered_area_mm2'] - old['area_mm2']) * .81,
    other_onchip_J=ref['covered_onchip_J'] - old['energy_J'],
    removed_old_attention_rng=old,
    other_scenarios={k: dict(onchip_J=v['covered_onchip_J'], onchip_W=v['covered_onchip_J']/T) for k, v in means.items()},
    conditions='Qwen3-4B post-trained shape, B1/2K,36layers,lm_head; stochastic FFN; screen_pv old Attention;500MHz core',
    status='conditional partial TLM budget; digital idle90% gating scenario; no fully calibrated chip total',
    replacement_scope='remove only old aggregate Attention RNG row, keep all other actions/time fixed; sensitivity, not an end-to-end Ising replacement')

reg_summary = read(BASE / 'regbank_20261029/SUMMARY.json')
reg_raw = read(BASE / 'regbank_20261029/RESULTS.json')
reg = next(r for r in reg_summary['rows'] if r['top'] == 'bank_w12_g1_c0')
rr = next(r for r in reg_raw['results'] if r['case']['top'] == reg['top'])
reg_leak_W = st.mean(w['power']['leakage_W'] for w in rr['windows'] if w['window']['name'] == 'idle')
reg_hold_W = reg['windows']['sample_hold']['power_uW'] * 1e-6
reg_idle_W = reg['windows']['idle']['power_uW'] * 1e-6
reg_load_J = reg['windows']['load']['energy_pJ'] * 1e-12
clock_s = 1e-8
frontends = {}
for core, lanes in [('gf64', 64), ('bivium', 20)]:
    d = read(ROOT / 'digital_circuit_simulation_registry/records' / ('rng-38322118-' + core + '-100.json'))
    active = [c for c in d['cases'] if c['scenario'] == 'stream' and c['phase'] == 'active']
    idle = [c for c in d['cases'] if c['scenario'] == 'idle' and c['phase'] == 'active']
    assert len(active) == len(idle) == 3
    assert sorted(c['seed'] for c in active) == [17, 503, 1009]
    assert all(c['clock_ns'] == 10 and c['frames_generated'] == 2048 for c in active)
    n = math.ceil(128 / lanes)
    frontends[core] = dict(
        instances=n, outputs=n*lanes, discarded=n*lanes-128,
        raw_area_um2=n*st.mean(c['area_um2'] for c in active) + reg['raw_area_um2'],
        area55_mm2=n*st.mean(c['area_um2'] for c in active)*.81e-6 + reg['area55_mm2'],
        endpoint_round_J=n*st.mean(c['pJ_per_generated_frame'] for c in active)*1e-12,
        endpoint_idle_W=n*st.mean(c['total_uW'] for c in idle)*1e-6,
        endpoint_leak_W=n*st.mean(c['leakage_uW'] for c in idle)*1e-6,
        native_q_bits=9, storage_pricing_bits=12)

sb = read(BASE / 'smallbanks_20261029/ARRAY_RESULTS.json')
sbs = read(BASE / 'smallbanks_20261029/SUMMARY.json')
sram = {}
for prob in [1,16]:
    def group(window):
        g = [c for c in sb['cases'] if c['stage'] == 'interface_results' and c['window'] == window and c['prob32'] == prob]
        assert len(g) == 3
        return g
    readg, loadg = group('sequential'), group('load')
    sram[prob] = dict(read_J=st.mean(c['total_power_W'] for c in readg)*clock_s,
                      write_J=st.mean(c['total_power_W'] for c in loadg)*clock_s,
                      leak_W=st.mean(c['leakage_power_W'] for c in readg),
                      raw_area_um2=sbs['area_raw_um2'],
                      area55_mm2=sbs['area_raw_um2']*.81e-6)
# Verify the previously collected raw area rather than silently changing its scale.
assert math.isclose(sbs['area_55eq_mm2'],sbs['area_raw_um2']*.81e-6)


def percentages(area, energy):
    return dict(
        area_share_pct=100*area/(anchor['other_area55_mm2']+area),
        onchip_power_share_pct=100*energy/(anchor['other_onchip_J']+energy),
        with_external_power_share_pct=100*energy/(anchor['other_onchip_J']+anchor['external_proxy_J']+energy),
        area_relative_to_original_budget_pct=100*area/anchor['area55_mm2'],
        energy_relative_to_original_budget_pct=100*energy/anchor['onchip_J'])


def calculate(core, H, updates, keep_idle_dynamic):
    assert H in [1,4,8,32] and 32 % H == 0
    head_invocations = 36*32
    head_reads = head_invocations*updates
    row = dict(core=core, parallel_heads=H, updates=updates, idle_dynamic_keep=keep_idle_dynamic)
    if core in frontends:
        a = frontends[core]
        active_round_J = a['endpoint_round_J'] + reg_hold_W*clock_s
        endpoint_idle = a['endpoint_leak_W'] + keep_idle_dynamic*(a['endpoint_idle_W']-a['endpoint_leak_W'])
        bank_idle = reg_leak_W + keep_idle_dynamic*(reg_idle_W-reg_leak_W)
        endpoint_idle_head_s = H*T-head_reads*clock_s
        bank_idle_head_s = H*T-head_reads*clock_s-head_invocations*8*clock_s
        assert bank_idle_head_s > 0
        E = (head_reads*active_round_J + head_invocations*reg_load_J
             + endpoint_idle_head_s*endpoint_idle + bank_idle_head_s*bank_idle)
        work_J = head_reads*active_round_J + head_invocations*reg_load_J
        active_W = H*active_round_J/clock_s
        per_head_cycles = updates+8
        raw_area = H*a['raw_area_um2']
        area = H*a['area55_mm2']
        extra = dict(idle_evidence='existing endpoint CE-idle and register idle PT; zero dynamic is unimplemented task-level clock-gating scenario')
    else:
        prob = int(core.split('_')[-1])
        a = sram[prob]
        writes = head_invocations*math.ceil(updates/2)
        # 160 updates require 64 initial writes +16 writes of32 fresh bits after128 reads.
        # This is an explicit scheduling/cost proposal, not an RTL-tested160-update run.
        idle_head_s = H*T-(head_reads+writes)*clock_s
        assert idle_head_s > 0
        idle_proxy = a['leak_W']+keep_idle_dynamic*(a['read_J']/clock_s-a['leak_W'])
        work_J = head_reads*a['read_J']+writes*a['write_J']
        E = work_J + idle_head_s*idle_proxy
        active_W = H*a['read_J']/clock_s
        per_head_cycles = updates+math.ceil(updates/2)
        raw_area = H*a['raw_area_um2']
        area = H*a['area55_mm2']
        extra = dict(idle_evidence='CEB tied0: always-reading active power proxy, NOT a measured static-address idle window; stopped-clock case retains measured leakage',
                     preload_write_cycles=math.ceil(updates/2),
                     omitted='upstream sample generation/read/transport, packing, task-level gating/refresh control')
    row.update(area_raw_mm2=raw_area/1e6, area55_mm2=area, active_W=active_W,
               work_J=work_J, energy_J=E, average_W=E/T,
               service_time_s=36*(32//H)*per_head_cycles*clock_s,
               sample_read_time_s=36*(32//H)*updates*clock_s, **extra,
               **percentages(area,E))
    return row


rows = [calculate(core,H,U,k) for core in ['gf64','bivium','sram_1','sram_16']
        for H in [1,4,8,32] for U in [128,160] for k in [0,.1,1]]
def pick(core,H=32,U=160,k=0):
    return next(r for r in rows if (r['core'],r['parallel_heads'],r['updates'],r['idle_dynamic_keep']) == (core,H,U,k))

# Fresh Bivium-generated samples instead of treating precomputation as free.
# A shared one-head generator is lower area but supplies all1152 head invocations serially.
g = pick('bivium',H=1)
b = pick('sram_1')
# One generator visits all32 heads once for the initial128 samples, then again
# for32 fresh samples. It must reload each head's threshold bank on that revisit.
extra_load_head_s=36*32*8*clock_s
extra_load_J=36*32*reg_load_J-reg_leak_W*extra_load_head_s
gen_service=g['service_time_s']+extra_load_head_s
serial_writes_s=36*32*80*clock_s
shared_energy=b['energy_J']+g['energy_J']+extra_load_J
shared_generation = dict(generator_head_engines=1,
    area55_mm2=b['area55_mm2']+g['area55_mm2'], energy_J=shared_energy,
    average_W=shared_energy/T, extra_threshold_reloads=36*32,
    generation_service_s=gen_service, serial_bank_writes_s=serial_writes_s,
    parallel_bank_reads_s=b['sample_read_time_s'],
    no_overlap_service_s=gen_service+serial_writes_s+b['sample_read_time_s'],
    status='conditional additive budget; packing/transport/clock-gating hardware unpriced; no overlap or timing demonstrated',
    **percentages(b['area55_mm2']+g['area55_mm2'], shared_energy))
result = dict(kind='derived_budget_not_new_EDA_or_end_to_end_model_run',
              area_scale=.81, sample_hz=100000000, model_anchor=anchor,
              threshold_storage=dict(top=reg['top'],area55_mm2=reg['area55_mm2'],idle_W=reg_idle_W,hold_W=reg_hold_W,leak_W=reg_leak_W,load_J=reg_load_J),
              frontends=frontends, sram=sram, rows=rows,
              sram_with_shared_bivium_generation=shared_generation,
              inputs=inputs, code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              caveats=['GF64 joint correlation: current Attention adapter rejects it by default; no matched P8 PPL',
                       'SRAM sample freshness/refill/160update control unverified; no free cyclic replay',
                       '500MHz model window and100MHz sampling island, no CDC/retiming integration',
                       'global entropy/reseed, fairness RNG, arbitration/feedback/LUT/address/V and global wires/CTS excluded',
                       'standalone endpoint, threshold bank and macro-array boundaries/loads differ; sum is a proxy, not integrated PT',
                       'whole-model denominator is partial, conditional; no new decode timing or accuracy claim'])
save('RESULTS.json', result)

labels={'gf64':'GF64＋阈值寄存器/比较','bivium':'Bivium＋阈值寄存器/比较','sram_1':'128个SRAM bank（p=1/32）','sram_16':'128个SRAM bank（p=1/2）'}
table='| 方案 | 每头面积 mm² | 32头面积 mm² | 面积占比 | 32头活动功率 mW |\n|---|---:|---:|---:|---:|\n'
pt='| 方案 | 现有空闲/常开代理 mW | 片上占比 | 停钟保留漏电 mW | 片上占比 | 加外存粗预算占比 |\n|---|---:|---:|---:|---:|---:|\n'
et='| 方案 | 128轮工作能量 μJ/token | 160轮工作能量 μJ/token | 160轮服务时间 μs/token |\n|---|---:|---:|---:|\n'
for core in labels:
    r=pick(core);u=pick(core,k=1);s=pick(core,U=128)
    table+=f"| {labels[core]} | {r['area55_mm2']/32:.5f} | {r['area55_mm2']:.4f} | {r['area_share_pct']:.3f}% | {r['active_W']*1000:.3f} |\n"
    pt+=f"| {labels[core]} | {u['average_W']*1000:.3f} | {u['onchip_power_share_pct']:.3f}% | {r['average_W']*1000:.3f} | {r['onchip_power_share_pct']:.3f}% | {r['with_external_power_share_pct']:.3f}% |\n"
    et+=f"| {labels[core]} | {s['work_J']*1e6:.3f} | {r['work_J']*1e6:.3f} | {r['service_time_s']*1e6:.2f} |\n"
report=f'''# Attention采样前端三方案：整模型面积与功耗占比

2026-10-29，Issue198 / PR199。只复用既有PT、宏库和Issue186整模型TLM计数，无新EDA/PPL或整机时序仿真，不新增registry run。

**判断：Bivium与128小bank的活动功率接近；32头并行时约占既有片上面积规模的2%–3%。采样间隙停钟后，采样前端平均功耗约为片上候选预算的0.2%；维持时钟运行则可能达到几个百分点甚至约10%。因此目前优先级是空闲门控、共享并行度与统计质量，而不是只优化一次比较的门数。**

## 统一边界与整模型分母

- 32个Q头各有128节点，36层复用同一套硬件；面积乘32，不乘36。每节点R8，需要128×8随机bit/轮。各前端100MHz，SS1.08V125°C。该100MHz岛与原500MHz计算平台尚未集成。
- GF64用2个64字端点，Bivium用7个20字端点、丢弃12字仍收费。端点已含比较器、输出寄存器及状态/接口控制，只另加已测的128×12位门控阈值库。q/256端口是9位，12位存储作为现有可容纳实现的计价代理，不宣称这是最小8/9位实现，也不再次加旧12/16位比较器总功耗。
- SRAM方案每头128个64×2宏，共2KiB；含选位寄存器/MUX与本地读写。32头共64KiB。样本生成、源读取和搬运另计，不把预存当免费。
- 共同的分数量化/LUT、反馈仲裁、公平随机源、token映射、V读取/累加不在此次“128位采样向量前端”内。面积是单元/宏总和，无布线/CTS/新停钟控制；原始报告保留。所有本项目原始面积只乘一次0.81，功耗不乘0.81。
- 整模型锚点来自已合并PR192的公开commit `{anchor['commit']}`，Qwen3-4B后训练模型形状、36层、B1/2K decode、含lm_head，随机FFN平台。三seed平均57.445385ms/token；原始计价面积{anchor['raw_area_mm2']:.6f}mm²，等效55nm面积{anchor['area55_mm2']:.6f}mm²。片上门控候选0.144545J/token、2.5162W；旧外存敏感性预算再加6.1661W，合计8.6823W。数字部分90%空闲动态削减仍是情景，完整已校准整机总值为空。
- **占比公式明确采用条件替换**：从上述锚点中仅移除原Attention随机端一行（原始面积{old['area_mm2']:.6f}mm²、{old['energy_J']*1000:.6f}mJ/token），再加入新方案，防止两份随机端重复计费。其余动作、时间和外存保持不变：面积分母=A其余+A新；能量分母=E其余+E新，外存列再加旧外存预算。原Attention是筛选＋准确softmax＋PV采样，旧8端点还含筛选和PV偏移服务；这仅是前端替换的规模敏感性，**并非完成新Attention功能替换后的真实整机预算**。新公平服务/反馈、改变KV流量和调度必须另补，不能据此宣称新PPL或TPOT。

## 面积和活动功率

{table}
活动功率指全部32头同时连续采样。不能直接用这一列除以2.5162W，声称是平均整机占比。Bivium的活动能量约84.61pJ/128位向量（含阈值保持），SRAM顺序读取81.71–82.92pJ；前者面积略小。GF64低价伴随已知联合相关性，当前Attention适配器默认拒绝；它是成本参照，不能直接作为已验收精度的优胜方案。三者均没有在此完成匹配P8的Qwen PPL对比。

## 平均功耗：必须包含空闲时间

默认主表用128保留样本＋32预热，共160次更新；这是沿用既有采样预算的工作量，不说明赢家保持一定需要32轮预热。RESULTS.json也列出128轮/无预热。

{pt}
左侧GF64/Bivium使用实测CE-idle功耗：每端点491.7/524.133μW，阈值库idle31.587μW。CE不更新状态并不等于停钟。SRAM当前RTL将CEB绑0，时钟不断就持续读；左侧用实测读窗口作为常开读出代理，**不是另测了静止地址idle**。

右侧是待实现的任务级停钟情景，保留实测漏电：每个GF64端点17.15μW、Bivium端点22.41μW，阈值库{reg_leak_W*1e6:.4f}μW；每头SRAM阵列约146.4–146.5μW。不是把门控后的功耗设为零。新增ICG、使能/唤醒、种子寿命服务和CTS/CDC均未集成验证，不能把这列写成已测完整停钟电路。90%空闲动态削减的中间情景也保留在RESULTS.json。

计算式：E_token=Σ(有效采样轮数×实测每轮能量)+Σ(装载拍数×实测写入能量)+Σ(各实例剩余空闲秒数×空闲功率)；P平均=E_token/57.445385ms。工作窗口已包含自身漏电，剩余时间才补空闲，避免重复计费。

## 有效采样工作、容量及上游生成

{et}
工作能量列包含阈值装载或SRAM写入，不包含剩余空闲时间。32头并行的160轮读取本身只需36×160×10ns=57.6μs/token，占原模型窗口约0.1003%；寄存器额外每次8拍装载。8拍装载要求每个并行头都能得到16个阈值/拍，32头共512个阈值/拍；共享LUT/输入总线若不足，会增加等待，这里尚未计其供给硬件。服务时间是局部串行工作下界，不是新TPOT，也没有宣称全能隐藏。

128bit/bank不能无代价提供160个新样本。128轮需要64拍写入；160轮情景按读完原128轮后，再写16个2bit字提供32个新样本，合计80拍写、160拍读。该刷新调度尚未做RTL/质量验证。写入价格沿用实测load窗口，不同刷新地址活动可能有差别；64/80写拍还假设上游每拍可供256bit。

如SRAM用**一套共享的Bivium＋阈值库**生成每个头每轮的新样本，再装入32套bank：在同一停钟情景，简单相加并补第二阶段阈值重装，得到面积至少{shared_generation['area55_mm2']:.4f}mm²、平均功率约{shared_generation['average_W']*1000:.3f}mW（片上占比{shared_generation['onchip_power_share_pct']:.3f}%）。还缺128bit暂存打包、搬运/写驱动和门控控制。采用“逐头产128轮→各头并行读128轮→逐头重装阈值并产32轮→并行读32轮”的明确两阶段调度：生成器含两次阈值装载共{shared_generation['generation_service_s']*1000:.5f}ms/token；逐头写入合计{serial_writes_s*1000:.5f}ms，两个读取阶段共{b['sample_read_time_s']*1000:.5f}ms。三者完全不重叠时合计约{shared_generation['no_overlap_service_s']*1000:.5f}ms，约占旧57.445ms的{100*shared_generation['no_overlap_service_s']/T:.2f}%；生成与写入流水可缩短，但本次未验证重叠。一个生成器只给128bit/拍，需两拍形成256bit写字，不能沿用32头都同时得到256bit/拍的理想装载时间。若用物理p-bit生成，应替换这一生成器预算，不能擅自计零。新鲜样本流水/存储相关性、输入概率变化与预存复用仍须验证。

## 是否重要，以及并行度

在这套既有较大随机FFN平台上，前端约2%–3%面积有优化价值，但不支持“它会主导整机功耗”的判断；未停钟带来的持续开销更应优先解决。Bivium和SRAM的端到端胜负还依赖上游生成/质量，不能只比较81与84pJ。

32头全并行是面积较大的配置，不是模型要求的硬件下限。若只配1套128节点引擎供32头轮流用，面积分别约0.03327/0.11890/0.13877mm²；160轮加本地装载的累计服务时间约1.93536/1.93536/2.76480ms/token，工作动态能量大致不变、常驻漏电下降。1/4/8/32并行度和三种空闲动态保留比例均已列在RESULTS.json。需结合QK/V时序选择，不承诺复用的延迟完全重叠。

本占比不能直接移植到更小、更快的纯数字平台；T变短而样本数不变时动态平均功率会上升。未计CIM外围、全局互连和HBM实测价格也限制整机分母。正确下一步是确定允许的采样延迟与任务级停钟接口，再做Bivium和存储方案的匹配统计/集成验证，而不是重跑所有已测模块。

## 证据与复算

RESULTS.json记录全部源文件SHA、模型Git blob、公式、96个情景和代码SHA；源RNG为38322118三seed，寄存器采用既有修复后正setup/hold的12位门控无比较库，小bank采用已有接口修复PT。源端点PWR/外推告警、无后布局寄生等限制沿原报告保留。未把组合这些价格称为集成PT。PRNG按连续保持状态使用，不在每个query重复播种；物理种子供给及刷新策略另计。

复算：`python derive.py WORKSPACE_ROOT PATH_TO_91f68416_ppa_recalibration_RESULTS.json`。源路径见RESULTS.json，原文件可从公开commit取回；脚本校验其Git blob。纯派生参考，不新增数字电路run。
'''
(OUT/'REPORT_ZH.md').write_bytes(report.encode())
print(json.dumps(dict(anchor_area55=anchor['area55_mm2'],rows=[pick(c) for c in labels],shared_generation=shared_generation),ensure_ascii=False,indent=2))
