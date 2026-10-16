"""Audit measured simulation outputs and generate tables/figures from JSON."""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from run_mapping_optimization import OUTPUT, verify_same_work
from system_decode import ROOT


def conditional_bounds(result):
    c = result['config']; n = c['decode_tokens']; d = c['digital']; w = c['weight_macro']
    sp = c['scratchpad']; r = c['rng']; E = c['sc_engines']; f = c['frequency_hz']
    shape = json.loads((ROOT/'configs/model_config.json').read_text())
    selected = json.loads((OUTPUT/'selection.json').read_text())[str(c['context_tokens'])][result['variant']]
    old = selected['lower_bounds']; energy = result['energy_J']
    h = shape['hidden_size']; m = shape['intermediate_size']
    kv = shape['num_key_value_heads']*(h//shape['num_attention_heads'])
    W = shape['num_hidden_layers']*(h*(h+2*kv)*2+h*h*2+3*h*m)+shape['vocab_size']*h*2
    capacity = w['cache_MiB']*2**20
    cold_min_weights = W+(n-1)*max(0, W-capacity)
    KV = result['traffic']['external_KV_read_logical_bytes']
    write = result['traffic']['external_KV_write_logical_bytes']
    communication = (cold_min_weights+KV)/n/c['external_memory']['bandwidth_GBs']/1e6
    resource = max(communication, old['digital_resource_compute_ms'], old['SC_work_conservation_ms'])
    frozen = max(resource, old['ideal_memory_same_arithmetic_and_RNG_ms'])
    fixed = sum(energy.get(k, 0) for k in ('SC_logic_active', 'digital_MAC', 'digital_vector',
                                          'digital_nonlinear', 'scratch_access', 'weight_resident_prepare'))
    weight_floor = W*n*w['read_pJ_per_byte']*1e-12+cold_min_weights*w['write_pJ_per_byte']*1e-12
    static_power = (w['cache_MiB']*w['leakage_W_per_MiB']+sp['capacity_MiB']*sp['leakage_W_per_MiB']
                    +d['idle_W']+c['control_interconnect_W']+E*w['active_tile_hold_W']
                    +r['sources']*r['source_power_W']+r['fifo_distribution_W'])
    active_engine_s = result['actions'].get('sc_tile_frames', 0)*(c['samples']+1)/f
    memspec = json.loads((ROOT/'dramsys/ddr4_2ch_NoPowerDown.json').read_text())['simulation']['memspec']
    arch = memspec['memarchitecturespec']; power = memspec['mempowerspec']; timing = memspec['memtimingspec']
    # Same formulas as DRAMPower 6.3.1 Calculation_DDR4::E_RD/E_WR.
    burst_time = arch['burstLength']/arch['dataRate']*timing['tCK']
    er = arch['nbrOfDevices']*burst_time*(power['vdd']*(power['idd4r']-power['idd3n'])
                                        +power['vpp']*(power['ipp4r']-power['ipp3n']))
    ew = arch['nbrOfDevices']*burst_time*(power['vdd']*(power['idd4w']-power['idd3n'])
                                        +power['vpp']*(power['ipp4w']-power['ipp3n']))
    policy = 'Staggered' if 'Staggered' in c['external_memory']['configuration'] else 'NoPowerDown'
    device_standby = power['vdd']*power['idd2n']+power['vpp']*power['ipp2n']
    if policy == 'Staggered':
        # Include even self-refresh as a deliberately optimistic state; the
        # selected controller need not be able to reach this lowest-power state.
        device_standby = min(device_standby,
            power['vdd']*power['idd3n']+power['vpp']*power['ipp3n'],
            power['vdd']*power['idd2p']+power['vpp']*power['ipp2p'],
            power['vdd']*power['idd3p']+power['vpp']*power['ipp3p'],
            power['vdd']*power['idd6n']+power['vpp']*power['ipp6n'])
    p_min = arch['nbrOfChannels']*arch['nbrOfRanks']*arch['nbrOfDevices']*device_standby
    command_floor = (cold_min_weights+KV)/64*er+write/64*ew
    def floor(t_ms):
        seconds = t_ms*n/1000
        soc = fixed+weight_floor+static_power*seconds+max(0, E*seconds-active_engine_s)*c['sc_cost']['idle_W_per_engine']
        return (soc+command_floor+p_min*seconds)*1000/n
    return dict(resource_time_lower_bound_ms=resource, frozen_phase_time_lower_bound_ms=frozen,
                ideal_memory_time_ms=old['ideal_memory_same_arithmetic_and_RNG_ms'],
                SC_work_ms=old['SC_work_conservation_ms'], fixed_SC_wave_ms=old['fixed_SC_wave_ms'],
                conditional_cold_communication_ms=communication,
                policy=policy, conditional_energy_lower_bound_mJ=floor(resource),
                frozen_phase_energy_lower_bound_mJ=floor(frozen),
                DDR4_min_standby_W=p_min, RD_increment_pJ_per_64B=er*1e12,
                caveat='conditional bounds for this uncompressed format, SRAM partition, fixed work and bundled DDR4 policy; omit positive ACT/PRE/refresh costs; Staggered floor permits even self-refresh; not achievable schedules or calibrated silicon values')


def main():
    rows = []; audits = {}; all_bounds = {}
    for context, policy in [(2048, 'NoPowerDown'), (8192, 'NoPowerDown'),
                            (2048, 'Staggered'), (8192, 'Staggered')]:
        for variant in ('digital_int8_ffn', 'fixed_sc_exact'):
            prefix = f'{variant}_{context}'
            bp = OUTPUT/'dramsys'/f'{prefix}_before_{policy}.json'
            ap = OUTPUT/'dramsys'/f'{prefix}_after_{policy}.json'
            if not bp.exists() or not ap.exists():
                raise FileNotFoundError(f'Validation incomplete: {prefix} {policy}')
            before = json.loads(bp.read_text()); after = json.loads(ap.read_text())
            audit = verify_same_work(before, after)
            for result in (before, after):
                ext = result['external_memory_model']; traffic = result['traffic']
                burst_bytes = sum(v for k, v in traffic.items() if k.startswith('external_') and k.endswith('_burst_bytes'))
                assert ext['burst_count']*64 == burst_bytes
                assert ext['peak_pending'] <= result['config']['external_memory']['max_pending']
                assert abs(sum(result['time_ns'].values())-ext['end_ns']) <= 1
                assert math.isclose(sum(result['energy_J'].values())*1000/result['config']['decode_tokens'],
                                    result['metrics']['scenario_mJ_per_token'], rel_tol=1e-10)
                for name in ('system_decode.py', 'mapping_decode.py', 'run_mapping_optimization.py', 'zigzag_mapper.py'):
                    assert result['source_hashes'][name] == hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), name
            audit.update(DRAM_burst_conservation=True, DRAM_full_horizon=True, finite_pending=True,
                         local_remote_source_hashes=True)
            key = f'{prefix}_{policy}'; audits[key] = audit
            bm = before['metrics']; am = after['metrics']; n = after['config']['decode_tokens']
            row = dict(context=context, policy=policy, variant=variant,
                before_ms=bm['mean_TPOT_ms'], after_ms=am['mean_TPOT_ms'],
                time_reduction_pct=(1-am['mean_TPOT_ms']/bm['mean_TPOT_ms'])*100,
                before_mJ=bm['scenario_mJ_per_token'], after_mJ=am['scenario_mJ_per_token'],
                energy_reduction_pct=(1-am['scenario_mJ_per_token']/bm['scenario_mJ_per_token'])*100,
                weights_before_MiB=before['traffic']['external_weights_read_burst_bytes']/n/2**20,
                weights_after_MiB=after['traffic']['external_weights_read_burst_bytes']/n/2**20,
                hardware_mm2=am['parameterized_area_mm2'])
            bound = conditional_bounds(after); all_bounds[key] = bound
            assert bound['resource_time_lower_bound_ms'] <= row['after_ms']
            assert bound['frozen_phase_time_lower_bound_ms'] <= row['after_ms']
            assert bound['conditional_energy_lower_bound_mJ'] <= row['after_mJ']
            row.update(time_bound_ms=bound['resource_time_lower_bound_ms'],
                           frozen_phase_bound_ms=bound['frozen_phase_time_lower_bound_ms'],
                           time_gap_pct=(row['after_ms']/bound['resource_time_lower_bound_ms']-1)*100,
                           frozen_phase_gap_pct=(row['after_ms']/bound['frozen_phase_time_lower_bound_ms']-1)*100,
                           energy_bound_mJ=bound['conditional_energy_lower_bound_mJ'],
                           energy_gap_pct=(row['after_mJ']/bound['conditional_energy_lower_bound_mJ']-1)*100)
            rows.append(row)
    (OUTPUT/'DRAMSYS_COMPARISON.json').write_text(json.dumps(rows, indent=2)+'\n')
    (OUTPUT/'LOWER_BOUNDS.json').write_text(json.dumps(all_bounds, indent=2)+'\n')
    (OUTPUT/'verification.json').write_text(json.dumps(audits, indent=2)+'\n')
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (OUTPUT/'DRAMSYS_COMPARISON.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    make_plot(rows)
    best = []
    for context in (2048, 8192):
        for variant in ('digital_int8_ffn', 'fixed_sc_exact'):
            choices = [r for r in rows if r['context'] == context and r['variant'] == variant]
            row = min(choices, key=lambda r:r['after_ms']*r['after_mJ']).copy()
            reference = next(r for r in choices if r['policy'] == 'NoPowerDown')
            row['reference_before_ms'] = reference['before_ms']
            row['reference_before_mJ'] = reference['before_mJ']
            row['total_time_reduction_pct'] = (1-row['after_ms']/reference['before_ms'])*100
            row['total_energy_reduction_pct'] = (1-row['after_mJ']/reference['before_mJ'])*100
            best.append(row)
    (OUTPUT/'BEST_POLICY_COMPARISON.json').write_text(json.dumps(best, indent=2)+'\n')
    write_markdown(rows, best)
    print(json.dumps(rows, indent=2))


def make_plot(rows):
    import os
    cache = OUTPUT/'matplotlib_cache'; cache.mkdir(exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(cache)
    deps = ROOT/'.deps/zigzag385'
    if deps.exists(): sys.path.insert(0, str(deps))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data = [r for r in rows if r['policy'] == 'NoPowerDown']
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    labels = [f"{'Digital' if r['variant'].startswith('digital') else 'p-bit SC'}\n{r['context']//1024}K" for r in data]
    for ax, key, title in [(axes[0], 'time_reduction_pct', 'Decode time'), (axes[1], 'energy_reduction_pct', 'System energy')]:
        bars = ax.bar(range(len(data)), [1-r[key]/100 for r in data], color=['#3265a8', '#df7d38']*2)
        ax.axhline(1, color='#555555', linestyle='--', linewidth=1)
        ax.set_xticks(range(len(data)), labels); ax.set_ylim(0, 1.13)
        ax.set_ylabel('After / before (lower is better)'); ax.set_title(title)
        ax.grid(axis='y', alpha=.2); ax.set_axisbelow(True)
        for bar, row in zip(bars, data):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+.025,
                    f"-{row[key]:.1f}%", ha='center', fontsize=10)
    fig.text(.5, .01, 'Same mixed-ASIC resources; DRAMSys DDR4 NoPowerDown; illustrative costs; no prefill / PHY',
             ha='center', fontsize=8, color='#555555')
    fig.tight_layout(rect=(0, .05, 1, 1)); fig.savefig(OUTPUT/'optimization.png', dpi=180)
    fig.savefig(OUTPUT/'optimization.svg'); plt.close(fig)


def write_markdown(rows, best):
    exhaustive = json.loads((OUTPUT/'exhaustive_verification.json').read_text())
    assert all(r['matches_validated_plan'] and r['coordinate_search_found_same_EDP'] for r in exhaustive.values())
    lines = [
        '# ZigZag接入与固定资源内存调度优化结果', '',
        '日期：2026-10-15。已完成本地映射搜索、同一台研究服务器上的16个真实DRAMSys/SystemC闭环情景，以及结果审计。以下均为参数化架构仿真，包含未标定的片上成本及示例DRAM电流；不代表芯片实测。', '',
        '## 1. 接入了什么', '',
        '采用ZigZag 3.8.5的LOMA与MemoryAllocator，生成五种逻辑GEMV形状的54个合法tile映射，并将循环前缀的权重数据块投影为现有调度器支持的13种DMA粒度。p-bit的4096拍计算、随机服务及重放由原TLM宏成本核算，未套用数字MAC时延。', '',
        '首轮坐标搜索122次，再对所支持空间完整枚举624次：每个上下文数字104点、p-bit208点，覆盖2K/8K、DMA块、pin/bypass、attention块及随机阵列权重提前加载。两个搜索选中同一方案。详细DRAMSys验证选中点的前后与两种电源策略，未对624点全部运行详细外存模型。', '',
        '本适配器保留原有矩阵算术和SC输入tile外循环；目前执行的是DMA阻塞粒度、驻留和预取投影，尚未实现LOMA的任意循环重排或完整编译器。', '',
        '## 2. 相同硬件资源与选中调度', '',
        '- 同一混合ASIC：100MHz，数字单元512 MAC/cycle，8个64×64随机阵列，32个既有均匀随机字源。',
        '- 权重SRAM 16MiB，scratch 1MiB，片上权重Link仍为同一个64GB/s接口；外存仍为原双通道DDR4及原地址映射、队列和FR-FCFS。',
        '- 数字路径也计入8个未使用阵列的待机与32个常开源的能量；两条路径参数化面积均为17.692mm²。它是同一混合芯片上的路线比较，不能当作最优纯数字ASIC的同面积设计搜索。',
        '- 选中：128KiB DMA块、双缓冲、15.75MiB固定驻留lm_head前缀、256KiB权重staging；attention块64 token。权重提前加载可与片上搬运/计算及既有随机供给重叠。',
        '- T=4096、随机字位数、输入流跨输出复用、重放格式、波次数、运算数、活跃计算能量、KV逻辑字节均不变。未新增概率/源共享设计，没有新增模型PPL结论。', '',
        'batch=1；每个情景连续两个decode token，起始缓存为空。结果是含首token冷缓存的两token平均，另在JSON保留first_decode与subsequent_decode。prefill和TTFT未覆盖。', '',
        '## 3. 固定DRAM电源策略的前后对比', '',
        '下表都使用NoPowerDown，隔离普通内存调度收益。能量单位mJ/生成token，时间单位ms/生成token。', '',
        '| 上下文 | 路径 | 时间：前→后 | 时间缩短 | 能量：前→后 | 节能 |',
        '|---|---|---:|---:|---:|---:|',
    ]
    for r in rows:
        if r['policy'] != 'NoPowerDown': continue
        label = '数字INT8权重FFN' if r['variant'].startswith('digital') else '固定权重随机FFN'
        lines.append(f"| {r['context']//1024}K | {label} | {r['before_ms']:.2f} → {r['after_ms']:.2f} | {r['time_reduction_pct']:.2f}% | {r['before_mJ']:.2f} → {r['after_mJ']:.2f} | {r['energy_reduction_pct']:.2f}% |")
    lines += ['', '## 4. 允许在已有两种DRAM策略中选择', '',
        '选择外存低功耗策略属于控制器调度，不改变通道、容量或算术硬件。下表以原NoPowerDown调度为统一起点，在优化后的NoPowerDown/Staggered中按EDP选择。不能将这个总收益全部归因于权重预取。', '',
        '| 上下文 | 路径 | 选中策略 | 时间：原→最终 | 总时间缩短 | 能量：原→最终 | 总节能 |',
        '|---|---|---|---:|---:|---:|---:|']
    for r in best:
        label = '数字' if r['variant'].startswith('digital') else 'p-bit/SC'
        lines.append(f"| {r['context']//1024}K | {label} | {r['policy']} | {r['reference_before_ms']:.2f} → {r['after_ms']:.2f} | {r['total_time_reduction_pct']:.2f}% | {r['reference_before_mJ']:.2f} → {r['after_mJ']:.2f} | {r['total_energy_reduction_pct']:.2f}% |")
    lines += ['', '长流计算期间的DRAM状态管理对p-bit路径有明显影响；数字路径较密集，选中的策略可能不同。示例低功耗电流尚未针对目标器件校准，因此只报告本模型中的结果，不推断所有DRAM都具有相同收益。', '',
        '## 5. 距离下界还有多远', '',
        '资源下界取计算工作守恒与必要外存搬运时间的较大值；外存按实际29.850746GB/s峰值和两token冷启动的最少权重流量计算。它允许理想重叠，通常无法直接达到。', '',
        '固定阶段下界进一步保留本轮未改变的SC波次、数字阶段及随机服务，只将内存时间理想化为零。它用于判断本轮内存调度还能解决多少问题，不适用于改变流长、随机供给或计算图后的设计。差距定义为“实际/下界−1”。', '',
        '| 上下文 | 最终路径 | 最终时间 | 资源下界 | 高于资源界 | 固定阶段界 | 高于固定阶段界 |',
        '|---|---|---:|---:|---:|---:|---:|']
    for r in best:
        label = '数字' if r['variant'].startswith('digital') else 'p-bit/SC'
        lines.append(f"| {r['context']//1024}K | {label} | {r['after_ms']:.2f} | {r['time_bound_ms']:.2f} | {r['time_gap_pct']:.2f}% | {r['frozen_phase_bound_ms']:.2f} | {r['frozen_phase_gap_pct']:.2f}% |")
    lines += ['', 'p-bit的76608个tile帧在8阵列下给出392.33ms工作量界；固定波次为411.01ms，保留随机服务和数字阶段后的理想无访存时间在2K为448.66ms。将472ms与392ms之间的全部差距归因于内存，会夸大内存调度的剩余机会。', '',
        '能量界采用保持不变的计算/必要片上动作、冷启动最少权重读写、DRAMPower的RD/WR增量式以及最低驻留功率。忽略正的ACT/PRE/刷新等开销；Staggered界还乐观允许最低自刷新功率，因此是条件性底线，并非可实现设计点。', '',
        '| 上下文 | 最终路径 | 最终能量mJ | 条件能量下界mJ | 高于能量界 |',
        '|---|---|---:|---:|---:|']
    for r in best:
        label = '数字' if r['variant'].startswith('digital') else 'p-bit/SC'
        lines.append(f"| {r['context']//1024}K | {label} | {r['after_mJ']:.2f} | {r['energy_bound_mJ']:.2f} | {r['energy_gap_pct']:.2f}% |")
    lines += ['', '## 6. 收益来源与结论', '',
        '平均权重外存流量从642.91降到635.03MiB/token，仅约1.23%；KV流量没有减少。因此，主要加速来自发射时刻和流水重叠，而非大量消除了权重字节。DRAM等待时长与状态改变则影响总能量。', '',
        '普通内存调度确实能显著加强数字基线。当前p-bit映射在优化后仍较慢；进一步主攻应是达到目标质量所需的流长、计算/源供给流水与有效并行，而不能假定更换mapper会消除长流计算工作量。', '',
        '本轮保留64×64，因为现有核心功耗标定只支持该原语；访存块已独立搜索，不要求算子矩阵等于64×64。即使理想消除当前波次碎片，纯SC时间也只是从411.01降到392.33ms。改变物理阵列形状时需要重新约束总并行资源、归约、互连与面积，不能直接沿用64×64单价。', '',
        '## 7. 验证与局限', '',
        '- 5项新增架构检查、原11项整模型检查和8项工作台检查通过。16次DRAMSys结果按8组前后核对运算、源服务/重放、资源、能量求和、burst字节、有限pending、完整计费时域及本地/远端源码hash。',
        '- 原调度器与旧结果未改写，新调度均为独立opt-in模块。',
        '- 624点枚举只覆盖适配器支持的有限空间；详细DRAM验证的是选中映射和两种策略。未声称全局最优，尚未搜索任意循环、KV布局、地址映射或完整SRAM bank/端口争用。',
        '- 仍沿用原有聚合SRAM Link、数字宏时序和参数化能量。DRAM vddq=0，接口不完整；PHY、CTS、host、prefill未计。原有固定权重SC硬件语义尚无独立匹配PPL，因此这里是调度比较。', '',
        '## 8. 文件入口', '',
        '- [汇总CSV](DRAMSYS_COMPARISON.csv)、[两种策略的完整比较](DRAMSYS_COMPARISON.json)、[最终策略选择](BEST_POLICY_COMPARISON.json)。',
        '- [下界参数与公式数值](LOWER_BOUNDS.json)、[8组审计](verification.json)、[624点搜索核验](exhaustive_verification.json)、[完整搜索表](exhaustive_search.csv)。',
        '- [LOMA映射](zigzag/loma_candidates.json)、[选中方案及初筛](selection.json)。',
        '- [优化图](optimization.png)、[矢量图](optimization.svg)。',
        '- 调度与复现入口见../../MAPPING_OPTIMIZATION_ZH.md。', '',
        '工具来源：[ZigZag作者仓库](https://github.com/KULeuven-MICAS/zigzag)；[DRAMSys](https://github.com/tukl-msd/DRAMSys)；[DRAMPower](https://github.com/tukl-msd/DRAMPower)。',
    ]
    (OUTPUT/'RESULTS_ZH.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
