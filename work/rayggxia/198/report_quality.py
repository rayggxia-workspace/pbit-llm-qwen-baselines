"""Independent post-run audit and compact report from checksum-sealed artifacts."""
from pathlib import Path
import hashlib,json,math,statistics
R=Path(__file__).resolve().parents[3];W=Path(__file__).resolve().parent
D=R/'experiments/sparq_ising_20261028/results';D.mkdir(exist_ok=True)
A=Path('C:/Users/86134/Documents/a_P_BIT/project_archives/attention_compare_issue198_20261027/quality')
SHORT='d9b64717641a';FULL='a7108f8cba2c'

def load(p):
    data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==p.with_suffix('.json.sha256').read_text().strip(),p
    return json.loads(data)

def summary(rows,bf,exact):
    values=[r['perplexity'] for r in rows];nll=[r.get('mean_nll',r['nll_sum']/r['scored_tokens']) for r in rows]
    return dict(ppl_mean=statistics.mean(values),ppl_sample_std=statistics.stdev(values),ppl_per_seed=values,
        mean_nll=statistics.mean(nll),ppl_from_mean_nll=math.exp(statistics.mean(nll)),
        delta_ppl_percent_vs_bf16=100*(statistics.mean(values)/bf-1),delta_ppl_percent_vs_sparq=100*(statistics.mean(values)/exact-1))

out={'short_source':SHORT,'full_source':FULL,'model':'Qwen/Qwen3-4B','original_ffn':True,'hardware_ppa':None,'short':{}}
raw=A/SHORT/'results'/SHORT/'short';allrows={};reference_positions=None
for seed in range(3):
    folder=raw/f'seed{seed}';completed=load(folder/'complete.json')
    assert completed['status']=='completed'
    for name,sha in completed['files'].items():assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==sha
    for name in ('bf16','sparq_exact','winner_S32','winner_S128','winner_S512','iid_S128'):
        row=load(folder/(name+'.json'));assert row['scored_tokens']==1024 and row['tokens_per_layer']==[1024]*36
        assert row['original_ffn'] and len(row['audit']['layers'])==36
        assert row['plan']['every_full_corpus_target_once'] is False
        positions=row['plan']['target_positions_sha256_le_int64']
        if reference_positions is None:reference_positions=positions
        assert positions==reference_positions
        assert all(l['zero_fallback']==0 for l in row['audit']['layers'].values())
        assert math.isclose(row['perplexity'],math.exp(row['nll_sum']/1024),rel_tol=1e-14)
        assert len(row['records'])==8 and sum(r['scored_tokens'] for r in row['records'])==1024
        if name.startswith('winner'):
            samples=row['config']['samples'];burn=row['config']['burn']
            for layer in row['audit']['layers'].values():
                assert layer['sampled_head_rows']==1024*32
                assert layer['_activity'][0]==1024*32*(samples+burn)
                assert layer['_activity'][1]==1024*32*samples
        allrows.setdefault(name,[]).append(row)
bf=allrows['bf16'][0]['perplexity'];exact=allrows['sparq_exact'][0]['perplexity']
assert len({r['nll_sum'] for r in allrows['bf16']})==len({r['nll_sum'] for r in allrows['sparq_exact']})==1
for name,rows in allrows.items():
    out['short'][name]=summary(rows,bf,exact)
    if name.startswith(('winner','iid')):
        out['short'][name]['mean_unique_v_per_kv_group']=statistics.mean(sum(l['_unique_v'] for l in row['audit']['layers'].values())/(1024*36*8) for row in rows)
