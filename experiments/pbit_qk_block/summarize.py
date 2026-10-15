"""Audit block-scale extension against the archived single-scale experiment."""
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path('results/pbit_qk_block_20261006')
EXP=Path('experiments/pbit_qk_block')
OLD=Path('results/pbit_qk_20261006')


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def main():
    assert read(ROOT/'status.json')['stage']=='complete'
    for name,digest in read(ROOT/'protocol.json')['source_sha256'].items():
        assert hashlib.sha256((EXP/name).read_bytes()).hexdigest()==digest,name
    for name in ('test_sampling.json','test_integration.json'):
        assert read(ROOT/name)['status']=='passed'
    assert read(ROOT/'test_sampling.json')['legacy_block64_bitwise_identical']
    rs=[read(p) for p in sorted((ROOT/'evaluation').glob('*.json'))]
    assert len(rs)==76,len(rs)
    assert len({r['mlp_sha256'] for r in rs})==1
    assert len({r['text_sha256'] for r in rs})==1
    for r in rs:
        a=r['args']; ctx=a['context']
        assert r['attention_layers']==24 and a['decode']==128
        assert (a['examples'],a['batch'],r['scored_tokens'])==((32,16,4096) if ctx==2048 else (16,4,2048))
        assert r['value_aggregation']=='dense continuous PV; no value sampling'
        assert math.isfinite(r['perplexity'])
        assert math.isclose(math.exp(r['mean_nll']),r['perplexity'],rel_tol=1e-10)
        assert math.isclose(sum(e['nll_sum'] for e in r['examples'])/r['scored_tokens'],r['mean_nll'],rel_tol=1e-10)
        for name,digest in r['source_sha256'].items():
            assert hashlib.sha256((EXP/name).read_bytes()).hexdigest()==digest,name
        if a['block_size']==64:
            prev=read(OLD/'evaluation'/f"ctx{ctx}_{a['mode']}_b{a['samples']}_seed{a['seed']}.json")
            assert r['perplexity']==prev['perplexity'],'Original baseline changed'
    rows=[]; baselines={}
    keys=['unique_key_feature_fraction_per_head','unique_key_feature_fraction_GQA_group_union',
          'signed_add_events_relative_to_dense_mac_terms','score_relative_l2_global',
          'attention_KL_exact_to_sampled','attention_total_variation','attention_argmax_agreement']
    for ctx in (2048,8192):
        group=[r for r in rs if r['args']['context']==ctx]
        ref=read(OLD/'evaluation'/f'ctx{ctx}_sdpa_b4_seed0.json')
        positions=[e['first_target_token'] for e in ref['examples']]
        assert all([e['first_target_token'] for e in r['examples']]==positions for r in group)
        assert rs[0]['mlp_sha256']==ref['mlp_sha256'] and rs[0]['text_sha256']==ref['text_sha256']
        base={r['args']['mode']:r['perplexity'] for r in group if r['args']['mode'] in ('sdpa','dense')}
        baselines[str(ctx)]=base
        for block in (64,16,8):
            for B in (4,8,16,32):
                selected=[r for r in group if r['args']['mode']=='stratified' and r['args']['block_size']==block and r['args']['samples']==B]
                assert sorted(r['args']['seed'] for r in selected)==[0,1,2]
                values=[r['perplexity'] for r in selected]
                row={'context':ctx,'block_size':block,'scales_per_head':64//block,'B':B,
                     'ppl_mean':statistics.mean(values),'ppl_std':statistics.pstdev(values),'ppl_values':values}
                row['ppl_increase_percent']=100*(row['ppl_mean']/base['sdpa']-1)
                for k in keys:
                    row[k]=statistics.mean(r['sampling_stats'][k] for r in selected)
                    assert math.isfinite(row[k])
                rows.append(row)
    result={'evaluations':len(rs),'audit':'passed; source/FFN/text/targets matched; block64 exactly reproduces archived per-seed PPL',
            'baselines':baselines,'rows':rows,'protocol':read(ROOT/'protocol.json')}
    (ROOT/'comparison.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    lines=['# 分块尺度p-bit QK：论文基础方案的扩展对照（2026-10-06）','',
        '## 与原文的关系','',
        '这不是原论文第5节基础方案的原样复现。原方案为每个query头统一尺度；本轮改成RoPE后连续特征块各自取absmax尺度。',
        '每头64维，block=64/16/8分别对应1/4/8个尺度。保留block64作为论文式对照，原始实验源码和结果未改动。',
        '编码仍为b_i~Bernoulli(abs(q_i)/a_block)，另存符号，B轮后乘回a_block/B。每维期望仍为q_i，故线性QK估计无偏。',
        '只替换24层decode QK；连续K、原始PV/FFN、投影、RoPE和精确prefill保留；无训练。','',
        '## 对照协议','',
        '2k：32个WT2片段、2047 token精确prefix、128步缓存teacher-forcing，4096计分token。',
        '8k：16个片段、8191 token精确prefix、128步，2048计分token。位置和上一轮完全相同。',
        '分层采样B=4/8/16/32，块大小64/16/8，每配置3个推理seed，外加四个密集基线，共76项。',
        '±为推理seed总体标准差，不是独立文本置信区间。追加改进仍使用同一测试集，结果为探索性比较。',
        '50000次概率测试验证不同块尺度的均值和解析方差，检查零块，并确认block64与旧编码逐位一致。',
        '缓存集成检查通过；76项源码/FFN/文本哈希、计分位置和PPL计算核验通过；所有block64逐seed PPL精确复现旧结果。','',
        '## 结果','']
    for ctx in (2048,8192):
        lines += [f'### 起始上下文{ctx}', '',f"原始SDPA PPL：{baselines[str(ctx)]['sdpa']:.6f}。",'',
            '| 块维度 | 尺度数/头 | B | PPL均值 ± 标准差 | 相对原始增加 | GQA组Key访问 | 加减事件/原始MAC项数 |',
            '| ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
        for r in rows:
            if r['context']!=ctx: continue
            lines.append(f"| {r['block_size']} | {r['scales_per_head']} | {r['B']} | {r['ppl_mean']:.6f} ± {r['ppl_std']:.6f} | {r['ppl_increase_percent']:.2f}% | {100*r['unique_key_feature_fraction_GQA_group_union']:.5f}% | {r['signed_add_events_relative_to_dense_mac_terms']:.3f} |")
        lines += ['']
    lines += ['## 精度与成本应分开看','',
        '分块使a_block不大于全头尺度，缩小随机舍入的步长；但分数尺度恢复从每头一个系数变成4/8个。',
        '位流硬件若按块累加，需要分别计算块内符号加减、乘回各块连续尺度，再合并各块输出。当前软件重构浮点query后做密集矩阵乘法，只验证数值效果。',
        '同B下，较小尺度也使abs(q)/a_block更大，通常增加选中事件及Key访问。改善精度不等于同成本改善。',
        '每个非零块的最大幅度分量被精确编码；块数增加也增加这种精确分量。极限block=1会把全部幅度放入连续尺度、概率变成0或1，等价回到原始连续乘法，不能作为p-bit加速。',
        '表中Key访问是B轮及GQA组7头的逻辑特征并集，不是实际DRAM事务。加减事件比例也不是速度或能耗比。',
        '未实现真实稀疏GPU内核、真实器件驱动或连续尺度电路，也未叠加随机PV/FFN。',
        '本轮可用于检验全头共享尺度是否限制低预算精度，不能据此声称复现了论文BitNet的4次结果或完全解决硬件成本。','',
        '![Block scale comparison](quality_access.png)','',
        '源码与复现：[experiments/pbit_qk_block](../../experiments/pbit_qk_block/README.md)。']
    (ROOT/'RESULTS_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(11,7.5),constrained_layout=True)
    for col,ctx in enumerate((2048,8192)):
        for block in (64,16,8):
            selected=[r for r in rows if r['context']==ctx and r['block_size']==block]
            x=[r['B'] for r in selected]
            label=f'{block} features/scale ({64//block} scales/head)'
            axes[0,col].plot(x,[r['ppl_mean']/baselines[str(ctx)]['sdpa'] for r in selected],'o-',label=label)
            axes[1,col].plot(x,[100*r['unique_key_feature_fraction_GQA_group_union'] for r in selected],'o-',label=label)
        axes[0,col].axhline(1,color='gray',linestyle='--')
        axes[0,col].set(yscale='log',ylabel='PPL / original PPL',title=f'{ctx}-token context')
        axes[1,col].set(ylabel='Logical GQA key features read (%)',ylim=(80,100.5))
        for ax in axes[:,col]:
            ax.set_xscale('log',base=2); ax.set_xlabel('B (stratified query sampling rounds)')
            ax.grid(alpha=.25); ax.legend(fontsize=8)
    fig.suptitle('Block-scale extension of signed p-bit QK\nOriginal FFN/PV; three seeds; dense arithmetic reference',fontsize=12)
    fig.savefig(ROOT/'quality_access.png',dpi=160); plt.close(fig)
    print(json.dumps({'status':'passed','evaluations':len(rs),'baselines':baselines,'rows':rows},indent=2))


if __name__=='__main__': main()
