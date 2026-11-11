"""Verify the SRAM policy against sealed results; preserve original artifacts."""
from pathlib import Path
import ast,copy,hashlib,importlib,json,math,sys,types

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
WS=ROOT.parents[1]
FOLDER=ROOT/'architecture_tlm/sram1216_20261106/250MHz'
OTHER=WS/'tmp/cross-model245-20261106'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
def write(p,s):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(s.encode())

# Use this exact overlay, rather than any older complete checkout on sys.path.
sys.path.insert(0,str(ROOT))
pkg=types.ModuleType('cim_policy_check250');pkg.__path__=[str(FOLDER)]
sys.modules[pkg.__name__]=pkg
price=importlib.import_module(pkg.__name__+'.pricing').price
cost=importlib.import_module(pkg.__name__+'.cim_weight_policy').weight_read_cost
rows=[];sources={}
for seed,folder in zip((17,503,1009),('0','1','2')):
    archived=WS/'project_archives/tlm_energy225_20261108'/folder
    r=json.loads((archived/'RESULT.json').read_bytes())
    old=json.loads((archived/'BUDGET.json').read_bytes())
    identities={n:sha(archived/n) for n in ('RESULT.json','BUDGET.json')}
    new=price(r);policy=new['CIM_weight_energy_policy']
    assert policy['weight_frames']==328320
    tags=r['memory']['SRAM']['by_tag']
    fills=sum(tags[k]['write_words'] for k in ('GU_weights_fill','down_weights_fill'))
    assert fills==policy['equivalent_read_words']==168099840
    delta=new['totals']['modeled_onchip_mJ']-old['totals']['modeled_onchip_mJ']
    assert math.isclose(delta,policy['additional_uJ']/1000,abs_tol=1e-10)
    assert new['totals']['covered_area55_mm2']==old['totals']['covered_area55_mm2']
    assert new['latency']==old['latency'] and new['bandwidth']==old['bandwidth']
    assert new['FFN_core_calibration']==old['FFN_core_calibration']
    assert identities=={n:sha(archived/n) for n in identities}
    # Reuse the same already-billed reads; a later explicit trace must add zero.
    explicit=copy.deepcopy(r)
    explicit['memory']['SRAM']['by_tag']['CIM_weight_presentation_read']={'read_words':fills}
    assert cost(explicit,12.0293)['additional_uJ']==0
    rows.append(dict(seed=seed,time_ms=r['time_ns']/1e6,
        old_onchip_mJ=old['totals']['modeled_onchip_mJ'],
        new_onchip_mJ=new['totals']['modeled_onchip_mJ'],added_read_mJ=delta,
        new_system4pJ_mJ=new['totals']['modeled_system_mJ_by_pJ_per_bit']['4.0'],
        area55_mm2=new['totals']['covered_area55_mm2'],policy=policy,
        original_archive=str(archived),original_sha256=identities))
    sources[str(archived)]=identities
    # Sample count does not multiply resident-weight reads.
    changed=copy.deepcopy(r);changed['short_FFN_contract']['GU_samples']=128
    assert cost(changed,12.0293)==policy

mean=lambda k:sum(z[k] for z in rows)/len(rows)
summary=dict(status='PASS_REPRICING_ONLY_NO_NEW_TIMING_RUN',rows=rows,
    mean={k:mean(k) for k in ('time_ms','old_onchip_mJ','new_onchip_mJ','added_read_mJ','new_system4pJ_mJ','area55_mm2')},
    checks=['three_sealed_seed_price_replays','write_words_equal_weight_read_footprint',
            'area_latency_bandwidth_core_price_unchanged','already_counted_reads_not_double_billed',
            'sampling_count_does_not_multiply_weight_reads','original_artifacts_SHA_unchanged'],
    scope='55nm250;ordinary SRAM weight-interface proxy selected by user;100MHz/28nm unchanged',
    new_RTL_PT=False,new_TLM_timing=False)
out=FOLDER/'CIM_SRAM_POLICY_20261109.json';dump(out,summary)
doc='''# CIM权重接口：普通SRAM能量代理

2026-11-09，用户决定；Issue225/PR249，跨模型接口接续Issue245/PR247。

定制CIM权重并行接口采用现有普通SRAM读写功耗，不再作为主线待补仿真项。保留现行CIM驻留权重并行使用与采样时序；这是明确的架构估算假设，不是定制SRAM实测。

- 权重装载写入：沿原DMA→SRAM事务收费，不重复加写能量。
- 权重读出：每个实际使用的K64/M128权重块8KiB计一次普通SRAM等效读；16B读事件为12.0293pJ。读出后供该帧GU16或Wd32采样复用，不逐采样重读。
- SRAM面积、全容量泄漏：沿原物理bank账本，仅计一次。不新增整套权重寄存器或并行端口面积。
- 比较器、SNG、AND、计数器：仍由实测FFN整核价格承担，不叠加。
- 不将512个读事件解释为串行512拍。这是能量等效计费，现行并行供数时序保留。

原执行没有CIM权重读出事件，故新账本增加`CIM_weight_presentation_SRAM_proxy`。若后续事务已显式记录这些读，自动扣除已计部分。主线250MHz及未来新跨模型快照采用此政策；100MHz/28nm本轮不变。冻结快照和已封存原件不改。

## 原完整三seed的重计价

三份原始RESULT/BUDGET逐SHA保持；重新执行本版价格函数，验证只有新增读出能量改变。不是新时序回放或新电路仿真。

|项目|原账本|本政策|
|---|---:|---:|
'''
doc+=f"|含head时间|{mean('time_ms'):.6f}ms|{mean('time_ms'):.6f}ms|\n"
doc+=f"|片上能量|{mean('old_onchip_mJ'):.6f}mJ|{mean('new_onchip_mJ'):.6f}mJ|\n"
doc+=f"|含外存总能量，4pJ/bit|{mean('new_system4pJ_mJ')-mean('added_read_mJ'):.6f}mJ|{mean('new_system4pJ_mJ'):.6f}mJ|\n"
doc+=f"|已覆盖面积|{mean('area55_mm2'):.6f}mm²|{mean('area55_mm2'):.6f}mm²|\n\n"
doc+='每token328320帧，共168099840个16B读事件，新增2.022123mJ。写入、静态驻留、随机核内部成本不再重复相加。数据来自225独立三seed，不能与245不同胶合成本的数字表混成配对结果。245后续新价函数已接此接口；健康运行中的冻结任务仍使用提交时旧价，待封存后可按动作重计，不重跑时序。\n\n'
doc+='来源、原件SHA、逐seed结果及检查见同名JSON。全片CTS/NoC/PHY与外存pJ/bit情景仍按原边界；本政策不新增其仿真要求。\n'
write(FOLDER/'CIM_SRAM_POLICY_20261109.md',doc)

