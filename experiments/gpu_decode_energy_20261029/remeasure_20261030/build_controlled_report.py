"""Validate sealed measurements and produce a human-readable non-additive report."""
import argparse,base64,csv,hashlib,json,statistics
from pathlib import Path


def parse_collection(envelope, root):
    collection=json.loads(envelope.read_text(encoding='utf-8-sig'))
    assert collection['status']=='completed'
    root.mkdir(parents=True,exist_ok=True)
    for item in collection['artifacts']:
        path=(root/item['path']).resolve();assert root.resolve() in path.parents
        raw=base64.b64decode(item['base64']);assert len(raw)==item['bytes']
        assert hashlib.sha256(raw).hexdigest()==item['sha256']
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():assert path.read_bytes()==raw
        else:path.write_bytes(raw)
    return collection


def main():
    p=argparse.ArgumentParser();p.add_argument('--collection',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raw=a.output/'raw'
    collection=parse_collection(a.collection,raw)
    get=lambda p:json.loads((raw/p).read_text())
    env=get('ENVIRONMENT.json');sealed=get('COMPLETED.json')
    assert sealed['source_sha256']==env['source_sha256']
    assert sealed['contexts']==[2048,8192]
    whole=[];modules=[];diagnostics=[]
    lines=['# RTX5090 同卡长窗口复测与公开基准核对（2026-10-30）','',
      '**结论以整卡累计能量为准；模块回放用于定位成本，不能直接相加当作整机能量。**','',
      '后训练 Qwen/Qwen3-4B，单 RTX5090、batch=1、原始 BF16 权重和准确 Attention；没有替换概率算子。prefill、加载和 token 传出不在 decode 能量窗口。',
      f"revision `{env['revision']}`；Slurm `{sealed['job']}`；代码 SHA-256 `{sealed['source_sha256']}`。完整权重、分词器、语料和输入 SHA 见原件 ENVIRONMENT/INPUT，全部窗口使用同一个 GPU UUID。",'',
      '## 1. 整体实际测量','',
      '|上下文|运行方式|ms/token 或固定 forward|J/次|整卡平均 W|重复能量 CV|',
      '|---|---|---:|---:|---:|---:|']
    labels={'NATIVE_GREEDY':'原始 HF 连续贪心生成',
            'WHOLE_ORIGINAL_EAGER':'原始 HF 固定 forward',
            'WHOLE_ORIGINAL_GRAPH':'原始 HF 固定 forward＋Graph',
            'WHOLE_STATIC_KV_GRAPH':'静态 KV＋原始 SDPA＋Graph'}
    for context in [2048,8192]:
        prefix=str(context)+'/'
        guard=get(prefix+'NUMERICAL_GUARD.json');assert guard['bitwise_equal']
        profile=get(prefix+'PROFILE_STATIC_GQA.json')
        assert profile['all_36_layers_covered'] and len(profile['rows'])==14
        inv=get(prefix+'INVENTORY_STATIC_GQA.json')
        for key,label in labels.items():
            data=get(prefix+key+'.json');s=data['summary']
            for r in data['repeats']:
                assert r['wall_s']>=5. if key=='NATIVE_GREEDY' else r['wall_s']>=10.
                assert abs(r['energy_mJ_per_item']*r['iterations']/1000-r['energy_J'])<1e-7
                assert abs(r['average_W']*r['wall_s']-r['energy_J'])<1e-7
            if key=='NATIVE_GREEDY':assert data['deterministic_generated_ids']
            cv=s['energy_mJ_per_item']['stdev']/s['energy_mJ_per_item']['mean']
            row=dict(context=context,mode=key,ms=s['wall_ms_per_item']['mean'],
              J=s['energy_mJ_per_item']['mean']/1000,W=s['average_W']['mean'],energy_CV=cv,
              repetitions=len(data['repeats']),min_window_s=min(r['wall_s'] for r in data['repeats']))
            whole.append(row)
            lines.append(f"|{context//1024}K|{label}|{row['ms']:.3f}|{row['J']:.3f}|{row['W']:.1f}|{cv*100:.2f}%|")
        idle=get(prefix+'IDLE_LOADED_MODEL.json')['summary']['average_W']['mean']
        target=next(r for r in whole if r['context']==context and r['mode']=='WHOLE_STATIC_KV_GRAPH')
        assigned=0.
        for time_row in profile['rows']:
            category=time_row['category'];data=get(prefix+'REPLAY_'+category+'.json');s=data['summary']
            assert all(r['wall_s']>=5. for r in data['repeats'])
            assert len(data['repeats'])==3
            kernel_ms=time_row['GPU_kernel_ms_per_decode']
            # Kernel time already includes all 36 layers: do NOT multiply by 36 again.
            diag=(s['average_W']['mean']-idle)*kernel_ms/1000
            assigned+=diag
            row=dict(context=context,category=category,kernel_ms=kernel_ms,
                replay_J=s['energy_mJ_per_item']['mean']/1000,replay_W=s['average_W']['mean'],
                diagnostic_attribution_J=diag,calls_per_decode=inv[category]['calls_per_decode'],
                thermal_screen_pass=data['thermal']['stable_temperature_screen_pass'],
                min_window_s=min(r['wall_s'] for r in data['repeats']),
                first_temperature_C=data['repeats'][0]['state_before']['temperature_C'],
                last_temperature_C=data['repeats'][-1]['state_after']['temperature_C'])
            modules.append(row)
        floor=idle*target['ms']/1000
        linear_bytes=sum(inv[c]['weight_working_set_bytes'] for c in
                         ['QKV_projection','Wo_projection','FFN_gate_up','FFN_down','lm_head'])
        kv_read=2*36*8*128*2*context
        diagnostics.append(dict(context=context,idle_W=idle,diagnostic_floor_J=floor,
            diagnostic_active_assigned_J=assigned,residual_J=target['J']-floor-assigned,
            measured_whole_J=target['J'],linear_weight_bytes=linear_bytes,
            logical_minimum_KV_read_bytes=kv_read,
            logical_weight_plus_KV_minimum_GB_per_s=(linear_bytes+kv_read)/(target['ms']/1000)/1e9))
    lines+=['','连续生成每次 256 步、三个重复，含逐步 argmax 与真实 KV 增长；2K 的 KV 从 2048 增长到 2303，8K 从 8192 增长到 8447。固定 forward 保持同一个输入和缓存长度，不含 argmax，也不是服务吞吐。Graph 去除逐算子 Python 发射开销；静态 KV 使用原始 SDPA，只替换整段缓存复制为当前位置写入，两种上下文 logits 均逐位一致。',
      '', '## 2. 模块时间与隔离回放能量','',
      '以下均为一次 decode 中全部 36 层的同类操作合计。时间来自独立采集的 CPU 标注所关联的 GPU kernel 总时长；不是含空隙的 CUDA 注释跨度。回放 J/次和 W 由长窗口直接测得，但其执行顺序、缓存复用和并发不同于完整模型，不能直接求和。','','|部分|2K kernel ms|8K kernel ms|2K 回放 J/次|8K 回放 J/次|', '|---|---:|---:|---:|---:|']
    cn={'Embedding':'词嵌入','RoPE':'RoPE','QKV_projection':'Q/K/V 投影','QK_RMSNorm':'Q/K RMSNorm',
        'KV_append':'KV 当前位置写入','Attention_core':'融合准确 Attention（含 K/V 头展开）',
        'Wo_projection':'Attention 输出投影','Layer_RMSNorm':'层 RMSNorm','FFN_gate_up':'FFN Wg/Wu',
        'FFN_SwiGLU':'FFN SiLU＋逐元素乘积','FFN_down':'FFN Wd','Residual_add':'残差相加',
        'Final_RMSNorm':'末尾 RMSNorm','lm_head':'输出词表层'}
    for category in cn:
        x=next(r for r in modules if r['context']==2048 and r['category']==category)
        y=next(r for r in modules if r['context']==8192 and r['category']==category)
        lines.append(f"|{cn[category]}|{x['kernel_ms']:.4f}|{y['kernel_ms']:.4f}|{x['replay_J']:.5f}|{y['replay_J']:.5f}|")
    lines+=['','`MODULES.csv`另列诊断归因 `(模块回放功率−驻留空闲功率)×原位关联kernel时间`；时间已经包含所有层，不再乘36。底功耗与剩余残差单列在 DIAGNOSTICS.json，残差允许为负，不强迫饼图闭合。该归因是模型估计，不是每模块独立电源轨实测。',
      '', '## 3. 与公开速度基准比较','',
      '|来源|条件|公开结果|如何比较|','|---|---|---|---|',
      '|[Qwen 官方](https://qwen.readthedocs.io/en/latest/getting_started/speed_benchmark.html)|H20、Qwen3-4B BF16、B1、输入1/输出2048、Transformers4.51.3＋FA2|45.94 tokens/s，约21.77 ms/输出 token|GPU和内核不同，只能检查 HF 数量级；输入1时官方含输入的计数差异很小|',
      '|[Qwen 官方](https://qwen.readthedocs.io/en/latest/getting_started/speed_benchmark.html)|同上，SGLang0.4.6.post1|133.13 tokens/s，约7.51 ms/token|说明成熟引擎可快于通用 HF，不是我们的严格同卡对照|',
      '|[pegainfer 作者基准](https://github.com/pegainfer-project/pegainfer/blob/main/docs/models/qwen3/serving-performance.md)|单5090、Qwen3-4B BF16、TP1、输入1024/输出128、QPS1；驱动590/CUDA13.1|pegainfer TPOT6.53 ms；vLLM0.24 TPOT6.71 ms|同卡型/精度，输入、软件、服务路径不同；不能用高并发总吞吐替代单请求 TPOT|',
      '|[Grout 论文 §5.3](https://arxiv.org/html/2606.15991v1#S5.SS3)|5090、Qwen3-4B、f16、B1；prompt18、生成长度扫描|长生成8192时154.7 tokens/s，约6.46 ms/token|FP16和短prompt增长上下文，作为融合/Graph实现的旁证，不混称 BF16 同配置|',
      '', 'Qwen 官方 speed 的定义是“输入＋输出 token 数／总时间”。6144、14336等长输入的数百 tokens/s含 prefill，不能把倒数当作 decode TPOT。公开能耗方面，尚未找到与本轮同模型、单5090、BF16、B1、2K/8K且仅decode边界完全匹配的独立 J/token 原始结果；不拿 TDP×时间冒充它人的实测能量。',
      '', '## 4. 异常检查与适用范围','',
      '- 每个正式窗口核验 `平均W×秒=J`、`J÷实际执行次数=J/次`，不用 GPU TDP 替代读数。整模型首个长窗还对照同窗功率积分；两个接口同属 NVML，只验证内部一致性，不是外部电表校准。',
      '- 所有阶段先按最后五个约1s温度样本跨度≤1°C筛查，最多等待25s（整模型60s）；没有锁频/改功率上限。每个窗口保留前后温度和 SM/显存频率；未通过筛查照实列出，不静默剔除。它不是完整的冷却配对实验，温升/动态频率仍会影响绝对能量。',
      '- 原生 Flash GQA 在最初8K门禁 relative-L2 为1.42698%、top1相同，超过预设1%，保留失败而不放宽门限。本轮正式静态KV路径保留原始头展开；历史文件名 STATIC_GQA 是开发命名，不表示正式开启原生 GQA。',
      '- HF固定/Graph路径仍没有成熟引擎的线性层合并、QK Norm/RoPE融合及原生GQA等全部优化。若它慢于公开成熟引擎，不能推导 GPU 硬件本身只能达到该速度，也不能据它宣布概率ASIC对最佳GPU的倍数收益。',
      '- 只测GPU及其关联板载显存电路，未计主机CPU/系统DRAM。ASIC/TLM若对比整卡 J/token，也要标清外存、未定价模块、质量和速度差异。无新PPL、训练或ASIC电路验证。',
      '', '## 5. 复现与证据','',
      '`raw/COMPLETED.json`封存状态与ARTIFACT_MANIFEST相互校验；本地所有小JSON按原字节SHA下载。大TRACE留既有个人服务器存储，REMOTE_INDEX.json记录原位置、大小及SHA。冻结依赖7911a0aff763f0dc、源代码和启动/失败记录见EXECUTION.json。',
      '', '方法依据：[Zeus温度与长窗实验](https://ml.energy/blog/energy/measurement/thermally-stable-profiling-for-accurate-gpu-energy-measurement/)、[NVML设备接口](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html)、[PyTorch2.7 SDPA/GQA说明](https://docs.pytorch.org/docs/2.7/generated/torch.nn.functional.scaled_dot_product_attention.html)。']
    for name,rows in [('WHOLE.csv',whole),('MODULES.csv',modules)]:
        with (a.output/name).open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (a.output/'REPORT_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    for name,obj in [('DIAGNOSTICS.json',diagnostics),('SUMMARY.json',dict(whole=whole,modules=modules)),
                     ('REMOTE_INDEX.json',dict(directory=collection['remote_result_directory'],manifest=collection['large_trace_index']))]:
        (a.output/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(status='validated',windows=sum(3 for _ in whole)+len(modules)*3,
                         modules=len(modules),whole=whole),ensure_ascii=True))


if __name__=='__main__':main()
