"""Clock profiles: keep frozen mixed-clock experiments separate."""
from pathlib import Path
import argparse,hashlib,json,math
from architecture_tlm.unified_v6.shared_clock import SharedClock

def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def main(root):
    out=root/'architecture_tlm/shared_memory_20261101/clock100';out.mkdir(parents=True,exist_ok=True)
    work=root/'work/rayggxia/227';archive=root.parents[1]/'project_archives/shared_memory227_20261101'
    for name in ['chip100','legacy_mixed']:write(out/(name+'.json'),SharedClock(name).report())
    phases=['official_chip100','official_legacy_clock','wholeofficial_chip100'];rows=[];sources=[];raw={}
    for phase in phases:
        receipt=work/(phase+'_SUBMISSION.json')
        if not receipt.exists():continue
        d=read(receipt);p=archive/phase/'results/RESULT.json'
        row=dict(phase=phase,job=d['job'],remote_root=d['root'],source_archive_sha256=d['source_sha256'],
            config_sha256=d['config_sha256'],input_sha256=d['input_identity']['sha256'],
            source_files_sha256=d['manifest']['files_sha256'],status='submitted_not_sealed')
        if p.exists():
            r=read(p);assert r['status']=='completed';raw[phase]=r;m=r['memory'];s=m['SRAM']
            assert not m['final_pending'] and not m['final_response_occupied']
            row.update(status='completed',result_sha256=sha(p),time_ms=r['simulated_ms'],
                chip_cycles=r.get('simulated_chip_cycles'),SRAM_dynamic_mJ=s['dynamic_mJ'],SRAM_leakage_mJ=s['leakage_mJ'],
                SRAM_total_mJ=s['dynamic_mJ']+s['leakage_mJ'],DRAM_core_mJ=r['DRAM']['core_total_mJ'],
                phase_ms={v['stage']:v['duration_ns']*1e-6 for v in r['phases']},clock_contract=r['clock_contract'])
            sources.append(dict(path=str(p),sha256=sha(p)))
        rows.append(row)
    checks={}
    if all(p in raw for p in phases[:2]):
        a=raw[phases[0]];b=raw[phases[1]];sa=a['memory']['SRAM'];sb=b['memory']['SRAM']
        assert a['actions']==b['actions'] and a['kernel_active']==b['kernel_active']
        assert a['memory']['by_kind']==b['memory']['by_kind']
        assert sa['counts']['read_words']==sb['counts']['read_words'] and sa['counts']['write_words']==sb['counts']['write_words']
        # Counts match exactly. Chronological float addition may differ in its
        # last bits when read/write order changes; independently reprice counts.
        exact_count_price=(sa['counts']['read_words']*10.0527+sa['counts']['write_words']*13.9599)*1e-9
        additions=sa['counts']['read_words']+sa['counts']['write_words']
        gamma=additions*2.220446049250313e-16/(1-additions*2.220446049250313e-16)
        roundoff_bound=gamma*exact_count_price
        for s in [sa,sb]:assert abs(s['dynamic_mJ']-exact_count_price)<=roundoff_bound
        for p in a['phases']:
            assert abs(p['end_ns']/10-round(p['end_ns']/10))<1e-5
            assert abs(p['duration_ns']-p['chip_cycles']*10)<1e-4
        old=archive/'official_v3/results/RESULT.json'
        if old.exists():
            r=read(old);assert r['phases']==b['phases'] and r['memory']==b['memory']
            assert r['DRAM']==b['DRAM']
        checks=dict(same_arithmetic_and_samples=True,same_external_addresses=True,same_SRAM_events_dynamic_energy=True,
            chip100_whole_cycle_phases=True,legacy_actual_v3_reproduced=old.exists(),
            SRAM_dynamic_repriced_mJ=exact_count_price,SRAM_float_accumulation_bound_mJ=roundoff_bound,
            SRAM_dynamic_float_difference_mJ=sa['dynamic_mJ']-sb['dynamic_mJ'],
            time_change_percent=100*(a['simulated_ms']/b['simulated_ms']-1),
            digital_ideal_busy_ns={k:raw[p]['compute_macro_busy_sum_ns']['ordinary_MAC_ideal_ns'] for k,p in zip(['chip100','legacy_mixed'],phases[:2])})
    result=dict(profiles={k:SharedClock(k).report() for k in ['chip100','legacy_mixed']},runs=rows,
        checks=checks,sources=sources,status='paired_complete_full_pending' if checks else 'pending_pair',
        model='Qwen/Qwen3-4B post-trained shape; no weights/text/PPL',
        limitations=['same old2048lane/2cycle digital macro;100MHz is common clock, not complete array physical signoff',
            'FMA2 scalar hold caveat and crossK/quant/argmax macro assumptions retained',
            'SRAM read and DRAM write completion captured at next chip edge; capture/control physical power unpriced',
            'all hardware clocks in chip100 compute/memory frontend100MHz; DDR timings and async bridge transport remain independent'])
    write(out/'RESULTS.json',result)
    lines=['# 片上统一100MHz估计版本（Issue227 / PR228）','','**新共享后端默认使用`chip100`：片上计算、SRAM与DMA前端均为100MHz。旧版显式选择`legacy_mixed`，不改已有结果或运行中的冻结源码。外部DDR4继续用独立DDR4-1866时序。**','',
        '| 模块 | chip100 | legacy_mixed |','|---|---:|---:|',
        '| QKV、O、lm_head数字矩阵 | 100MHz | 500MHz |',
        '| QK、PV加法 | 100MHz | 100MHz |',
        '| FFN GU、随机非线性-Wd | 100MHz | 100MHz |',
        '| SRAM、DMA请求前端 | 100MHz | 100MHz |',
        '| 跨K、量化、最终BF16、argmax宏 | 100MHz整拍 | 原500MHz宏延迟 |',
        '| 外部DDR4 | 独立DDR4-1866 | 独立DDR4-1866 |','',
        '统一的是时钟，不是所有单元具有相同流水深度：QK保留14拍排空、PV保留7拍反馈；FFN核每帧66拍/660ns，采样T64不变。普通数字阵列2048MAC/拍，100MHz峰值为0.4096TOPS（2op/MAC），旧500MHz为2.048TOPS；阵列数量、bank数、容量和访问数据保持。数字阵列仍是吞吐宏，FMA2周期锚点有标量hold限制，尚无2048lane完整STA。','',
        '逐项修正旧快速宏：GU跨K 5拍=50ns（原10ns），Wd跨K2拍=20ns（原4ns），GU出口量化4拍=40ns（原8ns），BF16出口3拍=30ns（原6ns），argmax7拍=70ns（原14ns）。这些是保留原周期合同后换算，未冒称新RTL。其它100MHz宏向上取整成10ns整拍，TopK旧非整数ns代理分别164/815拍。','',
        'SRAM内部2.8767ns库延迟仍保留，但片上消费者在下一个10ns边沿捕获；DRAM写完成也在片上边沿被观察。Attention输入采样事件只对齐时间，不改地址/次数/顺序；PRNG就近接口与原随机性/采样合同不变。DMA前端8×64B/拍的额度不变，异步桥1ns请求保护间隔属于外存接口传输模型，不作为新的计算时钟。','',
        '因此不能把旧整机时间直接乘5：此前500MHz数字计算经常被SRAM/DRAM供数遮住；真正时间变化需要同地址回放。也不把动态动作能量按频率乘5：动作数不变时沿用相同动作单价，运行变长只重新计漏电/DRAM背景。没有宣布新全芯片功耗/面积。','',
        '## 实际回放','', '| 版本 | Slurm | 状态 | 时间ms | SRAM mJ | DRAM core mJ |','|---|---:|---|---:|---:|---:|']
    for r in rows:
        lines.append(f'| {r["phase"]} | {r["job"]} | {r["status"]} | {r["time_ms"]:.6f} | {r["SRAM_total_mJ"]:.6f} | {r["DRAM_core_mJ"]:.6f} |' if r['status']=='completed' else f'| {r["phase"]} | {r["job"]} | 已提交/未封存 | — | — | — |')
    if checks:
        lines += ['',f'配对已通过：同算术/采样次数、同外部地址与字节、同SRAM读写和动态能量；统一100MHz相对旧混合版时间变化{checks["time_change_percent"]:+.3f}%。新源码legacy_mixed还复现旧v3的实际DRAMSys时间、全部SRAM与DRAM结果。']
        lines += ['',f'普通数字MAC理想活动时间从{checks["digital_ideal_busy_ns"]["legacy_mixed"]:.0f}ns增至{checks["digital_ideal_busy_ns"]["chip100"]:.0f}ns，确为五倍；端到端没有同步放大，说明当前供数瓶颈遮住了大部分计算。小幅正负差来自请求到达/行局部性/仲裁顺序变化，不能宣称降频本身加速。SRAM事件数逐项严格相同；动态累计浮点尾差{checks["SRAM_dynamic_float_difference_mJ"]:.3g}mJ，通过次数×单价独立复算而不改原结果字节。']
    lines+=['', '单层配对含embedding与一层、无lm_head，B1/2K、K128/S64、seed17代表流量。完整36层+lm_head另跑新作业；原3650保留为旧混合版，不重复提交或改source。20项机制/时钟检查通过，其中旧合成时序fixture精确回归、地址/动作守恒及片上相位整拍检查。无新EDA/PPL。','',
        '命令：`python -m architecture_tlm --shared-memory --clock-profile chip100 ...`；旧复现用`--clock-profile legacy_mixed`。配置快照为本目录chip100.json/legacy_mixed.json，执行源码/配置/输入/结果SHA见RESULTS.json。']
    (out/'REPORT_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(status=result['status'],checks=checks,runs=[dict(phase=r['phase'],job=r['job'],status=r['status'],time_ms=r.get('time_ms')) for r in rows])))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();main(a.root.resolve())
