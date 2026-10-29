"""Summarize sealed GPU measurements; never infer in-situ energy from kernel time."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

LABELS={
 'Embedding':'词嵌入','QKV_projection':'Q/K/V投影','QK_RMSNorm':'Q/K归一化',
 'RoPE':'RoPE','KV_append':'KV追加','Attention_core':'融合QK＋Softmax＋PV',
 'Wo_projection':'Attention输出投影','Layer_RMSNorm':'层归一化',
 'FFN_gate_up':'FFN gate/up投影','FFN_SwiGLU':'SiLU＋逐元素乘法',
 'FFN_down':'FFN down投影','Residual_add':'残差相加',
 'Final_RMSNorm':'最终归一化','lm_head':'词表投影'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_bytes())
def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def mean(result,key):return result['summary'][key]['mean']
def dev(result,key):return result['summary'][key]['stdev']

def cpu_kernel_rows(rows,expected=LABELS):
    selected=[r for r in rows if r['CPU_range_ms_per_decode']>0]
    result={r['category']:r for r in selected}
    assert len(result)==len(selected), 'duplicate CPU range categories'
    assert set(result)==set(expected), 'missing or extra CPU range categories'
    return result

def verify(root):
    done=read(root/'COMPLETED.json')
    assert done['status']=='completed' and done['contexts']==[2048,8192]
    assert sha(root/'ARTIFACT_MANIFEST.json')==done['artifacts_manifest_sha256']
    for name,item in read(root/'ARTIFACT_MANIFEST.json').items():
        file=root/name
        if file.is_file():assert sha(file)==item['sha256'] and file.stat().st_size==item['bytes']
        else:assert file.name in ['TRACE.json','INSTALLED_FORWARD_SOURCE.json']
    return done

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--tlm',type=Path)
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    done=verify(a.raw);provenance=read(a.raw/'PROVENANCE.json')
    assert provenance['model_id']=='Qwen/Qwen3-4B' and provenance['batch']==1
    assert done['source_sha256']==provenance['source_sha256']
    whole_rows=[];module_rows=[];contexts={};short=[]
    report=['# RTX5090上的Qwen3-4B decode实测（Issue212）','',
      '正式Slurm3399已封存，全部原始文件在服务器核验SHA。后训练版Qwen3-4B、B1、BF16、原生SDPA；prefill不计入。以下均为本次真实GPU测量，不是TLM或TDP推算。','',
      '## 整段decode与forward','',
      '|上下文|执行方式|ms/token 或 ms/forward|mJ/token 或 mJ/forward|平均W|',
      '|---|---|---:|---:|---:|']
    for context in done['contexts']:
        folder=a.raw/f'context_{context}';summary=read(folder/'SUMMARY.json')
        assert summary['status']=='completed' and summary['all_36_layers_covered'] and summary['capture_logits_bitwise_equal']
        context_results={}
        for filename,label in [('NATIVE_CONTINUOUS_DECODE','原生连续decode'),
             ('FIXED_CONTEXT_DECODE','固定上下文forward'),
             ('CUDA_GRAPH_FIXED_CONTEXT_DECODE','CUDA Graph固定forward')]:
            result=read(folder/(filename+'.json'))
            if filename.startswith('CUDA_GRAPH'):assert result['status']=='completed' and result['logits_bitwise_equal']
            row={'context':context,'execution':filename,'ms_mean':mean(result,'wall_ms_per_item'),
              'ms_stdev':dev(result,'wall_ms_per_item'),'energy_mJ_mean':mean(result,'energy_mJ_per_item'),
              'energy_mJ_stdev':dev(result,'energy_mJ_per_item'),'average_W_mean':mean(result,'average_W'),
              'average_W_stdev':dev(result,'average_W'),'minimum_window_s':min(r['wall_s'] for r in result['repeats']),
              'repeats':len(result['repeats'])}
            assert row['repeats']==3
            whole_rows.append(row);context_results[filename]=row
            report.append(f"|{context}|{label}|{row['ms_mean']:.3f} ± {row['ms_stdev']:.3f}|{row['energy_mJ_mean']:.1f} ± {row['energy_mJ_stdev']:.1f}|{row['average_W_mean']:.1f}|")
        profile=read(folder/'TIME_PROFILE.json')
        inventory=read(folder/'INVENTORY.json')
        # Kineto also emits same-named CUDA user-annotation ranges. Their
        # duration includes stream gaps and is not the associated kernel sum.
        # Frozen 3399 saved both kinds without a device tag. A CPU range has
        # positive CPU time; only its device_time_total is the kernel sum.
        times=cpu_kernel_rows(profile['rows'])
        for category in LABELS:
            result=read(folder/('REPLAY_'+category+'.json'))
            row={'context':context,'category':category,'label':LABELS[category],
              'GPU_kernel_ms_per_decode':times[category]['GPU_kernel_ms_per_decode'],
              'isolated_replay_energy_mJ_mean':mean(result,'energy_mJ_per_item'),
              'isolated_replay_energy_mJ_stdev':dev(result,'energy_mJ_per_item'),
              'isolated_replay_average_W':mean(result,'average_W'),
              'minimum_window_s':min(r['wall_s'] for r in result['repeats']),
              'maximum_window_s':max(r['wall_s'] for r in result['repeats']),
              'execution':result['execution'],'calls_per_decode':inventory[category]['calls_per_decode'],
              'weight_working_set_bytes':inventory[category]['weight_working_set_bytes']}
            row['short_energy_window']=row['minimum_window_s']<3.
            if row['short_energy_window']:short.append(f'{context}/{category}')
            module_rows.append(row)
        native=read(folder/'NATIVE_CONTINUOUS_DECODE.json')
        context_results['native_KV_range']=[native['repeats'][0]['KV_total_length_first'],native['repeats'][0]['KV_total_length_last']]
        context_results['all_native_repeats_generated_ids_match']=len({r['generated_ids_sha256'] for r in native['repeats']})==1
        context_results['FlashAttention_observed']=profile['FlashAttention_observed']
        contexts[str(context)]=context_results
    report.extend(['','±是三次重复的标准差，不是传感器精度。原生连续decode包含argmax，KV范围分别为2048～2175和8192～8319。固定forward不包含argmax，CUDA Graph捕获/预热在窗口外，不冒充完整自回归生成。','',
      '## 各部分时间与隔离回放能量','',
      '核时间来自真实decode的Profiler，回放能量/功率来自另一轮长窗口。两者执行边界不同；**模块能量不能直接相加，也不能据此画原生整机能量占比图**。QK/Softmax/PV保留融合，未强拆。冻结原始TIME_PROFILE中包含同名CPU范围及CUDA注释范围；本表只取CPU范围关联的内核时间，排除CUDA注释范围的流间隙时间，不重复计数。','',
      '|部分|2K核时间ms|2K回放mJ|2K回放W|8K核时间ms|8K回放mJ|8K回放W|',
      '|---|---:|---:|---:|---:|---:|---:|'])
    for category,label in LABELS.items():
        r2=next(r for r in module_rows if r['context']==2048 and r['category']==category)
        r8=next(r for r in module_rows if r['context']==8192 and r['category']==category)
        mark='†' if r2['short_energy_window'] or r8['short_energy_window'] else ''
        report.append(f"|{label}{mark}|{r2['GPU_kernel_ms_per_decode']:.4f}|{r2['isolated_replay_energy_mJ_mean']:.2f}|{r2['isolated_replay_average_W']:.1f}|{r8['GPU_kernel_ms_per_decode']:.4f}|{r8['isolated_replay_energy_mJ_mean']:.2f}|{r8['isolated_replay_average_W']:.1f}|")
    report.extend(['','†能量窗口不足3秒，受计数器刷新及主机发射影响更大，仅供参考。实际窗口和标准差见MODULES.csv；主要FFN/Attention以实际记录为准。短窗口项：'+(', '.join(short) or '无')+'。'])
    comparison=None
    if a.tlm:
        tlm=read(a.tlm);gpu=contexts['2048']['CUDA_GRAPH_FIXED_CONTEXT_DECODE']
        assert tlm['context']==2048 and tlm['batch']==1 and tlm['full_calibrated_system_energy_mJ'] is None
        conditional=tlm['covered_onchip_energy_mJ']+tlm['external_proxy_energy_mJ']
        comparison={'TLM_reference_sha256':sha(a.tlm),'GPU_graph_fixed_forward_ms':gpu['ms_mean'],
          'GPU_graph_fixed_forward_energy_mJ':gpu['energy_mJ_mean'],'TLM_TPOT_ms':tlm['TPOT_ms'],
          'TLM_conditional_onchip_plus_external_proxy_mJ':conditional,
          'TLM_to_GPU_time_ratio':tlm['TPOT_ms']/gpu['ms_mean'],
          'GPU_to_TLM_conditional_energy_ratio':gpu['energy_mJ_mean']/conditional,
          'hardware_measured_energy_saving_ratio':None,'quality_matched':False,
          'limitations':tlm['limitations']}
        report.extend(['','## 与当前概率架构条件TLM对照（2K）','',
          '|指标|RTX5090 CUDA Graph固定forward实测|概率架构TLM条件预算|',
          '|---|---:|---:|',
          f"|时间ms|{gpu['ms_mean']:.3f}|{tlm['TPOT_ms']:.3f}|",
          f"|能量mJ|{gpu['energy_mJ_mean']:.1f}|{conditional:.1f}|",
          f"|平均功率W|{gpu['average_W_mean']:.1f}|{conditional/tlm['TPOT_ms']:.3f}|",'',
          f"沿用当前条件预算时，TLM时间为GPU固定forward的{comparison['TLM_to_GPU_time_ratio']:.2f}倍；GPU能量与TLM条件预算的数值比为{comparison['GPU_to_TLM_conditional_energy_ratio']:.2f}。**这不是已经验证的芯片节能倍率，也不支持速度相当的结论。**",'',
          f"TLM采用FMA2标定后的片上已计价小计{tlm['covered_onchip_energy_mJ']:.3f}mJ，加片外旧代理{tlm['external_proxy_energy_mJ']:.3f}mJ。片外仍为64pJ/B＋50mW的旧预算，不是HBM DRAMPower校准；转换、定制CIM外围、互连/CTS等成本尚未闭合。完整校准系统能量保持null。",'',
          '此TLM路径为随机FFN＋QK筛选/准确Softmax/PV采样，不是Ising路径；GPU是原始准确BF16模型，质量尚未匹配。TLM仍有待审约束，8K未提供同版本配对估计。固定forward少argmax，且TLM阶段时间含调度/等待；不直接逐行等同于GPU核时间。'])
    report.extend(['','## 证据与限制','',
      f"模型revision `{provenance['revision']}`；torch `{provenance['torch']}`；transformers `{provenance['transformers']}`。冻结执行快照 `7911a0aff763f0dc`，源码SHA见PROVENANCE；原始文件SHA见ARTIFACT_MANIFEST。",'',
      'NVML为设备遥测，未用外部电表校准；GPU与相关显存电路计入，不包含主机CPU/DRAM。温度/时钟记录在各窗口JSON；未锁频。隔离回放会改变缓存、并发和操作顺序，小算子还可能受Python发射影响。未安装Nsight命令行，使用PyTorch CUDA Profiler；没有把TDP当实测功耗。', '',
      '文件：WHOLE.csv为整段测量；MODULES.csv为36层各类操作的核时间与隔离回放；SUMMARY.json为机器可读汇总。大trace和安装源码快照不复制到Git；manifest保留相对位置、大小与SHA。'])
    for name,rows in [('WHOLE.csv',whole_rows),('MODULES.csv',module_rows)]:
        with (a.output/name).open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    save(a.output/'SUMMARY.json',{'status':'completed','Slurm_job_id':provenance['Slurm_job_id'],
      'contexts':contexts,'modules_not_additive':True,'TLM_comparison':comparison,
      'raw_completion_sha256':sha(a.raw/'COMPLETED.json'),'raw_manifest_sha256':sha(a.raw/'ARTIFACT_MANIFEST.json')})
    (a.output/'REPORT_ZH.md').write_text('\n'.join(report)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'contexts':contexts,'TLM_comparison':comparison},ensure_ascii=False))

if __name__=='__main__':main()
