"""Refresh area tables from the existing1216KiB budget; no new simulation."""
from pathlib import Path
import csv,hashlib,io,json,math

WD=Path(__file__).resolve().parents[4]
FOLDER=WD/'architecture_tlm/sram1216_20261106'
def load(p):return json.loads(p.read_bytes())
def save(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())

budget=load(FOLDER/'BUDGET_ESTIMATE.json')['central50ms']
inputs_path=WD/'architecture_tlm/current_handoff_budget_20261106/INPUTS.json'
inputs=load(inputs_path)
areas=budget['areas55_mm2'];total=math.fsum(areas.values())
groups=[];seen=set()
for name,predicate in (
    ('FFN计算、随机前端及跨块累加',lambda k:k.startswith('FFN_')),
    ('共享数字FMA池及末端归约',lambda k:k.startswith('ordinary_')),
    ('Attention计算、筛选、采样及V累加',lambda k:k.startswith('Attention_')),
    ('片上SRAM宏',lambda k:k=='shared_SRAM'),
    ('DMA24KiB入口保持',lambda k:k=='DMA_24KiB_holding'),
    ('格式、向量及数字本地保持代理',lambda k:k in ('format_and_vector_proxy','digital_holding_proxy'))):
    keys=[k for k in areas if predicate(k)]
    assert not seen.intersection(keys);seen.update(keys)
    area=math.fsum(areas[k] for k in keys)
    groups.append(dict(name=name,area55_mm2=area,share_percent=area/total*100,source_keys=keys))
assert seen==set(areas)
assert math.isclose(math.fsum(x['area55_mm2'] for x in groups),total,abs_tol=1e-10)
price=inputs['prices']['SRAM_macro_area55_mm2']
sr=[]
for name,kib,physical in (
    ('八组Attention局部缓冲',512,True),('普通数字权重双缓冲',160,False),
    ('CIM权重驻留槽',256,False),('激活与量化码',128,False),
    ('FFN跨K宽状态',96,False),('归一化参数双缓冲',32,False),
    ('DMA相关SRAM预留',32,False)):
    sr.append(dict(name=name,capacity_KiB=kib,equivalent_4KiB_macros=kib//4,
        area55_mm2=kib/4*price,dedicated_physical_partition=physical))
assert sum(x['capacity_KiB'] for x in sr)==1216
assert sum(x['equivalent_4KiB_macros'] for x in sr)==304
assert math.isclose(math.fsum(x['area55_mm2'] for x in sr),areas['shared_SRAM'],abs_tol=1e-10)
assert budget['Attention_KiB_per_group']==64 and budget['ordinary_weight_slot_KiB']==80
assert budget['activation_KiB']==128 and budget['SRAM_banks']==304
assert areas['FFN_random_service_proxy']==0 and areas['FFN_common_core']>0
comparisons=[]
for name,kib,area in [('旧2.5MiB预算',2560,inputs['reference']['covered_area55_mm2']),
    ('上一版1952KiB预算',1952,57.573748218226825),('当前保留1216KiB',1216,total)]:
    comparisons.append(dict(name=name,SRAM_KiB=kib,covered_area55_mm2=area))