out['short_target_positions_sha256']=reference_positions
froot=A/FULL/'results'/FULL/'full'
full_complete=all((froot/f'seed{s}_S128/complete.json').exists() for s in range(3))
out['full_status']='complete' if full_complete else 'running_or_not_collected'
if full_complete:
    full={}
    full_unique={}
    for seed in range(3):
        folder=froot/f'seed{seed}_S128';receipt=load(folder/'complete.json')
        assert receipt['status']=='completed' and receipt['phase']=='full'
        provenance=load(folder/'provenance.json')
        assert provenance['source']['commit']=='a7108f8cba2c72ad319114af34557f4cec2b793d'
        assert provenance['token_count']==299078
        for name,sha in receipt['files'].items():assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==sha
        for name in ('bf16','sparq_exact','winner_S128'):
            row=load(folder/(name+'.json'));assert row['complete'] and row['scored_tokens']==299077
            assert row['seed']==seed
            expected=1
            for rec in row['records']:
                assert rec['first_target']==expected;expected=rec['last_target_exclusive']
            assert expected==299078
            parts=sorted(folder.glob(name+'_part*.json'))
            assert len(parts)==10
            unique=0
            part_rows=[]
            for part in parts:
                value=load(part);assert value['tokens_per_layer']==[value['scored_tokens']]*36
                assert value['seed']==seed and value['original_ffn']
                assert value['provenance_sha256']==hashlib.sha256((folder/'provenance.json').read_bytes()).hexdigest()
                part_rows.extend(value['records'])
                assert all(l['zero_fallback']==0 for l in value['audit']['layers'].values())
                if name.startswith('winner'):
                    for layer in value['audit']['layers'].values():
                        unique+=layer['_unique_v']
                        assert layer['sampled_head_rows']==value['scored_tokens']*32
                        assert layer['_activity'][0]==value['scored_tokens']*32*160
                        assert layer['_activity'][1]==value['scored_tokens']*32*128
            assert part_rows==row['records']
            assert math.isclose(math.fsum(r['nll_sum'] for r in part_rows),row['nll_sum'],rel_tol=1e-14)
            assert math.isclose(math.exp(row['nll_sum']/299077),row['perplexity'],rel_tol=1e-14)
            full.setdefault(name,[]).append(row)
            if name.startswith('winner'):full_unique.setdefault(name,[]).append(unique/(299077*36*8))
    bf2=full['bf16'][0]['perplexity'];ex2=full['sparq_exact'][0]['perplexity']
    assert len({x['nll_sum'] for x in full['bf16']})==len({x['nll_sum'] for x in full['sparq_exact']})==1
    out['full']={name:summary(rows,bf2,ex2) for name,rows in full.items()}
    for name,values in full_unique.items():out['full'][name]['mean_unique_v_per_kv_group']=statistics.mean(values)
    # Logical scalar demand with complete intra-group reuse, not physical traffic.
    dense=k_cost=v_exact=0
    for rec in full['bf16'][0]['records']:
        for step in range(rec['scored_tokens']):
            n=rec['prefill_tokens']+step+1
            dense+=2*n*128
            k_cost+=(n*32+128*96) if n>128 else n*128
            v_exact+=min(n,128)*128
    v_sample=statistics.mean(full_unique['winner_S128'])*299077*128
    out['full_logical_kv']={
        'scope':'per KV group per layer, summed over all scored queries; BF16 storage, ideal scalar-granular loads, selected K dimensions reused, shared Q-head V hits fully deduplicated',
        'dense_elements':dense,'sparq_k_elements':k_cost,'sparq_v_elements':v_exact,
        'winner_v_elements_mean':v_sample,
        'winner_vs_dense_ratio':(k_cost+v_sample)/dense,
        'winner_vs_sparq_ratio':(k_cost+v_sample)/(k_cost+v_exact),
        'exclusions':'No actual GPU/DRAM trace. No burst, layout, cache capacity, metadata, buffer, KV writes, p-bit, arbitration or accumulation cost.'}
(D/'SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n')
lines=['# SparQ + Ising赢家保持：Attention-only质量验证','',
       'Qwen/Qwen3-4B后训练版；原BF16 FFN/投影/归一化保持。r32/k128/local32，burn32、spacing1；源与模型/语料/token SHA见执行及收集回执。这里的纯SparQ指本项目固定GQA筛选版本，候选softmax/PV精确计算，不含均值V补偿；不等同于声称完整复现所有官方SparQ变体。',
       '', '## 1024目标后缀初筛（不是完整WT2）','',
       '|方案|PPL 三seed均值±样本标准差|相对BF16|相对纯SparQ|每KV组平均唯一V行|',
       '|---|---:|---:|---:|---:|']
