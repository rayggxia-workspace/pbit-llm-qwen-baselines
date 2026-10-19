"""Post-execution summary: never pool prefixes, baselines, or sample lengths."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import statistics


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def summarize(collections_paths,output):
    rows=[]; artifacts=[]; executions=[]; calibration_info=[]
    for cp in collections_paths:
        evidence=json.loads(Path(cp).read_text(encoding='utf-8'))
        assert evidence['source_rechecked']
        raw=Path(evidence['raw_local']);sub=evidence['submission']
        identity=json.loads((raw/'identity.json').read_text(encoding='utf-8'))
        assert identity['status']=='verified'
        for rel,e in evidence['manifest'].items():
            f=raw/rel
            assert f.stat().st_size==e['bytes'] and digest(f)==e['sha256'],rel
            artifacts.append(dict(execution_commit=sub['commit'],relative_path=rel,
                server_path=sub['output']+'/'+rel,**e))
        executions.append(dict(commit=sub['commit'],jobs=[sub['prepare_job'],sub['array_job']],
            source_rechecked=True,expected_replacements=sub['cases'],output=sub['output'],
            identity_sha256=digest(raw/'identity.json'),calibration_sha256=digest(raw/'static_calibration.json')))
        cal=json.loads((raw/'static_calibration.json').read_text(encoding='utf-8'))
        exponents={}
        import math
        for stage in ('x','z'):
            vals=[x for d in cal['layers'].values() for x in d[stage]['q9999']]
            es=[math.ceil(math.log2(max(x,1e-20))) for x in vals]
            exponents[stage]=dict(groups=len(vals),min_exponent=min(es),max_exponent=max(es),
                distinct_exponents=sorted(set(es)))
        calibration_info.append(dict(execution_commit=sub['commit'],train_tokens=cal['train_tokens'],
            train_ids_sha256=cal['train_ids_sha256'],q9999_ceil_pow2=exponents))
        expected=json.loads((raw/'suite.json').read_text(encoding='utf-8'))['cases']
        actual={f.stem for f in (raw/'runs').glob('*.json') if not f.name.startswith('bf16_')}
        assert actual=={c['name'] for c in expected},(len(actual),len(expected))
        for f in sorted((raw/'runs').glob('*.json')):
            d=json.loads(f.read_text(encoding='utf-8'));cfg=d['configuration']
            assert d['scored_tokens']==d['input_tokens']-1
            row=dict(configuration=cfg,execution_commit=sub['commit'],protocol=d['protocol'],
                perplexity=d['perplexity'],nll=d['nll'],tokens=d['scored_tokens'],
                forward_seconds=d['forward_seconds'],artifact_sha256=digest(f),
                token_ids_sha256=d['token_ids_sha256'])
            if cfg['kind']=='baseline':
                assert d['baseline_gate_passed']
            else:
                assert d['code_commit']==sub['commit'] and d['attention']=='unchanged BF16 SDPA'
                ds=list(d['diagnostics'].values());assert len(ds)==24
                for stage in ('x','z'):
                    count=sum(x[stage+'_values'] for x in ds)
                    for stat in ('mean_probability','zero_fraction','clip_fraction','p_one_fraction'):
                        row[stage+'_'+stat]=sum(x[stage+'_'+stat]*x[stage+'_values'] for x in ds)/count
                    row[stage+'_layer_mean_encoding_nmse']=statistics.mean(x[stage+'_encoding_nmse'] for x in ds)
            rows.append(row)
    groups=collections.defaultdict(list)
    for r in rows:
        c=r['configuration']
        if c['kind']!='baseline':
            groups[(c['policy'],c['kind'],c['input_tokens'],c['cycles'])].append(r)
    grouped=[]
    for (p,k,n,t),rs in sorted(groups.items()):
        assert sorted(r['configuration']['seed'] for r in rs)==([0,1,2] if k=='dual' else [0])
        assert len({r['token_ids_sha256'] for r in rs})==1
        values=[r['perplexity'] for r in rs]
        g=dict(policy=p,kind=k,input_tokens=n,scored_tokens=n-1,cycles=t,
            seeds=[r['configuration']['seed'] for r in rs],ppl_mean=statistics.mean(values),
            ppl_population_std=statistics.pstdev(values),nll_mean=statistics.mean(r['nll'] for r in rs),
            forward_seconds_mean=statistics.mean(r['forward_seconds'] for r in rs))
        for stage in ('x','z'):
            for stat in ('mean_probability','zero_fraction','clip_fraction','p_one_fraction','layer_mean_encoding_nmse'):
                g[stage+'_'+stat]=statistics.mean(r[stage+'_'+stat] for r in rs)
        grouped.append(g)
    summary=dict(executions=executions,calibration=calibration_info,groups=grouped,
        baselines=[r for r in rows if r['configuration']['kind']=='baseline'],
        rows=rows,limitations=['Replacement scores are fixed prefixes, not full WT2',
        'Mild follow-up registered after .75 mean failure; exploratory same text, not independent final score',
        'No new training/RTL/PT/TLM or physical RNG replay',
        'No calibration values or raw activations published'])
    out=Path(output);write(out/'SUMMARY.json',summary)
    write(out/'ARTIFACT_INDEX.json',dict(artifacts=artifacts,storage='Existing authorized personal server projects; access required',
        verified_files=len(artifacts),all_transferred_sha256_verified=True,execution_sources_rechecked=True))
    def label(g):
        return f"{g['ppl_mean']:.4f} ± {g['ppl_population_std']:.4f}" if g['kind']=='dual' else f"{g['ppl_mean']:.4f}"
    lines=['# Qwen随机FFN：截断与固定二次幂范围结果','',
        '负责人jieruiz，Issue39/PR40。全部24FFN，Attention保持原BF16 SDPA；自然IID，输入共享64、W逐连接独立，精确联合/条件计数，无OR、无Gaussian、无训练。',
        '', '**替换结果都是同一WT2测试前缀PPL，不是完整WT2。** 每组双随机seed0/1/2，表为PPL算术均值±总体标准差；无采样期望用于隔离编码偏差。', '',
        '原BF16完整WT2重新复现11.652735（299077目标）；512token前缀12.089225，2048token前缀9.328747。不得跨协议直接比较。', '']
    for n,t in ((512,256),(512,128),(2048,256)):
        lines += [f'## {n} token前缀，T={t}', '', '|策略|无采样期望PPL|双随机PPL|x截断比例|z截断比例|', '|---|---:|---:|---:|---:|']
        selected=[g for g in grouped if g['input_tokens']==n and g['cycles']==t and g['kind']=='dual']
        for g in selected:
            means=[x for x in grouped if x['policy']==g['policy'] and x['kind']=='mean' and x['input_tokens']==n]
            lines.append(f"|{g['policy']}|{label(means[0]) if means else '—'}|{label(g)}|{100*g['x_clip_fraction']:.5f}%|{100*g['z_clip_fraction']:.5f}%|")
        lines += ['']
    lines += ['## 方法与证据边界','',
        'control是原dynamic64/row64，最高概率255/256；dynamic100_one只改为满幅显式恒1。dynamic095/090/075/050把每组当次最大幅度分别乘0.95/0.90/0.75/0.50，超出范围恒1；dynamic_z050仅缩z。fixed999/fixed9999用8192个train-token、逐层每64通道99.9/99.99绝对值分位，推理不求最大值。potA将激活尺度向上取2的幂；potAW额外将同一W8的权重行组尺度向上取2的幂。', '',
        '主53case与补充12case来自两个不可变提交；补充在最早0.75无采样结果失败后注册，加入0.95/0.90和端点对照。它是同一文本上的探索，不能当独立最终评估。主2048确认三策略在任何test结果之前固定，没有按512成绩挑选。', '',
        'g/u先恢复FP32，再准确SiLU(g)×u，然后以z自己的范围重编码供Wd。没有全比特流非线性。静态阈值来自原BF16 teacher，传播噪声造成的漂移由test PPL覆盖；不保证所有部署文本越界率相同。', '',
        '完整模型质量、真实PRNG相关性、物理源偏差、进一步权重裁剪和新PPA均未由本轮验证。输入和权重分布、固定尺度电路成本及参考论文见[电路分析](../../../experiments/qwen_ffn_clipping_20261019/SCALING_HARDWARE_ZH.md)。', '',
        '逐项执行提交、job、hash见SUMMARY/ARTIFACT_INDEX；原始校准及逐case详细diagnostics在索引指向的授权服务器，未公开上传。', '']
    (out/'RESULTS_ZH.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    print(json.dumps(dict(results=len(rows),groups=len(grouped),artifacts=len(artifacts),output=str(out))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--collection',action='append',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();summarize(a.collection,a.output)
