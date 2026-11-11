"""Adopt the user-requested mixed organization after sealed finite-port tests."""
from pathlib import Path
import json,hashlib,ast,zipfile

H=Path(__file__).resolve().parent;ROOT=H.parents[3];WS=ROOT.parents[1];D=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump=lambda p,x:p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
result=json.loads((D/'SRAM_MIXED34_VALIDATION_20261109.json').read_bytes())
assert result['status']=='PASS_FINITE_PORT_SHARED_MIXED_MACRO_PAIRS'
rows=[x for x in result['rows'] if x['mixed']];default=json.loads((D/'DEFAULT_SRAM832_20261109.json').read_bytes())
original_default=json.loads(json.dumps(default))
for row in rows:
    mhz=row['clock_MHz'];f=D/f'{mhz}MHz';ref=f/'WHOLE_CONFIG_832_ALL4K_REFERENCE.json'
    current=f/'WHOLE_CONFIG.json'
    if not ref.exists():
        assert json.loads(current.read_bytes())['SRAM']['bank_count']==208
        ref.write_bytes(current.read_bytes())
    tested=H/'revision2'/Path(result['sources'][f'p{mhz}_mixed']['folder']).name/'RESULT.json'
    r=json.loads(tested.read_bytes());cfg=r['macro_config']
    # Metadata correction only: S2 access energy is estimated, not new PT.
    cfg['SRAM'].update(macro_characterized=False,
        policy='real S0/S2 macro geometry;shared106front/72Attention1RW;S0PT+S2CLKdelta energy estimate',
        timing_scope='S0/S2 TT library single-macro period;1cycle return/II1;fabric unplaced',
        macro='S0_4KiB_and_S2_8KiB;see macro_models')
    dump(current,cfg)
    check=json.loads(current.read_bytes())
    tested_cfg=json.loads(tested.read_bytes())['macro_config']
    for k in ('macro_characterized','policy','timing_scope','macro'):
        check['SRAM'].pop(k,None);tested_cfg['SRAM'].pop(k,None)
    assert check==tested_cfg
    old=next(x for x in default['rows'] if x['clock_MHz']==mhz)
    old.update(physical_banks=178,front_banks=106,attention_banks=72,
        physical_macro_counts={'S2_8KiB':30,'S0_4KiB':148},SRAM_macro_area_mm2=row['SRAM_macro_area_mm2'],
        conditional_subsystem_area_mm2=row['conditional_subsystem_area_mm2'],
        default_config_sha256=sha(current),tested_config_sha256=r['macro_config_sha256'],
        metadata_only_changes_after_replay=['macro_characterized','policy','timing_scope','macro'],
        paired_partial_time_ms=row['time_ms'],paired_partial_time_change_pct=row['time_change_pct'],
        paired_reference='same832KiB_all4KiB208macros',full_default36_time_ms=None,
        full_default36_energy_mJ=None)
default.update(status='USER_ACCEPTED_832KiB_MIXED30x8_148x4_SHARED106_DEFAULT',
    mapping=result['mapping'],CIM_capacity_accounting=result['CIM_capacity_accounting'],
    isolated_CIM34_timing_tested=False,SRAM_S2_energy_status=result['S2_power'],
    validation='SRAM_MIXED34_VALIDATION_20261109.json',
    no_new_timing_replay=False,new_PPA=False,
    tests=['four_completed_seals_and_input_SHA','178_real_ports_and_53248_unique_words',
           'work_external_bytes_and_addresses_conserved','bank_action_price_audit',
           'default_runtime_fields_match_tested_mixed_configs;four_metadata_fields_corrected'])
dump(D/'DEFAULT_SRAM832_20261109.json',default)

