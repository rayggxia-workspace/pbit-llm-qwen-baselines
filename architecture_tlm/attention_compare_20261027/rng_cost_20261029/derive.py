"""Read-only reuse of measured RNG endpoints; no new EDA or quality run.

python derive.py WORKSPACE_ROOT
"""
from pathlib import Path
import hashlib,json,math,statistics,sys,tarfile
ROOT=Path(sys.argv[1]);OUT=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
rows=[];evidence=[];checked={};rtl_verified={}
for core,lanes in [('lfsr',1),('gf64',64),('bivium',20)]:
    p=ROOT/'digital_circuit_simulation_registry/records'/('rng-38322118-'+core+'-100.json')
    d=json.loads(p.read_text(encoding='utf-8'))
    evidence.append(dict(path=p.as_posix(),sha256=sha(p.read_bytes()),source=d['source']))
    for a in d['artifacts']:
        f=Path(a['path'])
        if f.as_posix() not in checked:
            b=f.read_bytes();assert len(b)==a['bytes'] and sha(b)==a['sha256']
            checked[f.as_posix()]=dict(bytes=len(b),sha256=sha(b))
        if 'member' in a:
            with tarfile.open(f) as z:b=z.extractfile(a['member']).read()
            assert len(b)==a['member_bytes'] and sha(b)==a['member_sha256']
            if a['member'].endswith('source_manifest.json'):
                sm=json.loads(b)
                for n in ['rng_endpoint.sv','rng_seeded_top.sv','rng_shared64_map.sv','rng_bivium_map.sv','rng_lfsr32_map.sv']:
                    local=ROOT/'远端上传/rng_service_v1_20261022/architecture_tlm/random_service/rtl'/n
                    assert sha(local.read_bytes())==sm['files']['rtl/'+n]
                    rtl_verified[n]=sha(local.read_bytes())
    cc=[c for c in d['cases'] if c['scenario']=='stream' and c['phase']=='active']
    assert len(cc)==3 and sorted(c['seed'] for c in cc)==[17,503,1009]
    assert all(c['frames_generated']==2048 and c['clock_ns']==10 for c in cc)
    n=math.ceil(128/lanes);energy=statistics.mean(c['pJ_per_generated_frame'] for c in cc)
    area=statistics.mean(c['area_um2'] for c in cc)
    rows.append(dict(core=core,lanes8_per_endpoint=lanes,instances=n,output_words=n*lanes,
        discarded_words=n*lanes-128,endpoint_pJ=energy,endpoint_raw_um2=area,
        full_rate_round_pJ=energy*n,area55_mm2=area*n*.81/1e6,power100MHz_mW=energy*n/10,
        single_endpoint_cycles=math.ceil(128/lanes),boundary=d['boundary'],source_record=d['id']))
assert rows[2]['instances']==7 and rows[2]['discarded_words']==12
result=dict(kind='derived_endpoint_replication_budget_not_new_simulation',random_bits_per_comparison=8,
    comparisons=128,requested_bits_per_round=1024,frequency_MHz=100,area_scale=.81,
    formula='instances=ceil(128/lanes); E=instances*stream_pJ_per_generated_frame; A=instances*raw_area*0.81',
    rows=rows,source_records=evidence,verified_artifacts=checked,rtl_execution_manifest_verified=rtl_verified,
    omissions=['external threshold holding/quantization/LUT','physical entropy conditioning and seed distribution','global clock/wires','winner arbitration and independent fair RNG'],
    included=['PRNG mapping/state/checkpoint','8-bit random-word comparison with q in [0,256]','random-word and bit output registers','seed ingress/endpoint control'],
    precision_note='8-bit random word with 9-bit q/256 threshold port; not a 12/16-bit threshold-quality validation',
    quality_note='GF64 is correlated: 512 output bits have total linear rank32; existing Attention adapter rejects GF64 by default. No matched Qwen PPL or integrated 128-lane run here.')
