"""Compare completed sealed scheduling runs. No latency or energy is invented."""
import hashlib,json,statistics,sys
from pathlib import Path
R=Path(__file__).resolve().parents[3];D=R/'architecture_tlm/scheduling_v2_20261027';W=R/'work/jieruiz/186'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def sumbytes(x):return sum(v for k,v in x.items() if k.endswith('_physical_bytes'))
def work(x):
    return {k:v for k,v in x.items() if k not in {'dram_background_ns','digital_idle_ns','sc_idle_ns','control_interconnect_ns','uncalibrated_HBM_system_ns'} and not (k.startswith('rng_') and ('clock' in k or 'idle' in k))}

def main():
    source=read(W/'SCHEDULE_V2_SUBMISSION.json');matrix=read(D/'MATRIX.json')['cases'];runs=[]
    for index,case in enumerate(matrix):
        p=D/'results'/('case_'+str(index));m=read(p/'MANIFEST.json')
        assert m['status']=='completed' and m['case']==case
        for name in ['RESULT_SUMMARY.json','EXECUTION.json']:assert sha(p/name)==m['files'][name]['sha256']
        r=read(p/'RESULT_SUMMARY.json');assert r['execution_commit']==source['commit']
        assert r['model']['num_hidden_layers']==36 and r['config']['ffn']['samples']==64 and r['config']['ffn']['nonlinear_samples']==128
        runs.append(r)
    a=runs[0];rows=[];checks=[]
    # Same-seed mathematical transactions/address choices are identical.
    for index,b in enumerate(runs):
        c=b['config'];f=b['FFN_contract']
        for key in ['core_hz','macs_per_cycle','vector_lanes','nonlinear_lanes','weight_chunk_bytes','digital_weight_chunk_bytes']:
            assert c[key]==a['config'][key],key
        for key in ['capacity_bytes','banks','fabric_GBs','clock_hz']:assert c['sram'][key]==a['config']['sram'][key]
        assert c['ffn']==a['config']['ffn']
        assert f['local_state']==a['FFN_contract']['local_state']
        for key in ['logical_job_order_sha256','logical_frame_order_sha256']:assert f['local_pipeline'][key]==a['FFN_contract']['local_pipeline'][key]
        assert b['FFN_activity']==a['FFN_activity']
        if c['seed']==0:
            assert b['DRAM']['traffic']==a['DRAM']['traffic']
            assert b['SRAM']['traffic']==a['SRAM']['traffic']
            assert b['attention_activity']==a['attention_activity']
            # Identify time-related RNG endpoint bookkeeping separately.
            diff={k:[a['actions'].get(k,0),b['actions'].get(k,0)] for k in set(a['actions'])|set(b['actions']) if a['actions'].get(k,0)!=b['actions'].get(k,0)}
            checks.append(dict(index=index,same_seed_work_identical=work(a['actions'])==work(b['actions']),changed_actions=diff))
            assert work(a['actions'])==work(b['actions']),diff
        phase=b['phase_ns'];ffn=sum(v for k,v in phase.items() if k.startswith('FFN_') or k.startswith('ffn_'))/1e6
        rows.append(dict(index=index,name=b['case']['name'],seed=c['seed'],TPOT_ms=b['metrics']['TPOT_ms'],FFN_ms=ffn,
            ordinary_projection_ms=sum(phase.get(k,0) for k in ['QKV_projection','O_projection','lm_head_and_argmax'])/1e6,
            attention_ms=phase['attention_core']/1e6,DRAM_bytes=sumbytes(b['DRAM']['traffic']),
            SRAM_bytes=sumbytes(b['SRAM']['traffic']),SRAM_reserved_bytes=b['SRAM']['reserved_peak_bytes'],
            local_weight_bytes=f['local_state']['weight_hold_bytes'],priced_subtotal_mJ=b['metrics']['priced_subtotal_mJ_per_token'],
            percent_time_reduction=100*(1-b['metrics']['TPOT_ms']/a['metrics']['TPOT_ms']),speedup=a['metrics']['TPOT_ms']/b['metrics']['TPOT_ms'],
            calendar=b.get('schedule_v2'),SC_pipeline_counts=f['local_pipeline']['counts'],wall_seconds=b['wall_seconds']))
    old=read(R/'architecture_tlm/clock500_resource_20261026/results/case_4/RESULT_SUMMARY.json')
    baseline_delta=a['metrics']['TPOT_ms']-old['metrics']['TPOT_ms'];assert abs(baseline_delta)<1e-6
    combined=[rows[i] for i in [4,5,6]]
    result=dict(scope='7 completed full36-layer Qwen3-4B synthetic decode/2K fixed resource; scheduling only; no PPL or measured chip PPA',
        execution_commit=source['commit'],baseline_reproduced_ms_delta=baseline_delta,checks=checks,rows=rows,
        combined_mean_ms=statistics.mean(x['TPOT_ms'] for x in combined),combined_std_ms=statistics.stdev(x['TPOT_ms'] for x in combined),
        combined_min_ms=min(x['TPOT_ms'] for x in combined),combined_max_ms=max(x['TPOT_ms'] for x in combined),
        unknown='Complete energy/area incl control, interconnect, HBM and clock distribution remain uncalibrated; priced subtotal is not total')
    dump(D/'COMPARISON.json',result)
    text=['# 随机版固定资源调度优化结果','',
        'Issue186/PR192；Qwen3-4B后训练形状，36层/B1/2K，含lm_head。执行'+source['commit']+'，7项均completed并封存SHA核验。',
        '', '本轮保持500MHz、32个64×64随机阵列、GU64/NL128、8MiB/512bank/512GB/s片上SRAM与同一标准HBM时序。Attention仍为筛选＋准确Softmax＋PV采样；主比较均不开门控。',
        '', '| 方案 | 整机ms/token | FFN ms | 普通投影/lm_head ms | 较原调度时间减少 |', '|---|---:|---:|---:|---:|']
    labels=['原调度seed0','只开普通矩阵预填充','只开SC跨窗口装载','只改资源就绪日历','三项组合seed0','三项组合seed1','三项组合seed2']
    for label,row in zip(labels,rows):text.append(f"| {label} | {row['TPOT_ms']:.4f} | {row['FFN_ms']:.4f} | {row['ordinary_projection_ms']:.4f} | {row['percent_time_reduction']:.2f}% |")
    text+=['',f"组合三seed平均{result['combined_mean_ms']:.4f}ms/token，标准差{result['combined_std_ms']:.4f}ms。原调度与旧封存64.411ms情景差{baseline_delta:.12g}ms，复现通过。",'',
        '同seed算术、随机抽样需求、FFN逻辑帧/恢复顺序、SRAM/DRAM物理字节相同；各情景计算资源、SRAM容量/接口和本地数据状态相同。没有新增数据bank、计数器或第二套SC计算资源；就绪仲裁控制的具体PPA仍待后续校准。', '',
        '资源日历只对已有有限tile前瞻利用空隙，外存仍是原单macro actor/批间排空；本轮没有声称完成跨描述符并发、SRAM逐beat仲裁或SC计算/恢复解耦。', '',
        '动态动作不变时，调度提速本身不会同比减少计算和访存动态能量；总时长缩短可减少开钟空闲/背景/泄漏。当前priced_subtotal不含完整HBM/CIM/控制/时钟树，不能当整机功耗或能效比。后续PPA回填保留同动作边界。', '',
        '本轮是事务时序/动作模型，没有新模型PPL、GPU性能或RTL/PT。数字算子L/II仍沿原参数来隔离调度影响；后续按文献/实库校准另做参数情景。', '',
        '复现：先collect_schedule_v2.py核远端completed和原件SHA，再analyze_schedule_v2.py重新生成本报告。具体各动作变化、资源日历命中数和原件SHA见COMPARISON.json与results/。']
    (D/'RESULTS_ZH.md').write_text('\n'.join(text)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'rows':len(rows),'baseline_ms':rows[0]['TPOT_ms'],'combined_ms':result['combined_mean_ms'],'baseline_reproduced':True}))
if __name__=='__main__':main()