doc='''# 832KiB混合宏：拆分两个8KiB宏

2026-11-09，Issue225 / PR249。按用户选择，将256KiB容量份额采用30×8KiB＋4×4KiB；相对32×8KiB，拆分两个宏后净增两个端口。28nm两频默认采用这一混合组织，55nm保持。

## 容量、端口和面积

全体SRAM为30×8KiB＋148×4KiB＝832KiB，共178个真实128bit/1RW宏；原布局是208个4KiB宏。Attention保持72个4KiB宏。前端普通权重、CIM、激活、Norm、部分和继续共享544KiB，实际106个端口，已删除30个端口，没有保留虚构带宽。

**256KiB是CIM容量记账，不能等同于34个独占CIM端口。** 本轮保留既有共享条带组织；没有另做CIM专属34端口布局。独占34端口的理想写带宽为250MHz136GB/s、500MHz272GB/s，仅是端口乘法，不构成实际吞吐验证。

物理地址映射：前424KiB在106个宏的低256行条带化；后120KiB在30个8KiB宏的高256行条带化。上下半部共享同一个真实1RW端口。53248个16B物理位置全部枚举通过容量、边界和无别名检查；八Attention组各9个宏。

|指标|原832KiB|混合宏832KiB|
|---|---:|---:|
|全体真实宏数/端口数|208|178|
|共享前端端口|136|106|
|Attention端口|72|72|
|SRAM宏面积|2.471065mm²|2.278958mm²|
|250MHz条件子系统面积|6.758447mm²|6.566340mm²|
|500MHz条件子系统面积|6.784987mm²|6.592880mm²|

SRAM面积减少0.192107mm²（7.77%），整机条件预算约减少2.84%/2.83%。28nm面积乘1，无统一15%预留；地址译码/互连尚未新增布局表征，不把宏面积节省解释为签核后的整片面积。

## 有限bank回放

保持Qwen3-4B/B1/2K/K128/S64、GU16/Wd32、核数、数字计算资源和外存不变。250MHz是三核两层＋384词条head，500MHz是两核一层＋384词条head；固定参考地址seed17，外存为136.4606GB/s/30ns解析后端。读写要经过真实bank竞争、端口和DMA回压。

|频率|原832小流程|混合宏小流程|时间变化|SRAM能量变化|
|---|---:|---:|---:|---:|
'''
for x in rows:
    base=next(z for z in result['rows'] if z['clock_MHz']==x['clock_MHz'] and not z['mixed'])
    doc+=f"|{x['clock_MHz']}MHz|{base['time_ms']:.6f}ms|{x['time_ms']:.6f}ms|{x['time_change_pct']:+.4f}%|{x['SRAM_energy_change_pct']:+.3f}%|\n"
