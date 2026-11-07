from pathlib import Path
import hashlib,json,math,runpy,sys
WD=Path(__file__).resolve().parents[4]
PROJECT=WD.parents[1]
F=WD/'architecture_tlm/qk_supply_100mhz_20261107'
W=Path(__file__).parent
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def text(p,x):Path(p).write_bytes(x.encode())

s=load(W/'final_replay/SUMMARY.json')
seal=load(W/'final_replay/SEAL.json')['files_sha256']
for name,digest in seal.items():assert sha(W/'final_replay'/name)==digest,name
for name,digest in s['source_sha256'].items():assert sha(PROJECT/name)==digest,name
checks=['final replay seal and execution sources SHA match']
old={}
for manifest in ('sram1216','sampling_latency','attention_candidate_20261107'):
    for name,record in load(WD/f'work/rayggxia/225/{manifest}/SOURCE_MANIFEST.json').items():
        if name.startswith('architecture_tlm/'):
            assert sha(WD/name)==record['sha256'],name
            old[name]=record['sha256']
tt={}
for name,record in load(WD/'work/rayggxia/225/tt250_catalog_20261107/SOURCE_MANIFEST.json').items():
    if name.startswith('architecture_tlm/sram1216_20261106/250MHz/'):
        assert sha(WD/name)==record['sha256'],name
        tt[name]=record['sha256']
checks+=['32 original100MHz files unchanged','all6 isolated250MHz formal files unchanged']
assert len(old)==32 and len(tt)==6
owner=load(WD/'architecture_tlm/attention_candidate_20261107/INPUTS.json')['source_sha256']
assert sha(PROJECT/'architecture_tlm/attention_resource_compaction_20261107/model.py')==owner['architecture_tlm/attention_resource_compaction_20261107/model.py']
checks+=['owner resource actor unchanged and pinned']
for pair in s['pairs']:
    assert pair['external_bytes_unchanged'] and pair['actions_unchanged']
    assert pair['additional_read_words']==pair['additional_write_words']==pair['groups']*2048
checks+=['all6 paired work and external-address multiset checks', 'exact2048 extra read/write words per group']
for f in (W/'final_replay').glob('supply*.json'):
    r=load(f)
    for row in r['supply_audit']:
        assert row['scalar_MAC']==(262144 if row['kind']=='coarse' else 65536)
        assert row['max_ready_tiles']<=2
        assert row.get('max_operand_credits',0)<=4
    assert r['SRAM']['capacity_bytes']==1216*1024 and r['SRAM']['physical_banks']==304
    assert not r['memory']['final_pending'] and not r['memory']['final_response_occupied']
checks+=['coarse/selected MAC conservation and drained queues','two scratch tiles and four operand credits bounded',
    '1216KiB304bank16B1RW capacities retained']
# Rerun the exact original layout prototype without its file-writing entrypoint.
prototype=runpy.run_path(str(PROJECT/'architecture_tlm/qk_supply198_100mhz_20261107/transpose_check.py'),run_name='verify_layout')
layout=[prototype['check'](seed) for seed in (17,503,1009)]
record=load(PROJECT/'architecture_tlm/qk_supply198_100mhz_20261107/LAYOUT_CHECK.json')
assert layout==record['cases']
checks+=['three-seed original layout/integer oracle rerun unchanged; not independent hardware validation']

native=load(WD/'architecture_tlm/sampling_latency_20261106/COMPLETED_RESULTS.json')['rows'][1]['timing']
projection=s['whole36_projection']
resource_delta_ms=36*(640.21-605.30)/1000
head_delta_ms=(7419.06-7075.62)/1000
projection.update(old_resource_changes_prefix_delta_ms=resource_delta_ms,
    old_resource_changes_cold_head_delta_ms=head_delta_ms,
    including_lm_head_ms=native['including_lm_head']+resource_delta_ms+head_delta_ms+projection['additional_time_ms'],
    excluding_lm_head_stage_ms=native['excluding_lm_head_stage']+resource_delta_ms+projection['additional_time_ms'],
    method='old whole native T8/32 + prior native resource prefix delta x36 + cold-head delta + current supply delta x36; conditional estimate',
    new_whole_token_native_run=False)
