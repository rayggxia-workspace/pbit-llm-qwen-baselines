"""Check original bytes and summarize deterministic local score precision audit."""
from pathlib import Path
import json,hashlib,statistics,shutil
R=Path(__file__).resolve().parents[3];W=Path(__file__).parent;WS=R.parents[1]
A=WS/'project_archives/attention_compare_issue198_20261027/score_dtype_20261028'
E=R/'experiments/attention_score_dtype_20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def save(p,d):p.write_bytes((json.dumps(d,indent=2,ensure_ascii=False)+'\n').encode())
def main():
    collection=read(W/'DTYPE_COLLECTION.json')
    for name,m in collection['files'].items():assert sha(A/name)==m['sha256'] and (A/name).stat().st_size==m['bytes']
    source=read(W/'DTYPE_SOURCE.json')
    for name,h in source['manifest']['files_sha256'].items():assert sha(R/name)==h
    data=read(A/'results/RESULTS.json');assert len(data['rows'])==len(data['profiles'])==32
    assert all(x['native_repeats_equal'] for x in data['native_baseline'])
    assert all('aten::_scaled_dot_product_flash_attention' in x['operators'] for x in data['profiles'])
    result={}
    for scope in ['full_kv','fixed_sparq128']:
        rows=[x for x in data['rows'] if x['scope']==scope];assert len(rows)==16
        result[scope]=dict(query_layer_cases=16,head_rows=512,probability_tv_mean=statistics.mean(x['probability']['tv_mean'] for x in rows),
            probability_tv_max=max(x['probability']['tv_max'] for x in rows),output_relative_rms_mean=statistics.mean(x['output_rounding_only']['relative_rms'] for x in rows),
            output_relative_rms_max=max(x['output_rounding_only']['relative_rms'] for x in rows),argmax_changes=sum(x['probability']['argmax_changes'] for x in rows),
            native_vs_fp32_reference_relative_rms_mean=statistics.mean(x['native_vs_fp32_reference']['relative_rms'] for x in rows))
    save(E/'SUMMARY.json',dict(status='completed_local_numeric_diagnostic',job=3290,summary=result,source=source['manifest'],original_result_sha256=sha(A/'results/RESULTS.json'),baseline_repeated_exactly=4,slurm_finished=True,new_circuit_run=False,new_ppl=False))
    for name in ['RESULTS.json','provenance.json','COMPLETE.json']:shutil.copyfile(A/'results'/name,E/name)
    table='\n'.join(f"|{scope}|{x['probability_tv_mean']*100:.4f}%|{x['probability_tv_max']*100:.4f}%|{x['output_relative_rms_mean']*100:.4f}%|{x['output_relative_rms_max']*100:.4f}%|{x['argmax_changes']}/512|" for scope,x in result.items())
    report='''# Qwen3-4B进入softmax的分数：原生内核与BF16接口审计

2026-10-28，Issue198 / PR199，rayggxia。结论分两层：本批原生SDPA实测走FlashAttention；对应PyTorch2.7.1发布源码用FP32分数累加片段进入softmax，之后才转换概率片段为BF16。**但分数接口并非必须FP32**：原生eager支持BF16分数→FP32 softmax，本次同真实QKV的BF16分数舍入路径可执行且有可量化的非零误差，不能宣称完整PPL无损。

## 实际测试

GPU Slurm3290，RTX5090，torch2.7.1+cu128 / transformers4.51.3。模型Qwen/Qwen3-4B后训练revision1cfa9a7208912126459214e8b04321603b3df60c；权重/tokenizer逐文件SHA、WT2 train/test原字节SHA及完整token SHA核验。torch_dtype BF16、SDPA、TF32关闭，原FFN/投影/QK-norm/RoPE/cache均保持。源码父提交0d8a6f1a加不可变逐文件SHA快照；本次未改变旧实验默认。

WT2起点0/4096，各长度512/2048，4个真实窗口；每窗完整原生prefill后观察最后一个decode query，层0/12/23/35、每层32头。16个原生query-layer调用，共512头行；再固定同一FP32 SparQ r32/k128/local32候选，对同512头做128候选诊断。合计32个张量对照，不是32个独立文本、不是1024个独立原生输入。无随机采样，seed0单次确定性数值诊断，三随机种子不适用。

原生模型每个窗口重复两次，带诊断钩子与不带诊断计算的词表logits逐字节一致，4/4通过。诊断只旁路观察，不把替代输出送回模型后续层，因此不是全层替换PPL。模型加载/文件哈希以外的审计耗时约1.864秒，不能当推理吞吐或硬件时延。

CPU operator profiler的全部32个被测decode调用均记录aten::_scaled_dot_product_flash_attention和aten::_flash_attention_forward。该结论限本次batch1、query_len1、无padding及这些形状；不冒称已经追踪原完整PPL所有batch32/prefill调用。profiling确认分派，发布源码给出类型语义，未反汇编wheel/逐寄存器观测。

## 隔离分数舍入的结果

参考：同BF16 Q/K转FP32计算z=(QKᵀ)/sqrt(128)，FP32 softmax和FP32 PV。
对照：同一个z先舍入成BF16，再提升为FP32执行同样softmax和PV。因此只改变进入softmax前的分数有效精度，不混入概率量化、PV低精度、随机采样或候选重筛选。提升回FP32不会恢复已经丢失的分数位。

TV=0.5×sum(abs(Pbf16−Pfp32))。平均TV按全部头行等权；输出相对RMS为每个query-layer张量的||误差||₂/||参考||₂，再跨16张量等权平均，最大RMS是16张量中最大，**不是逐头最坏RMS**。argmax变化可由舍入形成并列最大值，不自动等于任务错误。

|范围|平均TV|最大单头TV|平均输出相对RMS|最大张量相对RMS|argmax变化|
|---|---:|---:|---:|---:|---:|
'''+table+'''

另实际执行eager式BF16 QK矩阵输出→BF16缩放→FP32 softmax→BF16概率→BF16 PV，各项均有限、score dtype均BF16；其误差包含多个舍入边界，不能与上表的单一分数舍入混称。逐项误差保留在RESULTS.json。128候选是固定FP32路由，仅诊断分数精度，不验证BF16路由会选择相同候选。

## 类型依据与硬件含义

对应[PyTorch v2.7.1的FlashAttention子模块](https://github.com/pytorch/pytorch/tree/v2.7.1/third_party/flash-attention)指向979702c87a8713a8e0a5e9fee122b90d2ef13be5。[kernel_traits.h](https://github.com/Dao-AILab/flash-attention/blob/979702c87a8713a8e0a5e9fee122b90d2ef13be5/csrc/flash_attn/src/kernel_traits.h)定义ElementAccum为float；[flash_fwd_kernel.h](https://github.com/Dao-AILab/flash-attention/blob/979702c87a8713a8e0a5e9fee122b90d2ef13be5/csrc/flash_attn/src/flash_fwd_kernel.h)先将acc_s交给softmax，之后才转Element用于PV；[softmax.h](https://github.com/Dao-AILab/flash-attention/blob/979702c87a8713a8e0a5e9fee122b90d2ef13be5/csrc/flash_attn/src/softmax.h)直接在该片段上缩放/取exp2。精确blob和行号见REFERENCES.json。缩放可以融合进指数计算，不要求先物化完整缩放分数矩阵。

[Transformers4.51.3 eager路径](https://github.com/huggingface/transformers/blob/v4.51.3/src/transformers/models/qwen3/modeling_qwen3.py#L134-L155)接收BF16 Q/K时，QK/缩放输出为BF16张量，再通过dtype=torch.float32进行softmax并回转。这证明BF16分数接口是已有可执行选择，不意味着softmax内部所有运算也是BF16。[SDPA文档](https://docs.pytorch.org/docs/2.7/generated/torch.nn.functional.scaled_dot_product_attention.html)另明确math后端的BF16输入中间量为FP32。

因此硬件应分别确定乘法输入、累加精度、score输出接口、softmax/LUT内部精度。推荐将BF16 Q/K输入、FP32或经验证宽定点累加、BF16 score接口作为下一步待验候选，FP32 score保留质量参考；本次不默认替换已有方案。直接从高精度累加器量化进LUT也可省去一次BF16中间舍入，须单独计转换成本和误差。

原0.923nJ/128次输出仅仲裁控制；本轮没有新RTL/DC/PT、PPA或完整PPL，不新增数字电路台账run。BF16 score会改变分布；8位LUT/12位阈值的误差仍需单独测，不能把它们与本表误差混合继承。当前不能承诺整模型质量阈值或无损。

## 可恢复证据

work/rayggxia/198/DTYPE_SOURCE.json、DTYPE_SUBMISSION.json和DTYPE_COLLECTION.json绑定快照、Slurm3290与全部6原件SHA；原字节本机project_archives/attention_compare_issue198_20261027/score_dtype_20261028，个人GPU目录保持。COMPLETE.json逐项哈希校验通过，当前源码与执行manifest相同。日志的全语料tokenizer长度警告只是一次分词299078 token；实际模型输入最大2048，并未把整份语料送入模型。无失败作业或重复提交，PR199待审，未合并。
'''
    (E/'REPORT_ZH.md').write_bytes(report.encode())
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