sources=[FOLDER/'BUDGET_ESTIMATE.json',FOLDER/'RESULTS.json',inputs_path]
result=dict(date='2026-11-06',owner='rayggxia',issue=225,pr=248,
    selected_configuration='compact1216',selection='user_selected_keep1216KiB_local_reference',
    scope='covered area budget from existing prices; not new RTL/PPA or complete die',
    SRAM_KiB=1216,SRAM_MiB=1216/1024,physical_4KiB_banks=304,
    covered_area55_mm2=total,groups=groups,detail_areas55_mm2=areas,SRAM_attribution=sr,
    SRAM_attribution_note='front176 physical banks are shared/striped; front per-use areas are capacity accounting, not extra dedicated banks',
    area_scale_note='existing project55-equivalent values already include raw area x0.81 once; do not scale again',
    comparisons=comparisons,not_included=['new compact address decoder/interconnect PPA','full NoC/CTS/PHY/IO/pads/floorplan and routing overhead'],
    FFN_random_area_note='SNG/PRNG/comparison included in C20 core price; zero extra proxy does not mean zero random hardware',
    long_context='retain1216KiB for currentB1/2K/K128/S64; FFN and ordinary tiles need not grow with context; largerK or whole coarse-score retention may need more Attention SRAM or a different streaming/cache schedule',
    sources=[dict(path=p.relative_to(WD).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sources],
    no_new_jobs=True,no_new_RTL_PPA=True,no_new_PPL=True)
save(FOLDER/'AREA_BREAKDOWN.json',result)
output=io.StringIO(newline='');writer=csv.writer(output,lineterminator='\n')
writer.writerow(['module','area55_mm2','share_percent'])
writer.writerows((x['name'],format(x['area55_mm2'],'.9f'),format(x['share_percent'],'.6f')) for x in groups)
writer.writerow(['total',format(total,'.9f'),'100.000000'])
(FOLDER/'AREA_BREAKDOWN.csv').write_bytes(output.getvalue().encode('utf-8'))
lines=['# 保留1216KiB配置后的各模块面积', '',
    '2026-11-06，Issue225/PR248。用户决定先保留1216KiB（1.1875MiB），本表将其作为当前本地面积参考；不静默改写旧执行快照或泛用CLI默认。当前条件为Qwen3-4B、B1/2K、K128/赢家S64、640路普通池、12个C20/T64公共FFN核、96KiB GU状态。', '',
    f'**已覆盖片上面积合计约{total:.3f}mm²。** 除SRAM布局外沿用上一轮已有单价，没有重新综合逻辑。表中面积已包含本项目raw×0.81一次，不再缩放。', '',
    '## 1. 总表', '', '|部分|55等效面积mm²|占比|','|---|---:|---:|']
for x in groups:lines.append(f"|{x['name']}|{x['area55_mm2']:.3f}|{x['share_percent']:.2f}%|")
lines += [f'|**合计**|**{total:.3f}**|**100%**|','',
    '共享数字池包括QKV/O/lm_head计算资源，只计一份；Attention的独立512路QK仍保留。FFN随机前端/SNG/比较器已包含在C20核价内，不能再加第二份。', '',
    '## 2. 计算与控制详细分项', '', '|预算项|面积mm²|','|---|---:|']
for k,a in areas.items():lines.append(f'|{k}|{a:.6f}|')
lines += ['', 'FFN_random_service_proxy=0表示不额外重复收费，不代表随机源硬件免费。普通FMA池为40个FMA16切片，仍有128个FP32末端归约器；缩减实例不等于MAC总动作量等比例减少。', '',
    '## 3. SRAM内部容量与面积归属', '', '|用途|KiB|等价4KiB宏|面积mm²|','|---|---:|---:|---:|']
for x in sr:lines.append(f"|{x['name']}|{x['capacity_KiB']}|{x['equivalent_4KiB_macros']}|{x['area55_mm2']:.6f}|")
lines += [f"|**SRAM合计**|**1216**|**304**|**{areas['shared_SRAM']:.6f}**|",'',
    '这张SRAM表是上面8.181625mm²的内部拆分，不加到总表第二次。八Attention组各16个独立bank；其余区域在前176bank中交织共享。前端按容量摊分的等价宏数不表示各模块另外独占这些物理宏。32KiB DMA相关SRAM预留与24KiB入口保持是两项现有预算边界，本次仍保留，不擅自合并或免费删除。', '',
    '## 4. 版本比较', '', '|版本|SRAM KiB|覆盖面积mm²|','|---|---:|---:|']
for x in comparisons:lines.append(f"|{x['name']}|{x['SRAM_KiB']}|{x['covered_area55_mm2']:.3f}|")
lines += ['',f"相对1952KiB版本，SRAM少{(1-1216/1952)*100:.2f}%，覆盖总面积少{(1-total/57.573748218226825)*100:.2f}%。这是面积预算，不将比例套到能量或时间上。", '',
    '## 5. 长上下文是否需要增容', '',
    '不是上下文变长就让全部SRAM按比例增加。FFN工作区、普通权重tile及norm槽通常可保持；完整KV主体仍在片外。主要变化在Attention候选/粗分数/局部V缓存。', '',
    '例如，若K由128增加到256且继续整份缓存候选V，单组V数据由128×128×2B=32KiB变成64KiB；当前每组64KiB还要容纳分数和其他工作区，因此不能直接套用当前布局。可以扩大Attention区域，也可以分块或使用有限带tag缓存，后者需评估重读和调度代价。若K保持128并流式处理更长上下文，容量有机会保持，质量与时序需要另测。', '',
    '当前先保留1216KiB，不继续试992KiB等候选，也不提前把长上下文增容计入2K主表。', '',
    '## 6. 证据和边界', '',
    '本轮只是更新面积分类与来源绑定，未重跑模型或电路。已有8项机制检查和三配置一层合成时序回放仍按原范围引用，不升级为原生整token结果。按用户决定，不重试故障EDA服务器。', '',
    '新紧凑译码/互连增量、完整NoC/CTS、PHY/IO/pad、布局布线等尚未补齐，因此52.62mm²是已覆盖模块预算，不是最终die面积。外部DRAM芯片不计入片上面积；没有从GPU整片面积反推算子面积。', '',
    '机器可读表为AREA_BREAKDOWN.json/CSV；来源SHA在JSON，生成器为work/rayggxia/225/sram1216/build_area.py。旧SOURCE_MANIFEST与原始结果不改，新增表由AREA_VALIDATION.json单独登记。', '']
(FOLDER/'AREA_BREAKDOWN_ZH.md').write_bytes('\n'.join(lines).encode('utf-8'))
save(Path(__file__).with_name('AREA_VALIDATION.json'),dict(status='PASS_area_accounting',
    no_new_simulation=True,configuration='user_keep1216KiB',area_components=len(areas),groups=len(groups),
    checks=['all area keys assigned once','group sum equals covered total','SRAM capacities sum1216KiB',
    'SRAM equivalent macros sum304','SRAM subareas equal shared_SRAM once','selected dimensions64/80/128/304 match',
    'FFN random zero-extra proxy not zero hardware'],
    sources=result['sources'],outputs={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (FOLDER/'AREA_BREAKDOWN.json',FOLDER/'AREA_BREAKDOWN.csv',FOLDER/'AREA_BREAKDOWN_ZH.md')}))
print(json.dumps(dict(covered_area55_mm2=total,groups=groups,SRAM_KiB=1216,SRAM_area55_mm2=areas['shared_SRAM']),ensure_ascii=True))