doc+='''
四个完成case的SEAL、源码/配置/绑定SHA、队列排空、相同核帧/尺度/编码/算术/采样工作量、外存各类字节与地址摘要通过。SRAM访问量和冲突按实际结果保留，不能强制它们与旧映射相同。上述变化在本次局部回放小于1%，未观察到明显的新整体瓶颈；不是完整36层/完整词表/其它上下文或原生LPDDR结果。

## 能量来源与保留限制

S0 4KiB沿用真实TT0.9V25°C的PT增量访问价；S2 8KiB面积/时序/漏电来自同工艺库，读写动态价暂用S0 PT＋同PVT CLK internal-energy差值：读+0.40995pJ、写+1.17135pJ。S2没有新跑PT，不因面积减小就按比例削减能耗。实际访问按各物理宏分别计价，停钟驻留只计一次；CIM每次装载权重字另计一次等效读，采样期间不逐拍重读。

首次混合回放在能耗一致性断言失败，未封存为完成。原因是逐事件binary64求和与按整数次数乘单价的舍入差；修订后保留整数次数核对，并按2×事件数×机器epsilon检查误差界，实际误差和原失败SHA保留在JSON。没有更改该修复前后的调度逻辑，已封存的250MHz参考复用。

新默认与冻结混合配置的执行字段相同；仅纠正macro_characterized、policy、timing_scope、macro四个描述字段，明确S2是估价。旧832全4KiB和960参考另存WHOLE_CONFIG_832_ALL4K_REFERENCE/WHOLE_CONFIG_960_REFERENCE。冻结PLAN命令是复现入口，换新输出目录即可；run_pairs是基于旧默认的一次性冻结工具，不对已切换默认重复取样。

完整token的当前时间/能耗仍未新跑；旧960外推45.901/40.991ms不能改标签当新混合宏结果。无新训练/PPL/RTL/PT，无芯片签核结论。
'''
(D/'SRAM_MIXED34_VALIDATION_20261109_ZH.md').write_bytes(doc.encode())
default_doc='''# 28nm默认832KiB：混合宏更新

2026-11-09，Issue225 / PR249。用户决定拆分两个8KiB宏，250/500MHz默认均已更新为**30×8KiB＋148×4KiB＝832KiB，178个真实1RW宏**。CIM容量记账30×8KiB＋4×4KiB＝256KiB；前端仍共享106端口、Attention保持72端口，并非CIM独占34端口。

|分区|KiB|
|---|---:|
|普通投影权重双缓冲|64|
|CIM权重32个驻留槽|256|
|激活/概率码/元数据|96|
|Norm双缓冲|32|
|八组Attention|288|
|FFN跨K状态|96|
|总计|832|

SRAM宏面积2.278958mm²，减少0.192107mm²。无15%统一预留的250/500MHz条件子系统预算6.566340/6.592880mm²。S0用真实PT，S2动态价采用同库CLK差值估计，未冒称新PT。

有限bank配对时间与能量见[混合宏回放](SRAM_MIXED34_VALIDATION_20261109_ZH.md)，在当前局部流程内未出现明显新增瓶颈；完整token尚未重跑。旧208宏参考为同目录WHOLE_CONFIG_832_ALL4K_REFERENCE.json，旧960也保留。两频默认配置仅改宏组织与相应价格，核数、采样、外存和55nm均不变。
'''
(D/'DEFAULT_SRAM832_20261109_ZH.md').write_bytes(default_doc.encode())
for name in ('README_ZH.md','WHOLE_MODEL_ZH.md'):
    p=D/name;t=p.read_text(encoding='utf8')
    old=t.splitlines()[0]
    assert '默认832KiB/208bank' in old
    t=t.replace(old,'> **2026-11-09更新：28nm250/500MHz默认832KiB/178个混合宏。** 前端106共享端口＋Attention72端口；条件面积预算6.566340/6.592880mm²。见[混合宏验证](SRAM_MIXED34_VALIDATION_20261109_ZH.md)。55nm保持。',1)
    if name=='WHOLE_MODEL_ZH.md':t=t.replace('208bank/832KiB','178混合宏/832KiB')
    p.write_bytes(t.encode())
# Preserve compact reproducible timing evidence outside the disposable checkout.
archive=WS/'project_archives/mixed34_issue225_20261109';archive.mkdir(exist_ok=True)
z=archive/'finite_pairs_and_failed_audit.zip'
assert not z.exists(),'never overwrite an existing evidence archive'
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as package:
    for rel in ('PLAN.json','p250_mixed.log','p250_mixed_RETURN.json'):
        package.write(H/rel,rel)
    for rel in ('RESULT.json','BUDGET.json','VALIDATION.json','SEAL.json'):
        package.write(H/'p250_base'/rel,'p250_base/'+rel)
    for p in (H/'execution_e1a741184720').rglob('*'):
        if p.is_file():package.write(p,p.relative_to(H))
    for p in (H/'revision2').rglob('*'):
        if p.is_file():package.write(p,p.relative_to(H))
dump(H/'ARCHIVE_INDEX.json',dict(path=str(z),sha256=sha(z),bytes=z.stat().st_size,
    scope='completed paired results,configs,frozen sources,plans,first failed energy audit;not vendor library'))
for n in ('candidate_sram.py','mixed_sram.py','whole_model.py','sram_characterization.py','whole_pricing.py','run_whole.py'):
    ast.parse((D/n).read_text(),filename=n)
print(json.dumps(dict(status='ADOPTED_MIXED_DEFAULT_AFTER_VERIFIED_PAIRS',area_mm2=[x['conditional_subsystem_area_mm2'] for x in rows],archive=str(z),archive_sha256=sha(z)),ensure_ascii=False))