for name,row in out['short'].items():
    unique=row.get('mean_unique_v_per_kv_group')
    lines.append(f'|{name}|{row["ppl_mean"]:.6f} ± {row["ppl_sample_std"]:.6f}|{row["delta_ppl_percent_vs_bf16"]:+.2f}%|{row["delta_ppl_percent_vs_sparq"]:+.2f}%|{unique:.2f}|' if unique is not None else f'|{name}|{row["ppl_mean"]:.6f} ± {row["ppl_sample_std"]:.6f}|{row["delta_ppl_percent_vs_bf16"]:+.2f}%|{row["delta_ppl_percent_vs_sparq"]:+.2f}%|—|')
lines+=['','## 完整WT2','', '固定S128、三seed、window2048/stride1024、299077目标，各方案同batch32/分片形状；分片随机键独立。']
if full_complete:
    lines+=['','|方案|PPL均值±样本标准差|相对BF16|相对纯SparQ|','|---|---:|---:|---:|']
    for name,row in out['full'].items():lines.append(f'|{name}|{row["ppl_mean"]:.6f} ± {row["ppl_sample_std"]:.6f}|{row["delta_ppl_percent_vs_bf16"]:+.2f}%|{row["delta_ppl_percent_vs_sparq"]:+.2f}%|')
    traffic=out['full_logical_kv']
    lines+=['',f'完整WT2 S128每KV组平均唯一V {out["full"]["winner_S128"]["mean_unique_v_per_kv_group"]:.3f}行。按实际各query长度求和、理想标量读取/维度复用/四Q去重，联合方案K+V元素需求为dense的{100*traffic["winner_vs_dense_ratio"]:.2f}%，为纯SparQ的{100*traffic["winner_vs_sparq_ratio"]:.2f}%。这只是逻辑需求估计，不能作为实测带宽或加速比。',
        '计算：N>128时K需求=32N+96×128，候选完整K的32个已读维度复用；N≤128时K需求=128N。纯SparQ的V需求=128×min(N,128)，采样V需求=128×各组命中并集。各query共用同一KV组的四Q，不把K/V重复计四遍。未计访存突发放大、布局、元数据、有限缓存、KV写入及采样/仲裁/累加。']
else:lines+=['','当前未收齐完整结果，不能以短流结果替代完整WT2验收。']
lines+=['','## 解释与限制','',
 '本实现的SparQ GQA共享候选筛选仍对每个Q头的全N近似logits做softmax，然后跨头求和排序。Ising仅替换候选K上的第二阶段softmax/PV；不能称消除了全部softmax。跨头概率求和通常不能直接改成logits求和，后者属于需要独立质量验证的另一筛选算法。r32筛选扫描、温度归一化、该softmax和top-k均须计价。',
 '短流S128与S512均值低于原BF16，但高于纯SparQ；不能称采样无损或通用提升。S32明显退化。S512赢家保持与IID128质量接近，提示相关性/有限链成本必须计入；IID是诊断对照，不是Ising实现。',
 '唯一V行是四Q头共享同KV组、假设能完全去重的逻辑集合，不是GPU HBM或DRAM实测。GPU参考先gather候选V，硬件可按采样命中延后读取；缓存、突发、bank/仲裁和有限buffer仍待实现。',
 'Ising每头候选节点上限128；每个保留样本仍有更新、仲裁、V读取与累加，burn32另计。FP32理想sigmoid/Philox不代表器件噪声、量化响应或真实硬件周期。',
 '原生同形状BF16包装门禁logits逐字节相同，参数地址与版本不变；全部计分目标经过36层单query，winner每头均采样，无额外PV抽样，零覆盖回退次数为0。',
 '三seed标准差是随机性离散程度，不是跨语料置信区间。每方案都使用同一测试子集，初筛已观察，完整S128结果为进一步验证而非独立训练集调参。',
 '未约定可接受PPL损失阈值；本轮验证质量，完整面积/功耗/速度竞争力仍需同工艺、同质量对照。没有新RTL/EDA/台账run。','']
(D/'REPORT_ZH.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
print(json.dumps(out,indent=2))
