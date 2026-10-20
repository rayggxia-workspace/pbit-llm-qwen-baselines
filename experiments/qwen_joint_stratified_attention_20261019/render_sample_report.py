"""Render the PPL-only observation-count report and an exportable figure."""
import argparse,csv,json
from pathlib import Path


def render(summary,out,full_job):
    out.mkdir(parents=True,exist_ok=True);r=summary
    def cell(mean,sd):return f'{mean:.6f} ± {sd:.6f}'
    rows=['# Ising观测次数与PPL：固定四档32拍FFN','',
        'Issue50 / [PR52](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/52)，2026-10-19，负责人jieruiz。本次只评估PPL，未追加任务基准、训练或硬件能效估算。','',
        '**原有完整联合任务用S128；此前联合后缀测过S128和S512。本次补齐S32/64/256/1024及筛选后准确PV，固定FFN与其他Attention设置。** S为每个query/head保留的Ising观测数；预热16、观测间隔4固定，观测时刻16+4k，k=1..S。它不是器件更新次数，也不是独立有效样本数。','',
        '## 结果总表','',
        '全部为同一32段×128目标＝4096目标的固定后缀PPL，初始context2048、batch8、seed0/1/2；±为三个种子的总体标准差，不是语料置信区间。越低越好。','',
        '| Ising观测数S | 原始FFN＋相同Attention | 四档32拍FFN＋相同Attention |',
        '|---:|---:|---:|']
    for x in r['curve']:
        rows.append(f"| {x['samples']} | {cell(x['original_ffn_ppl_mean'],x['original_ffn_ppl_population_sd'])} | {cell(x['ppl_mean'],x['ppl_population_sd'])} |")
    exact=r['candidate_exact_reference'];e=exact['joint']
    rows += [f"| 筛选后准确Softmax＋准确PV（无Ising） | {cell(exact['original_ffn_ppl_mean'],exact['original_ffn_ppl_population_sd'])} | {cell(e['ppl_mean'],e['ppl_population_sd'])} |",'',
        f"原始BF16/SDPA匹配基线 **{r['baseline_bf16_ppl']:.6f}**；仅替换四档32拍FFN、Attention原版 **{cell(r['ffn_only']['ppl_mean'],r['ffn_only']['ppl_population_sd'])}**。FFN的32拍与Ising的S是两个独立参数。上表不是完整WT2，不能直接减去原全量11.65。",'',
        '## 变化说明','']
    indexed={x['samples']:x for x in r['curve']}
    for low,high in ((32,64),(64,128),(128,256),(256,512),(512,1024)):
        a,b=indexed[low],indexed[high]
        rows.append(f"- S{low}→S{high}：联合PPL {a['ppl_mean']:.6f}→{b['ppl_mean']:.6f}，变化{b['ppl_mean']-a['ppl_mean']:+.6f}。")
    rows += ['',
        '只看本轮后缀PPL，1024次最低。256与512的均值仅差约0.011，小于两组各自的seed标准差；目前没有清楚的质量差异证据，但这不证明二者等价。是否可用256代替512，继续用完整WT2确认。','',
        f"S1024与同筛选准确PV参考的PPL差为{indexed[1024]['ppl_mean']-e['ppl_mean']:+.6f}；该准确PV是取消候选内随机估计的诊断参考，不是数学上的PPL下界。筛选仍存在，筛选候选可以随模型hidden和独立筛选随机流变化。不能由这条曲线宣布继续增加S必然无用，也不能把全部剩余损失归于Ising。",'',
        'S可以大于最多512个候选，因为链可反复观测同一类别；这里没有要求选出S个互不相同的token。相邻重复包含注意力分布集中与链相关两种因素，不能直接据此计算ESS。','',
        '## 只改变了什么','',
        '全24层FFN保持B4/T32/K32、历史固定INT8权重、A8共享64路分层输入/乘积编码；SiLU(g)×u仍连续FP32，接口BF16。FFN的prefill/decode均替换。计分query的24层Attention均实际执行max4概率筛选、固定8块修补、候选准确QK、有限hard-onehot CTMC Ising、按索引直接选择并平均V。Attention多token prefill仍准确SDPA。没有先准确Softmax再冒称Ising，也没有重复PV抽样。','',
        '不同S的burn、spacing、候选预算、筛选train校准、FFN和计分位置均不变。三seed全部保留，不选择最好的seed。随机域分离，但不同S的真实hidden及CTMC事件消耗会改变轨迹，不宣称所有输出随机数完全配对。','',
        '## 全量确认','',
        f"此前Slurm2430的22项完整cached对照仍按原53dd快照运行，含B4T32的S128及原BF16/FFN-only；不修改或重交。新S256/S512各3seed完整确认：{full_job}。完整计分为299077目标、window2048/stride1024、batch32，所有计分query真正触发替换；完整任务未收齐时不填写其PPL。新完整任务复用已通过的实际32×1023显存门禁，并核验数值内核源码未变。",'',
        '## 来源与复现','',
        '新15项后缀执行源c0fd54446d843f0b21e94bf138c692048e518c86；Slurm2440重新核验模型/语料与原BF16后缀参考10.37155678462956，再由Slurm2441评估。已有B4T32 S128/S512及FFN-only来自原Issue50/d61，不重复计算。原FFN曲线来自成员Issue48/PR49的公开固定8块结果：publication8dd1b06a、execution11f1d6ee、Slurm2380；并非本次重新运行。',
        '',
        'references保存原始公开summary/ARTIFACTS/input核验与独立SHA导入记录。原FFN参考与本任务的权重、模型revision、测试文本/token/目标位置、batch以及基线相同；两边配置/分词器部分原文件的字节不同，已在IMPORT_IDENTITY记录，不能称全部输入逐字节相同。重叠的原FFN S128/S512均值与本任务已有结果完全一致。','',
        'SUMMARY.json保留各seed和逐段NLL；ARTIFACT_INDEX.json索引新/复用原件路径、大小和SHA；模型、文本、runtime校准及大原件保留本人授权服务器，不重复上传。数值输入、配置SHA、环境、24层执行audit均在摘要或原件中。离线统计使用experiments/qwen_joint_stratified_attention_20261019/summarize_sample_sweep.py；收集使用collect_results.py。','',
        '![Ising samples vs suffix PPL](PPL_CURVE.png)','']
    with (out/'RESULTS_ZH.md').open('w',encoding='utf-8',newline='\n') as f:
        f.write('\n'.join(rows))
    with (out/'PPL_CURVE.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.writer(f,lineterminator='\n');writer.writerow(['samples','original_ffn_ppl','original_ffn_seed_population_sd','b4_t32_ppl','b4_t32_seed_population_sd'])
        for x in r['curve']:writer.writerow([x[k] for k in ('samples','original_ffn_ppl_mean','original_ffn_ppl_population_sd','ppl_mean','ppl_population_sd')])


def figure(r,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    xs=[x['samples'] for x in r['curve']];e=r['candidate_exact_reference']
    fig,ax=plt.subplots(figsize=(10,6),dpi=150)
    for key,sd,label,color in [('original_ffn_ppl_mean','original_ffn_ppl_population_sd','Original FFN + Ising','#2878b5'),
                             ('ppl_mean','ppl_population_sd','B4/T32 FFN + Ising','#d86627')]:
        ax.errorbar(xs,[x[key] for x in r['curve']],yerr=[x[sd] for x in r['curve']],marker='o',capsize=3,label=label,color=color)
    ax.axhline(e['original_ffn_ppl_mean'],ls='--',lw=1.2,color='#2878b5',label='Original FFN + candidate-exact PV')
    ax.axhline(e['joint']['ppl_mean'],ls='--',lw=1.2,color='#d86627',label='B4/T32 FFN + candidate-exact PV')
    ax.axhline(r['baseline_bf16_ppl'],ls=':',lw=1.2,color='#555555',label='Original model / SDPA')
    ax.set_xscale('log',base=2);ax.set_xticks(xs,[str(x) for x in xs]);ax.set_xlabel('Retained Ising observations per query/head (S)')
    ax.set_ylabel('Suffix perplexity (lower is better)');ax.grid(alpha=.2);ax.set_title('Ising sample-count sweep: fixed screening and FFN')
    ax.legend(fontsize=9,loc='upper right');fig.text(.5,.01,'4096 fixed suffix targets; 3 seeds (mean +/- population SD); burn=16, spacing=4; exact SDPA attention prefill',ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.035,1,1));fig.savefig(out/'PPL_CURVE.png');fig.savefig(out/'PPL_CURVE.svg');plt.close(fig)


def main():
    p=argparse.ArgumentParser();p.add_argument('summary');p.add_argument('output');p.add_argument('--full-job',default='尚未提交');p.add_argument('--figure',action='store_true');a=p.parse_args()
    r=json.loads(Path(a.summary).read_text(encoding='utf-8'));out=Path(a.output);render(r,out,a.full_job)
    if a.figure:figure(r,out)
if __name__=='__main__':main()
