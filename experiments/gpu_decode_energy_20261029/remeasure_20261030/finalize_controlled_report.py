"""Combine independently sealed warm, cooldown and Nsight observations."""
import argparse,csv,hashlib,json,statistics
from pathlib import Path
from build_controlled_report import parse_collection


def main():
    p=argparse.ArgumentParser();p.add_argument('--collection',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    parse_collection(a.collection,a.report)
    load=lambda name:json.loads((a.report/name).read_text(encoding='utf-8'))
    env=load('raw/ENVIRONMENT.json');penv=load('paired/raw/ENVIRONMENT.json');nenv=load('nsys/ENVIRONMENT.json')
    assert env['uuid_sha256']==penv['uuid_sha256']==nenv['uuid_sha256']
    assert env['prepared_sha256']==penv['prepared_sha256']==nenv['prepared_sha256']
    assert env['revision']==penv['revision']==nenv['revision']
    assert penv['target_start_temperature_C'] is None
    assert load('paired/raw/COMPLETED.json')['status']=='completed'
    assert load('nsys/VALIDATION.json')['all_36_layers_verified']
    labels={'original_eager':'原始 HF 固定forward','original_graph':'原始HF固定forward＋Graph',
            'static_KV_graph':'静态KV＋原SDPA＋Graph','native_greedy':'原始 HF 连续贪心生成'}
    paired=[];integral_errors=[];warm_errors=[]
    for f in (a.report/'raw').rglob('WHOLE*.json'):
        warm_errors.extend(abs(r['power_integral_relative_difference']) for r in json.loads(f.read_text())['repeats']
                           if 'power_integral_relative_difference' in r)
    for context in [2048,8192]:
        summary=load('paired/raw/'+str(context)+'/SUMMARY.json')
        for mode,label in labels.items():
            rows=[load('paired/raw/'+str(context)+'/'+mode+'_'+str(i)+'.json') for i in range(3)]
            for r in rows:
                assert r['thermal_reset']['seconds']>=10 and r['thermal_reset']['pass_target']
                assert r['wall_s']>=(5 if mode=='native_greedy' else 10)
                assert abs(r['energy_J']-r['energy_mJ_per_item']*r['iterations']/1000)<1e-7
                assert abs(r['energy_J']-r['average_W']*r['wall_s'])<1e-7
                if 'power_integral_relative_difference' in r:integral_errors.append(abs(r['power_integral_relative_difference']))
            if mode=='native_greedy':assert len({r['generated_ids_sha256'] for r in rows})==1
            s=summary[mode]
            paired.append(dict(context=context,mode=mode,ms=s['wall_ms_per_item']['mean'],
                J=s['energy_mJ_per_item']['mean']/1000,W=s['average_W']['mean'],
                energy_CV=s['energy_mJ_per_item']['stdev']/s['energy_mJ_per_item']['mean'],
                start_temperature_min_C=min(r['state_before']['temperature_C'] for r in rows),
                start_temperature_max_C=max(r['state_before']['temperature_C'] for r in rows)))
    with (a.report/'PAIRED_WHOLE.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(paired[0]));writer.writeheader();writer.writerows(paired)
    # nsys' official kernel report, NOT projected NVTX range elapsed time.
    with (a.report/'nsys/NVTX_KERNELS.csv').open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        fields=reader.fieldnames
        range_key=next(k for k in fields if k.lower()=='range' or 'nvtx range' in k.lower())
        time_key=next(k for k in fields if 'total time' in k.lower() and '(ns)' in k.lower())
        totals={}
        for row in reader:
            # nsys 2024.6 prefixes domain 0 ranges with an empty domain ':'.
            name=row[range_key]
            if name.startswith(':'):name=name[1:]
            if not name.startswith('qwen3/'):continue
            parts=name.split('/');assert len(parts)==3,name
            key=(int(parts[1]),parts[2]);totals[key]=totals.get(key,0)+float(row[time_key].replace(',',''))/1e6/4
    assert len(totals)==28
    original=load('SUMMARY.json');cross=[]
    for m in original['modules']:
        nsys=totals[(m['context'],m['category'])]
        cross.append(dict(context=m['context'],category=m['category'],nsys_kernel_ms=nsys,
            torch_profiler_kernel_ms=m['kernel_ms'],relative_difference=nsys/m['kernel_ms']-1,
            replay_J=m['replay_J'],replay_W=m['replay_W']))
    with (a.report/'NSYS_MODULES.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(cross[0]));writer.writeheader();writer.writerows(cross)
    report=(a.report/'REPORT_ZH.md').read_text(encoding='utf-8')
    report=report.replace('## 1. 整体实际测量','## 1. 连续长窗口测量（预热阶段）')
    extra=['## 1b. 固定冷却间隔对照（最终整模型参考）','',
      '同一张GPU，校准在冷却前完成；每个窗口前至少空闲10秒，最后五个约1s温度样本跨度≤1°C。四种方式轮换次序、各重复三次，保留实际起始温度；这不是40°C恒温或锁频实验。',
      '', '|上下文|方式|ms/次|J/次|平均W|能量CV|实际起温范围°C|', '|---|---|---:|---:|---:|---:|---:|']
    for r in paired:
        extra.append(f"|{r['context']//1024}K|{labels[r['mode']]}|{r['ms']:.3f}|{r['J']:.3f}|{r['W']:.1f}|{r['energy_CV']*100:.2f}%|{r['start_temperature_min_C']}–{r['start_temperature_max_C']}|")
    extra+=['',f"预热测量的6个同窗计数器/积分对照最大差异 {max(warm_errors)*100:.2f}%；冷却对照18个固定forward窗口最大差异 {max(integral_errors)*100:.2f}%，积分偏低。NVIDIA文档说明现代GPU的powerUsage是1秒平均，冷却后从约65–80W跃迁到工作功率会产生边界响应；这与观察方向相符，但没有外部电表证明全部差异只来自这一项，也未做任意时移修正。两接口同属NVML，不是独立精度认证。[NVML说明](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html)。连续生成另为256步×3，排除prefill，包含argmax和真实缓存增长。",'',
      '初次3441/3442的40°C起点门控均失败，未列为有效配对结果：前者在回温后再次校准；后者证实停止短时加热后，计量准备期间温度快速下降（释放39°C、实际33°C）。失败窗口/快照保留。依据公开温度实验改用固定空闲冷却协议，不把失败数据改名为通过。', '']
    report=report.replace('## 2. 模块时间与隔离回放能量','\n'.join(extra)+'\n## 2. 模块时间与隔离回放能量')
    cross_lines=['## 2b. Nsight Systems独立模块时间核对','',
      '另一个进程仅做CUDA/NVTX跟踪，未用其时长/能量代替无Profiler主结果。官方`nvtx_kern_sum`统计每类实际kernel总时长，除以四次forward；SQLite核对两种上下文全部36层/14类标签。它不是NVTX投影跨度。',
      '', '|模块|2K Nsight ms|8K Nsight ms|', '|---|---:|---:|']
    for category in ['QKV_projection','QK_RMSNorm','RoPE','KV_append','Attention_core','Wo_projection','Layer_RMSNorm',
                     'FFN_gate_up','FFN_SwiGLU','FFN_down','Residual_add','lm_head','Embedding','Final_RMSNorm']:
        cross_lines.append(f"|{category}|{totals[(2048,category)]:.4f}|{totals[(8192,category)]:.4f}|")
    max_nonembedding=max(abs(r['relative_difference']) for r in cross if r['category']!='Embedding')
    cross_lines+=['',f"除约2微秒的Embedding外，其他26项与Torch Profiler的kernel总时间差异均小于1%（最大{max_nonembedding*100:.2f}%）。`NSYS_MODULES.csv`保留逐项差异。两个独立采集的启动/缓存/时钟状态不同，微秒级算子尤其敏感；不据此指定绝对计时精度。", '']
    report=report.replace('## 3. 与公开速度基准比较','\n'.join(cross_lines)+'\n## 3. 与公开速度基准比较')
    conclusions=['## 0. 本次能确认什么','',
      '1. 未发现mJ/J、token次数或平均功率换算错误；同窗计数器/积分及独立时间工具提供一致性证据。几J/token仍出现在重新测量中。',
      '2. 冷却前后以及运行阶段会改变能耗；通用HF的eager路径还对主机发射状态敏感。保留两组，不把全部变化归因于温度，也不把小CV当作绝对精度。',
      '3. 本实现仍慢于公开的成熟GPU引擎。关键差异包括Python发射、GQA头展开、缓存复制及未融合算子；它是通用HF参考，不是最佳GPU性能/能效。',
      '4. 尚无条件完全匹配的公开5090 BF16 Qwen3-4B decode J/token可直接验证绝对能量；速度对照只能核查数量级，不能替代独立电表。','']
    report=report.replace('## 1. 连续长窗口测量（预热阶段）','\n'.join(conclusions)+'\n## 1. 连续长窗口测量（预热阶段）')
    (a.report/'REPORT_ZH.md').write_text(report,encoding='utf-8',newline='\n')
    info=dict(status='completed',same_gpu_verified=True,all_36_layers_verified=True,
        paired_whole=paired,nsys_modules=cross,max_internal_energy_integral_difference=max(integral_errors),
        max_warm_internal_energy_integral_difference=max(warm_errors),max_nonembedding_timing_tool_difference=max_nonembedding,
        no_external_meter=True,unmatched_public_energy_baseline=True)
    (a.report/'FINAL_SUMMARY.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(status='validated',paired=paired,max_internal_delta=max(integral_errors),nsys_groups=len(totals))))


if __name__=='__main__':main()