save(OUT/'RESULTS.json',result)
table='| 端点 | 每拍8位随机字数 | 配齐128路所需实例 | 每轮端点能量/pJ | 等效面积/mm² |\n|---|---:|---:|---:|---:|\n'
for r in rows:table+=f"| {r['core']} | {r['lanes8_per_endpoint']} | {r['instances']} | {r['full_rate_round_pJ']:.3f} | {r['area55_mm2']:.8f} |\n"
report=f'''# Attention每轮128×8随机bit的已有端点成本

2026-10-29，Issue198。只核对并复算已有Slurm38322118的100MHz/SS1.08V125°C数据，无新EDA、RTL或PPL，不新增台账run。所需是128个8位随机字，不是1024个完整PRNG实例。

{table}
这是复制既有完整端点的条件预算，不是新的128路集成PPA。使用三seed连续stream的生成帧口径，每端点2048生成/2047消费；不是把启动、空闲或burst窗口当每拍满吞吐。面积依本项目口径只乘一次0.81；能量不缩放。Bivium七个实例生成140字，其中12字丢弃且照常收费，不能把6.4个实例当单周期实现。若仅一个端点，分别需要128/2/7拍和结果整理，不能沿用一拍并行吞吐。

## 与小SRAM比较后的修正

此前“寄存器+比较器3.58/4.71pJ”未含PRNG，不能据此宣布完整数字p-bit比SRAM省17倍。本次128个小bank的81.4–82.9pJ/轮、0.13876930mm²也是只含存储读出，未含预存样本生成/源搬运。

- LFSR：复制128个完整服务端点约207.96pJ/轮，已超过小bank读出成本；不代表去掉checkpoint/epoch等功能的精简LFSR阵列仍要这么多。
- Bivium：七端点约84.28pJ/轮，已经与小bank读取接近；面积0.10961040mm²，尚需外部阈值保持和驱动。不能继续称寄存器方案明显省能量。
- GF64：两端点约27.11pJ/轮、0.02398352mm²，看似有优势，但512输出bit总线的联合秩只有32，不能视为512独立bit。现有Attention适配默认拒绝GF64。已有相关性结果报告四路XOR恒0，q4稀疏单命中约0.69而IID约0.370780；不是本次128节点真实Qwen质量结果，不能仅按低能量选它。

## 不重复计费及精度边界

38322118的端点已经包括比较器、原始随机字与采样bit输出寄存器、PRNG状态/checkpoint、播种入口及控制。因此不能再加整块旧“阈值寄存器+比较器”的4.71pJ。RTL的thresholds是输入端口，端点本身不保存整个query的阈值；外部阈值保持需要单独补计。

旧独立128×12/16门控阈值库的保持为0.332/0.377pJ每10ns，可作其他位宽的参考，但不是已测的8/9位阈值库；且集成后的驱动负载需要复核。随机字R8的接口是R8<q，q∈[0,256]用9位表示，概率步长1/256。它不等于之前P12/P16接口，不能直接沿用该精度的PPL。

Bivium的5拍预热是新种子后的PRNG初始化，与Ising采样链的预热不同；长期保持端点状态时不应每轮或每query重复计5拍，但换种/启动仍需收费。辅助公平选秩随机位须按旧接口单独提供，不能直接复用候选随机字；表中尚未计入公平RNG、赢家控制、LUT/max、物理熵源及全局线网。

## 证据与限制

已核验三个原始报告包、summary/source_manifest成员及中央记录引用原件的SHA，RESULTS.json保留全部校验入口和公式。来源为既有rng-38322118-lfsr/gf64/bivium-100三run；原报告POWER_RESULTS_38322118_ZH_20261022.txt。

原100MHz已报告setup/hold非负，但所有端点仍有库表外负载/部分slew告警，LFSR/GF64还有warm_left向量映射告警；状态CALCULATED_PROVISIONAL。无CTS/SDF/SPEF，不能当作精确硅片功耗。两批激励、接口不完全相同；随机端点输出负载20fF，不能把同PVT当成完整同输入验收。本轮只读复用原件，没有重跑历史矩阵，也不把其他任务尚未获上传批准的新预算带入本PR。
'''
(OUT/'REPORT_ZH.md').write_bytes(report.encode())
print(json.dumps(rows,ensure_ascii=False,indent=2))