readiness=FOLDER/'PRIMARY_READINESS_ZH_20261109.md'
text=readiness.read_text(encoding='utf8')
start=text.index('### P0-3 ');end=text.index('### P1-1 ',start)
replacement='''### P0-3 CIM接口采用普通SRAM价格：已按用户决定闭合估价口径

2026-11-09用户明确：CIM权重并行接口采用默认普通SRAM读写功耗，不再以定制接口未联合表征为待补仿真或主线阻塞。装载写入、面积与泄漏沿原SRAM账本；每块驻留权重计一次普通SRAM等效读并跨采样复用，不重复计写入/驻留，不新增512拍串行读。

本版实现和完整三seed重计价见[CIM权重接口政策](CIM_SRAM_POLICY_20261109.md)。增加约2.022123mJ/token，时间与面积不变，原封存结果保留。属于用户选择的宏级代理，不能称定制SRAM实测。CTS/NoC/PHY等共同平台仍按声明边界，不要求本阶段全片签核。

'''
assert 'ordinary SRAM read' in (FOLDER/'pricing.py').read_text()
write(readiness,text[:start]+replacement+text[end:])
note='''## 2026-11-09 用户决定：CIM权重接口采用普通SRAM功耗

Issue225/PR249；55nm250主线的CIM权重并行接口直接采用普通SRAM读写事件价格，不再列待补仿真。写入/物理容量面积/泄漏沿原账本，新增每8KiB驻留tile一次等效读，16B为12.0293pJ，跨GU16/Wd32采样复用；保持并行供数时序，无逐采样重读、无额外权重DFF。已计读事件可去重。

225原三seed实际价格函数重放通过：328320帧/168099840读，新增2.022123mJ，片上均值27.228731mJ、总4pJ情景200.393226mJ，时间50.418948ms、面积22.086073mm²不变。原件SHA、时序、带宽和核价格逐项不变；不是新时序/RTL/PT，冻结任务不改。正式250MHz/CIM_SRAM_POLICY_20261109.md/json及helper/pricing.py；245新价格函数已接同接口，健康冻结任务旧价封存后另派生重计，不能假称已经刷新原表。

这是用户选择的架构成本假设，不宣称定制CIM联合PPA。100MHz/28nm本轮不改，CTS/PHY/NoC沿原平台边界。发布状态看本次PUBLICATION.json，未发布前只能称本地；看板待维护者同步。
'''
write(HERE/'HANDOFF.md',note+'\n下一步：按同政策对最终245冻结结果做派生重计，不因本政策重新提交长时序。\n')
for root in (ROOT,OTHER):
    status=root/'progress/rayggxia/STATUS.md'
    write(status,note+'\n---\n\n'+status.read_text(encoding='utf8'))
write(OTHER/'work/rayggxia/245/cim_sram_policy_20261109/HANDOFF.md',note)
master=WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
mirror=WS/'PROJECT_MEMORY_ZH.md';old=master.read_bytes();assert old==mirror.read_bytes()
new=(note+'\n---\n\n').encode()+old
assert master.read_bytes()==mirror.read_bytes()==old
master.write_bytes(new);mirror.write_bytes(new)

paths=['architecture_tlm/sram1216_20261106/250MHz/'+n for n in
    ('cim_weight_policy.py','pricing.py','CIM_SRAM_POLICY_20261109.md','CIM_SRAM_POLICY_20261109.json','PRIMARY_READINESS_ZH_20261109.md')]
paths+=['work/rayggxia/225/cim_sram_policy_20261109/HANDOFF.md','work/rayggxia/225/cim_sram_policy_20261109/update.py','progress/rayggxia/STATUS.md']
for name in paths[:5]:
    dest=WS/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/name).read_bytes())
for f in (FOLDER/'pricing.py',FOLDER/'cim_weight_policy.py',OTHER/'architecture_tlm/model_scaling_20261106/current_pricing.py'):
    ast.parse(f.read_text(),filename=str(f))
dump(HERE/'PUBLIC_FILES.json',dict(files=[dict(path=n,sha256=sha(ROOT/n),content=(ROOT/n).read_text(encoding='utf8')) for n in paths]))
other_paths=['architecture_tlm/model_scaling_20261106/current_pricing.py','progress/rayggxia/STATUS.md','work/rayggxia/245/cim_sram_policy_20261109/HANDOFF.md']
dump(HERE/'CROSS_PUBLIC_FILES.json',dict(files=[dict(path=n,sha256=sha(OTHER/n),content=(OTHER/n).read_text(encoding='utf8')) for n in other_paths]))
print(json.dumps(dict(status=summary['status'],mean=summary['mean'],files225=len(paths),files245=len(other_paths))))
