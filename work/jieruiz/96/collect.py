"""Verify immutable v6 executions and derive the compact Chinese report."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess

ROOT=Path(__file__).resolve().parents[3]
MODULE=ROOT/'architecture_tlm/unified_v6'
EXPECTED='fba22b192ab914046e50cc405f6dd473bf30d154'


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def text_output(p,data,verify):
    raw=data.encode('utf-8')
    if verify:
        if p.read_bytes()!=raw:raise ValueError('derived bytes differ: '+str(p))
    else:p.write_bytes(raw)


def main(verify=False):
    folders=[MODULE/'results/qwen_20261022_v2']+[MODULE/('results/%s_%s_20261022_v2'%(m,k))
        for m in ('llama1','llama2') for k in ('bf16','scpv')]
    results=[];manifest_checks=0;source_checks=0;contracts=0
    sources_seen=set();case_files={};manifest_files={}
    for folder in folders:
        manifest=folder/'ARTIFACT_MANIFEST.json'
        if not manifest.exists():raise ValueError('execution incomplete: '+str(folder))
        items=json.loads(manifest.read_text(encoding='utf-8'))
        for rel,record in items.items():
            p=folder/rel
            if p.stat().st_size!=record['bytes'] or digest(p)!=record['sha256']:
                raise ValueError('archived artifact changed: '+str(p))
            manifest_checks+=1
        execution=json.loads((folder/'EXECUTION.json').read_text(encoding='utf-8'))
        if execution['commit']!=EXPECTED:raise ValueError('unexpected execution source')
        for rel,record in execution['files'].items():
            if rel not in sources_seen:
                raw=subprocess.check_output(['git','show',EXPECTED+':'+rel],cwd=ROOT)
                if len(raw)!=record['bytes'] or hashlib.sha256(raw).hexdigest()!=record['sha256']:
                    raise ValueError('execution Git blob changed: '+rel)
                sources_seen.add(rel);source_checks+=1
        summary=json.loads((folder/'SUMMARY.json').read_text(encoding='utf-8'))
        for row in summary['rows']:
            name='%s_L%d_seed%d_%s_%s.json'%(row['model'],row['context'],row['seed'],row['ffn'],row['attention'])
            p=folder/row['model']/name
            d=json.loads(p.read_text(encoding='utf-8'));c=d['config'];m=d['model']
            config_sha=hashlib.sha256(json.dumps(c,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if d['execution_commit']!=EXPECTED or d['config_sha256']!=config_sha:raise ValueError('config/source mismatch')
            if d['metrics']['full_physical_energy_J'] is not None or d['metrics']['full_physical_area_mm2'] is not None:raise ValueError('unverified full PPA')
            if d['metrics']['quality_reference_ppl'] is not None:raise ValueError('inherited PPL')
            if abs(sum(d['phase_ns'].values())-d['metrics']['elapsed_ns'])>1e-3:raise ValueError('phase ledger')
            if d['SRAM']['reserved_peak_bytes']>c['sram']['capacity_bytes']:raise ValueError('capacity')
            if any(d['random_interface'][x]!=0 for x in ('random_stream_SRAM_bytes','extra_random_FIFO_bytes','extra_probability_copy_bytes')):raise ValueError('random storage')
            for phase in ('QKV_projection','attention_core','O_projection','FFN_gate_up','FFN_SwiGLU','FFN_down'):
                coverage={p['layer'] for p in d['phases'] if p['name']==phase}
                if coverage!=set(range(m['num_hidden_layers'])):raise ValueError('layer coverage')
                contracts+=1
            if c['ffn']['mode']=='sc':
                expected=3*m['hidden_size']*m['intermediate_size']*m['num_hidden_layers']//4096*c['decode_tokens']
                if d['FFN_activity']['SC_64x64_tiles']!=expected:raise ValueError('SC tile count')
                if d['FFN_activity']['BF16_to_probability8_values']!=m['hidden_size']*m['num_hidden_layers']*c['decode_tokens']:raise ValueError('g/u x is not shared')
                if d['FFN_activity']['FP32_to_probability8_values']!=m['intermediate_size']*m['num_hidden_layers']*c['decode_tokens']:raise ValueError('z input format')
                contracts+=3
            if c['attention']['mode'] not in ('exact','screen_exact'):
                multiplier=c['attention']['winner_update_multiplier'] if c['attention']['mode']=='screen_winner' else 1
                per=sum((c['attention']['samples'] or max(c['attention']['minimum_samples'],math.ceil((c['context_tokens']+t)*c['attention']['sample_ratio'])))*multiplier for t in range(c['decode_tokens']))
                if d['attention_activity']['V_sample_events']!=per*m['num_attention_heads']*m['num_hidden_layers']:raise ValueError('sampling horizon')
                contracts+=1
            results.append((row,d));case_files[str(p.relative_to(ROOT)).replace('\\','/')]=dict(sha256=digest(p),bytes=p.stat().st_size)
            contracts+=6
        manifest_files[str(manifest.relative_to(ROOT)).replace('\\','/')]=digest(manifest)
    if len(results)!=52:raise ValueError('expected48 Qwen+4 complete Llama cases')
    unique={(r['model'],r['context'],r['seed'],r['ffn'],r['attention']) for r,d in results}
    if len(unique)!=52:raise ValueError('duplicate cases')
    groups=defaultdict(list)
    for r,d in results:groups[(r['model'],r['context'],r['ffn'],r['attention'])].append((r,d))
    refs={}
    for (model,L,ffn,attn),values in groups.items():
        if ffn=='bf16' and attn=='exact':refs[model,L]=values[0][0]
    labels={('bf16','exact'):'原BF16＋准确Attention',('w8','exact'):'固定W8数字FFN＋准确Attention',
        ('sc','exact'):'B4/T32/K32＋准确Attention',('sc','pv'):'同FFN＋PV采样',
        ('sc','screen_exact'):'同FFN＋筛选后准确',('sc','screen_pv'):'同FFN＋筛选后PV',
        ('sc','screen_rejection'):'同FFN＋筛选后校正拒绝',('sc','screen_winner'):'同FFN＋筛选后赢家保持'}
    order=list(labels)
    lines=['# 统一整机TLM v6：结果与检查入口','',
        '2026-10-22；Issue96；负责人jieruiz。执行源码 `'+EXPECTED+'`。',
        '', '**这是完整decode的条件架构估计，不是PPL、GPU实测或芯片PPA。** 本轮52项全部完成：Qwen2K/8K各8方案×3seed，共48项；Llama1/2各BF16准确、SC/PV两项完整32层单seed连通，共4项。三模型文件分开，失败门禁不计入。',
        '', '统一条件：100MHz计算核、512 MAC/周期、64向量操作/周期、16非线性/周期；80MHz 1RW SRAM，16bank/16B字、16GB/s共享fabric；Link外存16GB/s、80ns、64B突发、32请求窗口。Qwen SRAM1MiB，Llama8MiB。随机源按本地接口供给，不存随机流。初始KV/摘要已存在，不含prefill/TTFT。',
        '', '## 一眼看懂时间对照','', '| 方案 | 2K ms/token | 8K ms/token |','|---|---:|---:|']
    for ffn,attn in order:
        vals=[statistics.mean(r['TPOT_ms'] for r,d in groups['qwen',L,ffn,attn]) for L in (2048,8192)]
        lines.append('| '+labels[ffn,attn]+' | %.3f | %.3f |'%tuple(vals))
    lines += ['', '同一行Qwen为三seed均值；普通基准也在本轮执行。赢家输出数为PV/拒绝的8倍：2K为1024、8K为4096次更新；PV/拒绝为128/512次，不能按相同S解释。新采样器没有继承完整模型PPL。',
        '', '**随机FFN不能只与BF16比较。** 与W8数字FFN相比，它还增加采样、分档归约和恢复，当前调度更慢；相对BF16的部分时间收益来自权重缩为W8。未知的阵列和随机源能量尚不支持总能效排名。',
        '', '## K/V物理读取究竟省了多少','', '| Attention（FFN固定为SC） | 2K K保留 | 2K V保留 | 8K K保留 | 8K V保留 |','|---|---:|---:|---:|---:|']
    for attn in ('exact','pv','screen_exact','screen_pv','screen_rejection','screen_winner'):
        vals=[]
        for L in (2048,8192):
            v=groups['qwen',L,'sc',attn];ref=refs['qwen',L]
            vals += [statistics.mean(r[k] for r,d in v)/ref[k]*100 for k in ('K_physical_bytes','V_physical_bytes')]
        lines.append('| '+labels['sc',attn].replace('同FFN＋','').replace('B4/T32/K32＋','')+' | %.2f%% | %.2f%% | %.2f%% | %.2f%% |'%tuple(vals))
    lines += ['', '以上只比较K/V读取，摘要、追加KV、投影权重和SRAM读写另计。2K固定8×64=512候选，逻辑QK保留25%，GQA不同查询头候选并集会使K读取明显大于25%；不能按保留率直接缩放KV。8K候选仍512，采样预算却为512，筛选后PV不一定比筛选后准确更快，额外频数/选择加法及调度也计入。',
        '', '## 时间主要在哪里','', '| Qwen2K，seed0 | gate/up | SwiGLU | down | Attention核心 | lm_head/选词 |','|---|---:|---:|---:|---:|---:|']
    for ffn,attn in [('bf16','exact'),('w8','exact'),('sc','exact'),('sc','screen_rejection'),('sc','screen_winner')]:
        d=next(d for r,d in groups['qwen',2048,ffn,attn] if r['seed']==0)
        vals=[d['phase_ns'].get(k,0)/1e6 for k in ('FFN_gate_up','FFN_SwiGLU','FFN_down','attention_core','lm_head_and_argmax')]
        lines.append('| '+labels[ffn,attn]+' | %.3f | %.3f | %.3f | %.3f | %.3f |'%tuple(vals))
    d=groups['qwen',2048,'sc','exact'][0][1];c=d['config'];m=d['model']
    restore=d['actions']['SC_restore_op']/c['vector_lanes']*(1e9/c['core_hz'])/1e6
    waves=(m['hidden_size']//64*math.ceil((2*m['intermediate_size']//64)/c['ffn']['engines'])+m['intermediate_size']//64*math.ceil((m['hidden_size']//64)/c['ffn']['engines']))*m['num_hidden_layers']
    core=waves*(c['ffn']['startup_cycles']+c['ffn']['samples']*c['ffn']['sample_II_cycles']+c['ffn']['drain_cycles'])*(1e9/c['core_hz'])/1e6
    lines += ['', 'SC准确Attention的Qwen2K：主阵列各波次服务约 **%.3fms**，按64路向量单元执行的四档/位平面恢复工作约 **%.3fms**。这两项来自明确配置的动作与调度，不是已测专用恢复电路性能。当前恢复、搬运和接口开销远比T32采样本身更值得验证；不能把T=32称为整层32周期。'%(core,restore),
        '', '校正拒绝逐候选偏移重编程、源/仲裁/反馈，以及串行直方图RMW；赢家的更多保留样本、输出写入和直方图RMW，都可能成为大项。完整资源忙闲、动作、阶段和等待在各JSON；当前sink保守占用SRAM fabric，直方图每地址安全RMW，不代表已经优化的流水。不能把这个调度的较慢结果当作所有p-bit实现的下界。',
        '', '## 存储与随机接口','', '| 模型/完整情景 | SRAM配置 | 本轮最高保留峰值KiB | 宏面积mm² | 随机流SRAM/FIFO |','|---|---:|---:|---:|---:|']
    for model in ('qwen','llama1','llama2'):
        ds=[d for r,d in results if r['model']==model]
        lines.append('| %s | %.0fMiB | %.2f | %.4f | 0 / 0 |'%(model,ds[0]['config']['sram']['capacity_bytes']/1024**2,max(d['SRAM']['reserved_peak_bytes'] for d in ds)/1024,ds[0]['SRAM']['area_mm2']))
    lines += ['', '宏面积只含已有宏表范围，不含外围/CDC/CTS，也不是全芯片面积。必要BF16残差、x/z独立缓冲、计数、宽部分和、候选/频数/地址仍存在；没有把它们冒称随机流缓存。SC局部计数状态峰值与采样器局部状态单列，未偷偷改成免费SRAM。SRAM预算尚未搜索最优，空余容量不等于已实现权重/KV缓存。',
        '', '随机端口记录局部启动/新帧/重放、均匀位、有偏响应、并行需求；FFN同64路共享，Attention候选独立。后端继续Issue95。`embedded_source_cycles`在此版是累计lane-slot周期，不是可直接加到系统时间的串行周期；有偏响应编码活动是逐候选重配置上界，实际电路再标定。',
        '', '## 目前可以比较什么能量','',
        '- SRAM宏内部读写/漏电有55nm SS表征依据；其绝对数值随动作/驻留时间核算。',
        '- 普通数字部分仍有明确标记的旧条件单价；默认外存是64pJ/B＋50mW背景情景，并非本轮DRAMPower。',
        '- B4短流阵列、恢复/编码、FP32 PV、动态转换、本地PRNG/概率响应、仲裁与外围等仍有未标定动作。',
        '- **完整物理能量、完整面积、新组合PPL全部null。不同方案priced_subtotal覆盖不同，禁止将它们相除声称整机能效收益。**',
        '', '## Llama完整连通（单seed，非质量结果）','', '| 模型 | BF16准确 ms/token | SC＋PV ms/token |','|---|---:|---:|']
    for model in ('llama1','llama2'):
        vals=[groups[model,2048,ffn,attn][0][0]['TPOT_ms'] for ffn,attn in [('bf16','exact'),('sc','pv')]]
        lines.append('| %s | %.3f | %.3f |'%(model,*vals))
    lines += ['', '两者形状相同，合成事务及时间相同是预期现象；不表示权重、tokenizer或任务精度相同。Llama没有三seed全方案评测，不与Qwen48项混称。',
        '', '## 验证、版本与下一步','',
        '21项新机制测试、18项原并行采样器与10项原v4检查通过；三模型旧anchor/新入口dry-run通过。完整52项另核验manifest、执行Git blob、配置SHA、层覆盖、阶段总和、SRAM容量、随机存储、SC tile数、共享入口与采样预算。核查数量见 `work/jieruiz/96/RESULT_CHECKS.json`。',
        '', '初版4e0d26b门禁的W8尺度元数据越界在fba22b1修复，并增加分块回归；两份旧BF16前缀和失败执行原件保留于原目录，索引FAILED_PREFLIGHT.json，不进入上述52项。原件不重写。',
        '', '下一步优先表征/校验：B4恢复与编码吞吐及能量、权重驻留接口、采样器偏移更新与直方图/输出流水、本地源接口。若这些验证能改变方案排名，再细化对应模块。普通ASIC对照与GPU实测不是同频同带宽，不能直接把本表时间当GPU误差。',
        '', '实现和运行说明：[README_ZH.md](README_ZH.md)。各结果目录有EXECUTION、配置SHA、SUMMARY和ARTIFACT_MANIFEST；每个模型有独立子目录。没有新模型推理、训练、GPU、Slurm、PT或真实DRAMSys运行。','']
    text_output(MODULE/'RESULTS_ZH.md','\n'.join(lines),verify)
    checks=dict(execution_commit=EXPECTED,accepted_cases=52,qwen_cases=48,llama_single_seed_cases=4,
        immutable_artifact_checks=manifest_checks,execution_source_blob_checks=source_checks,
        model_contract_checks=contracts,duplicate_cases=0,passed=True,
        manifest_sha256=manifest_files,case_files=case_files,
        disclaimer='offline verification of new synthetic TLM executions, not PPL/PT')
    text_output(ROOT/'work/jieruiz/96/RESULT_CHECKS.json',json.dumps(checks,ensure_ascii=False,indent=2)+'\n',verify)
    print(json.dumps({k:v for k,v in checks.items() if k not in ('manifest_sha256','case_files')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args();main(a.verify)
