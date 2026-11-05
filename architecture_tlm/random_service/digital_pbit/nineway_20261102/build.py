"""Reproducible arithmetic only. No EDA, no new random-quality claims."""
import json, math, hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent

def main():
    data=json.loads((HERE/'INPUTS.json').read_text(encoding='utf-8'))
    n=128; t=1e-8; rows=[]; f=data['fees_SS']
    for k in (1,64,128):
        for share in (1,4,8):
            m=n//share; load=0 if share==1 else share; duration=(load+k)*t
            for source,r in data['sources'].items():
                instances=math.ceil(n/r['words_per_cycle'])
                e_rng=instances*(r['stream_uW']*1e-6*k*t+r['idle_uW']*1e-6*load*t)
                e_lut=m*f['lut'][1]*duration+n*f['lut'][2]
                e_cache=0 if share==1 else n*(f['q_hold_proxy'][1]*duration+f['q_hold_proxy'][2])
                # During LOAD threshold changes can toggle the external comparator input.
                # SAMPLE comparisons/output holding are ALREADY in the whole endpoint.
                e_load_compare=0 if share==1 else n*f['compare'][2]
                energy=e_rng+e_lut+e_cache+e_load_compare
                row=dict(share=share,source=source,nodes=n,luts=m,instances=instances,K=k,
                    load_cycles=load,total_cycles=load+k,output_bits=n*k,
                    effective_Gbit_s=n*k/duration/1e9,
                    average_mW=energy/duration*1e3,J_per_bit=energy/(n*k),
                    pJ_per_bit=energy/(n*k)*1e12,endpoint_J=e_rng,LUT_J=e_lut,
                    cache_proxy_J=e_cache,load_compare_proxy_J=e_load_compare,
                    total_J=energy,evidence='conditional_composition_not_integrated_PPA')
                assert math.isclose(row['J_per_bit']*row['output_bits'],row['total_J'])
                assert math.isclose(row['average_mW']*1e-3/(row['effective_Gbit_s']*1e9),row['J_per_bit'])
                assert instances*r['words_per_cycle']>=n
                rows.append(row)
    result=dict(input_sha256=hashlib.sha256((HERE/'INPUTS.json').read_bytes()).hexdigest(),
                rows=rows,arithmetic_checks=81,new_simulation=False)
    (HERE/'RESULTS.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
    lines=['# 100MHz数字p-bit：三种输出结构×三种随机源','',
    '2026-11-02，接续Issue95/已合并PR215。已有单核/端点表，本表新增九项组合预算；无新EDA。',
    '', '**本表是条件组合估算，不是九套电路实测。** 统一128节点、SS1.08V125℃、100MHz。1 bit表示一个有效Bernoulli输出，不是R8的某一位，也不是认证独立熵bit。',
    '', '“4合一/8合一”解释为每4/8节点共享一张表，即128节点用32/16张表；不是整个阵列只用4/8张表。8位寄存器解释为保存查表后的概率q，比较器仍每节点一份。',
    '', '随机源采用38322118整套服务端点：LFSR/GF64/Bivium分别128/2/7份。端点已含比较器、输出保持、种子与控制，SAMPLE不再加比较器或融合核。Bivium产生140个字，用128个，12个照常收费。不是将128个p-bit都配一份64路GF宏。',
    '', '主表K=64：每个概率使用64次；全LUT的局部场由上游已有状态保持，状态费用未计。共享先LOAD4/8拍，再并行采64拍；不假定免费双缓冲或重叠，LOAD无有效输出。启动/重播种未摊入，沿用已初始化状态。',
    '', '## 主表：K=64（128节点整个模块的平均功率）','',
    '| 结构 | 随机源 | LUT数 | PRNG端点数 | 平均mW | 有效Gbit/s | pJ/输出bit | J/输出bit |',
    '|---|---|---:|---:|---:|---:|---:|---:|']
    names={1:'逐节点LUT＋比较',4:'q8寄存＋4节点共享LUT＋比较',8:'q8寄存＋8节点共享LUT＋比较'}
    for r in rows:
        if r['K']==64:lines.append('| %s | %s | %d | %d | %.6f | %.6f | %.6f | %.6e |'%(names[r['share']],r['source'],r['luts'],r['instances'],r['average_mW'],r['effective_Gbit_s'],r['pJ_per_bit'],r['J_per_bit']))
    lines+=['','## 概率复用次数敏感性','',
    '| 结构 | 随机源 | K=1 pJ/bit | K=64 pJ/bit | K=128 pJ/bit |',
    '|---|---|---:|---:|---:|']
    for share in (1,4,8):
        for source in data['sources']:
            v=[next(r['pJ_per_bit'] for r in rows if r['K']==k and r['share']==share and r['source']==source) for k in (1,64,128)]
            lines.append('| %s | %s | %.6f | %.6f | %.6f |'%(names[share],source,*v))
    lines+=['','## 计算公式与边界','',
    'T=10ns，N=128，LUT数M=N/share；LOAD=L=0/4/8，采样K拍，B=N×K。',
    'E端点 = 实例数×(P_stream×K + P_idle×L)×T。LOAD采用开钟idle，无ICG优惠。',
    'E表 = M×P_lut_idle×(L+K)×T + N×ΔE_lut。局部场仅在配置时改变。',
    '共享缓存E = N×[P_q代理_idle×(L+K)×T+ΔE_q代理]；另计LOAD阈值变化触发N次比较增量，SAMPLE比较已在端点内。',
    'P平均=E总/[(L+K)T]；J/bit=E总/(NK)。INPUTS记录SS参数、原件SHA，RESULTS保留逐项能量及27行完整结果。',
    '', '**q8缓存还没有可直接套用这两种阵列的独立PPA**：沿用已合并Catalog的“寄存表−组合表”q9/valid映射残差代理，既不叫8DFF实测，也不按8/9缩能量。未知写译码、选择器、额外互连/驱动/ICG成本未计；输入x保持成本也未计，不能据此称完整同边界阵列胜负。',
    '', '严格q8不能保存256。共享行功能按min(q,255)，p=1变255/256；主表全LUT端点保留q9端点。若要求所有结构精确等价，须给共享缓存补端点标志/借用已有符号状态或使用q9，并重新计费。不能用此表宣称质量相同。',
    '', '端点与LUT来自不同合成激励/负载：端点20fF、单核1fF；固定阈值期间仍以端点stream活动价做预算，不是新的联合门级活动。未知集成项不是零成本，也没有把整端点成本称为裸PRNG。所有原始库表/活动告警、无CTS/SPEF边界继续保留。',
    '', 'GF64的线性联合相关仍存在，低J/bit不证明可替代独立采样。此表不混入Attention整套Ising的公平源、仲裁/赢家、计数器，也不把其每query能量除128冒称纯p-bit。后续精简数字源可能明显比旧整端点省能，但三类须同样精简后才可公平比较。',
    '', '本轮只整理功率与能量，没有新面积结论；面积如后续增加，原报告保留，项目面积系数0.81只乘一次，功率/能量不乘0.81。',
    '', '来源：已有digital_pbit/RESULTS_ZH.md、catalog.json、38427136_SUMMARY；中央rng-38322118-{lfsr,gf64,bivium}-100记录；精确输入SHA见INPUTS。此表不改变TLM默认，不新增电路run。']
    (HERE/'REPORT_ZH.md').write_bytes(('\n'.join(lines)+'\n').encode())
    print('\n'.join(lines[14:28]))

if __name__=='__main__':main()
