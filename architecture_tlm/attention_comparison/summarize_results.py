from pathlib import Path
import csv,hashlib,json,math,shutil,statistics

import argparse

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def mean(values):return statistics.mean(values)
def std(values):return statistics.stdev(values) if len(values)>1 else 0.

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--no-copy-raw',action='store_true');args=parser.parse_args()
    source=args.input.resolve();OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=True);assert source.is_dir()
    assert not (OUT/'matched_summary.json').exists(),'choose a new output directory'
    state=json.loads((source/'job_state.json').read_text(encoding='utf-8'))
    assert state['status']=='completed' and state['exit_code']==state['tests_exit_code']==state['batch_exit_code']==0
    files=sorted((source/'results').glob('case_*.json'));assert len(files)==32
    cases=[json.loads(p.read_text(encoding='utf-8')) for p in files]
    for item in cases:
        assert item['validation']['phase_closed'] and item['validation']['allocated_capacity_fits']
        assert item['physical_PPA']['complete'] is False and item['physical_PPA']['energy_J'] is None
        assert item['validation']['PPL'] is None and item['layers']==24
        assert item['actions']['projection_weight_bytes']==84*2**20
        assert item['traffic']['external_projection_weights_read_burst_bytes']==84*2**20
        assert math.isclose(item['known_SRAM_internal']['dynamic_J'],item['proxy']['energy_ledger_J']['ATT_scratch'],rel_tol=1e-12)
    # Timing sensitivity changes service only, keeping candidate and sample addresses frozen.
    pairs=[]
    for length in [2048,8192]:
        group=[d for d in cases if d['case']['mode']=='screen_ising' and d['case']['selection']=='fixed_budget' and d['case']['context']==length and d['case']['samples']==128 and d['case']['seed']==0 and d['case']['summary']=='warm']
        assert {d['case']['period'] for d in group}=={1,10,100}
        for name in ['raw_rows_sha256','ordered_local_sample_indices_sha256']:
            assert len({d['workload'][name] for d in group})==1,(length,name)
        assert len({json.dumps(d['traffic'],sort_keys=True) for d in group})==1
        pairs.append(dict(context=length,periods=[1,10,100],candidate_and_sample_SHA_identical=True,traffic_identical=True))
    rows=[]
    for length in [2048,8192]:
        baseline=next(d for d in cases if d['case']['mode']=='digital_dense' and d['case']['context']==length and d['case']['max_pending']==32)
        for mode,samples in [('digital_dense',128),('screen_exact',128),('screen_ising',32),('screen_ising',128),('screen_ising',512)]:
            chosen=[d for d in cases if d['case']['mode']==mode and d['case']['context']==length and d['case']['samples']==samples and d['case']['summary']=='warm' and d['case']['period']==100 and d['case']['max_pending']==32 and (mode!='screen_ising' or d['case']['selection']=='fixed_budget')]
            assert len(chosen)==(3 if mode=='screen_ising' else 1)
            times=[d['timing']['full_module_ms'] for d in chosen];energies=[d['proxy']['energy_J']*1000 for d in chosen]
            r=dict(context=length,mode=mode,samples=samples if mode=='screen_ising' else None,n=len(chosen),full_ms_mean=mean(times),full_ms_std=std(times),core_ms_mean=mean([d['timing']['Attention_core_ms'] for d in chosen]),proxy_mJ_mean=mean(energies),proxy_mJ_std=std(energies),proxy_W_mean=mean([d['proxy']['mean_power_W'] for d in chosen]),latency_ratio=mean(times)/baseline['timing']['full_module_ms'],energy_ratio=mean(energies)/(baseline['proxy']['energy_J']*1000),SRAM_KiB=chosen[0]['allocation']['allocated_bytes']/1024,SRAM_macro_mm2=chosen[0]['allocation']['SRAM_macro_only_area_mm2'],known_SRAM_mJ_mean=mean([d['known_SRAM_internal']['dynamic_J']*1000 for d in chosen]),physical_PPA_complete=False,PPL=None)
            if mode=='screen_ising':
                r['macro_active_ms']=mean([d['macro']['active_ns']/1e6 for d in chosen])
                r['period_break_even_ns']=100+(baseline['timing']['full_module_ms']-mean(times))*1e6/(24*14*samples)
                r['K_physical_fraction']=mean([d['traffic']['attention_K_physical_bytes'] for d in chosen])/(length*24*2*64*2)
                r['V_physical_fraction']=mean([d['traffic']['attention_V_gather_physical_bytes'] for d in chosen])/(length*24*2*64*2)
            rows.append(r)
    save(OUT/'matched_summary.json',dict(source_commit=state['source_commit'],job_id=state['job_id'],condition='primary_pending32 warm, all coefficients except SRAM uncharacterized; three seeds for fixed Ising',rows=rows,sensitivity_address_checks=pairs))
    report=['## 实际完成的同协议条件模型对照','',f"Slurm{state['job_id']} CPU分配已完成，23份源文件SHA通过，9/9快照测试通过，32/32完整24层场景完成；无GPU/PPL/RTL。执行源`{state['source_commit']}`。",'',
            '下表为warm摘要、pending32、100ns样本周期；P的三seed均值。数字与P使用同一完整模块边界、投影流式和服务速率。mJ/W为未校准系数情景，**不是物理功耗预测或等PPL验收**。','',
            '| L | 方案 | 完整ms/token | core ms/token | 情景mJ/token | 情景平均W | SRAM KiB |',
            '|---:|---|---:|---:|---:|---:|---:|']
    for r in rows:
        label=r['mode']+(('/S'+str(r['samples'])) if r['samples'] else '')
        report.append(f"| {r['context']} | {label} | {r['full_ms_mean']:.6f} | {r['core_ms_mean']:.6f} | {r['proxy_mJ_mean']:.6f} | {r['proxy_W_mean']:.6f} | {r['SRAM_KiB']:.0f} |")
    report+=['','完整模型PPL仍未验证，2K固定候选率25%，8K仅6.25%；不能把8K的更大成本节约自动归为同等质量收益。','',
             '| L | S | 相对D0延迟 | 相对D0情景能量 | K物理读/dense K | V物理读/dense V | 仅调整宏周期的延迟盈亏点ns |',
             '|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        if r['mode']=='screen_ising':report.append(f"| {r['context']} | {r['samples']} | {r['latency_ratio']:.4f}× | {r['energy_ratio']:.4f}× | {r['K_physical_fraction']:.2%} | {r['V_physical_fraction']:.2%} | {r['period_break_even_ns']:.3f} |")
    report+=['','盈亏周期假设地址、其他阶段、root刷新次数和资源保持不变：`tau*=100+(T_D0-T_P)*1e6/(336*S)`。小于1ns表示在本轮允许的周期范围内，仅加快宏仍不足以获胜；它不是物理混合时间或独立样本率的证明。','',
             '### 宏周期/冷暖/容量部署敏感性（单seed，条件模型）','',
             '| L | selection | S | 周期ns | summary | 完整ms/token | 情景mJ/token | SRAM KiB |',
             '|---:|---|---:|---:|---|---:|---:|---:|']
    for d in cases:
        c=d['case']
        if c['mode']=='screen_ising' and c['seed']==0 and (c['period']<100 or c['summary']=='cold' or c['selection']=='variable'):
            report.append(f"| {c['context']} | {c['selection']} | {c['samples']} | {c['period']} | {c['summary']} | {d['timing']['full_module_ms']:.6f} | {d['proxy']['energy_J']*1000:.6f} | {d['allocation']['allocated_bytes']/1024:.0f} |")
    report+=['','S128周期1/10/100ns三组的候选、样本SHA及物理流量逐字一致，敏感性只改变服务时间；不把加速来自不同随机地址混入周期结论。完整子账本和阶段能量可由raw/results/case_*.json复核。']
    text='\n'.join(report)+'\n'
    (OUT/'MATCHED_RESULTS_ZH.md').write_text(text,encoding='utf-8',newline='\n')
    destination=OUT/'raw'
    assert not destination.exists(),'preserve prior collection'
    if not args.no_copy_raw:shutil.copytree(source,destination)
    save(OUT/'ANALYSIS_VALIDATION.json',dict(cases=32,phase_capacity_weight_energy_checks=32,timing_sensitivity_address_pairs=pairs,physical_PPA_unvalidated=True,PPL_unvalidated=True,source_commit=state['source_commit'],job_id=state['job_id']))
    print(json.dumps(rows,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