# Background slope: only known SRAM macro leakage and existing FMA/SC idle.
runtime=PROJECT/'project_archives/ffn_sram_batch204_20261106/runtime'
prices=load(runtime/'PRICES.json')
sc=load(runtime/'architecture_tlm/digital_fair_20261105/LATEST_SC_PRICES.json')['profiles']['C20_GF64_snake_partial']
background_W=304*7.7544e-6+40*prices['digital']['fma16_c4']['idle_W']+12*sc['idle_W_per_core_proxy']
projection['known_background_slope_W']=background_W
projection['known_background_extra_mJ']=background_W*projection['additional_time_ms']
projection['known_supply_extra_energy_mJ']=sum(projection[k] for k in ('additional_SRAM_dynamic_mJ','transpose_register_capture_proxy_mJ','known_background_extra_mJ'))
projection['energy_note']='known calibrated/proxy subtotal only; no added route/control/reg idle/DRAM background; constant pJ/bit external energy unchanged'
s['validation']=dict(status='PASS',checks=checks,unchanged100_files=len(old),unchanged250_files=len(tt),
    new_jobs=False,new_RTL_PT=False,old_owner_250_followup_read_only=True)
save(F/'RESULTS.json',s)
save(F/'VALIDATION.json',s['validation'])
summary_rows='\n'.join('|%d|%d|%.2f|%.2f|%.2f|'%(p['groups'],p['seed'],p['old_us'],p['supply_us'],p['delta_us']) for p in s['pairs'])
text(F/'README_ZH.md',f'''# 100MHz共享QK：1KiB转置缓冲接入TLM

2026-11-07，Issue225 / PR248，负责人rayggxia。**已把转置和供数接入现有1216KiB宿主的真实bank/端口服务；没有要求Attention模块继续补交电路。** 原参考、原冻结快照和250MHz目录不变。

## 结果先看这里

|项目|本轮结果|
|---|---:|
|八组Attention旧供数宏／新有限供数，三seed均值|128.43／154.62µs|
|供数增量|26.19µs＝2619个100MHz周期/层|
|36层供数增量投影|0.943ms/token|
|新共享候选覆盖面积|41.463→41.562mm²55等效|
|相对原52.622mm²参考的面积减少|约21.0%|
|SRAM容量|仍1216KiB；其中划出8KiB转置双缓冲|
|新增寄存器预算|八组共2KiB：1KiB转置暂存＋1KiB操作数FIFO|
|36层额外SRAM动态能量|0.01416mJ/token|
|计入暂存/FIFO捕获代理及已知背景后的供数增量小计|约{projection['known_supply_extra_energy_mJ']:.3f}mJ/token|

整机**条件外推**约{projection['including_lm_head_ms']:.1f}ms/token含lm_head，约{projection['excluding_lm_head_stage_ms']:.1f}ms扣lm_head阶段。它由旧51.40648ms完整原生结果，加上此前资源缩减前缀/冷head增量，再加本轮供数增量组成；**不是新完成的整机原生LPDDR仿真**。不同阶段重叠可能改变增量，不能把小数位当预测精度。

## 实际怎样调度

精K仍只从外存读取原128候选的一份32KiB。组内采用两个512B SRAM块；每块分四个8×8微块，每次读取128B到转置暂存，再以完整16B字写回。源读取512B、转置写入512B、计算读取512B均真实经过BeatSRAM的bank/端口；没有竖读或字节写掩码。每个32B K向量只读取一次，广播给同KV组的四个Q头。

粗K从相同外存地址多重集中按64token×32维分块搬运，两份4KiB源块放在原有两槽中；每组四个FMA16切片保留四个反馈context，完成64token后才重用。精K同样按64token批次、按维度顺序维护context，不能靠无限寄存器保存全部token部分和。

新增一个**四槽×32B的粗K操作数FIFO/组**，把SRAM返回和FMA发射解耦。它的128B与用户原型的128B转置暂存分别计价，不能遗漏。仅使用原单向量输入寄存器时，八组seed17为198.71µs；四槽FIFO后154.65µs，面积多约0.04953mm²。早期把读请求放在反馈等待之后的串行诊断为208.28µs，已保留原源码/结果，不作为推荐调度。

双缓冲占物理49152..50176，位于现有每组64KiB内；与0..32768源K、16384..49152粗分数保留区、61440输出区按阶段/地址分开。不是额外新增8KiB SRAM，也没有保留被删bank的端口。

## 配对周期与守恒

|KV组数|seed|旧宏µs|新供数µs|增量µs|
|---:|---:|---:|---:|---:|
{summary_rows}

六对逐项核对QK MAC、PV ADD、样本数、唯一V、转换次数和各类外存字节/地址sum/xor。每组新增2048次16B源读和2048次16B转置写；计算读取已替换旧operand读取，没有重复加一次。队列全部排空，四操作数credit及两转置块均有界。{len(checks)}类核查通过；32个100MHz旧成果和6个250MHz文件SHA未变。

## 依据、假设及边界

- 本轮运行是**本地事务TLM**：片上真实16B/1RW bank竞争；外存采用与此前测试一致的136.4606GB/s、30ns解析服务，不冒充Ramulator/原生LPDDR。外存模型只影响本轮配对，不修改正式LPDDR模型。
- FMA反馈L4及II1沿用既有FMA16/C4服务合同，没有新STA/RTL；反馈改为8拍时，八组seed17变为214.42µs，敏感性已保留。
- 转置布局沿用Issue198原型，三seed整数IEEE oracle复跑一致；当前供数模型没有真实模型张量，不是新PPL或完整共享阵列门级验收。
- SRAM读/写10.0527／13.9599pJ每16B，保持寄存器面积及捕获活动用既有模块代理；每字节面积4.83721875e-5mm²已含0.81折算，不再乘0.81。新增控制、布线、广播扇出/CTS及寄存器idle仍未独立标定，可由宏参数补充，不记作0。
- 动态MAC/ADD及外存访问不变，不能按面积减少比例打折能量。额外约{projection['known_supply_extra_energy_mJ']:.3f}mJ只是供数的已计小计；外存按pJ/bit时不变，若采用待机状态模型，应再加待机功率×新增时间。
- Issue198另一套2KiB转置暂存/组与XOR布局，原生前缀643.51µs属于不同方案；只读参考，不混成此1KiB SRAM/128B暂存方案的验证或价格。新PV异步复位TT250修复也不写成SS100已经验收。

## 接入与复现

在旧宿主构造后，先安装`attention_candidate_20261107.integrate.install(m, owner_install, 'combined32')`，再安装本目录`model.install(m)`；首次事务前调用。宏默认仍保留参考，新方案显式选择。实际示例见run.py。

运行：`python -B architecture_tlm/qk_supply_100mhz_20261107/run.py --project C:/Users/86134/Documents/a_P_BIT --out <新的输出目录>`。约25秒完成12个配对运行与两个敏感性运行；只需CPU，无服务器作业。先按bootstrap核runtime和依赖SHA，输入为已核同SHA的代表候选/采样索引。大/私有输入保留原授权存储，Git只提交结果索引及小型汇总。来源、配置、检查及原始回放位置见RESULTS.json、VALIDATION.json和同Issue交接。
''')
text(F/'.gitattributes','* -text\n')
print(json.dumps(dict(status='PASS',checks=len(checks),area=s['area']['candidate55_proxy_mm2'],time_projection=projection)))
