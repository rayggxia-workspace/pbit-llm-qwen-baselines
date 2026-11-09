"""Read only completed seals, compare unchanged work and actual smaller banks."""
from pathlib import Path
from collections import Counter
import hashlib,json,math

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
OUT=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=[];sources={}
for mhz in (250,500):
    pair=[]
    for cap in (960,832):
        folder=HERE/f'p{mhz}_{cap}'
        seal=json.loads((folder/'SEAL.json').read_bytes());assert seal['status']=='completed'
        for n,v in seal['files_sha256'].items():assert sha(folder/n)==v
        receipt=json.loads((HERE/(folder.name+'_RETURN.json')).read_bytes());assert receipt['exit_code']==0
        r=json.loads((folder/'RESULT.json').read_bytes());b=json.loads((folder/'BUDGET.json').read_bytes())
        assert r['status']=='completed' and r['head_probe_rows']==384
        assert r['SRAM']['capacity_bytes']==cap*1024 and r['SRAM']['physical_banks']==cap//4
        assert r['SRAM']['allocated_bytes']==cap*1024 and r['memory']['final_pending']==0
        assert r['memory']['final_response_occupied']==0
        assert r['SRAM_layout_contract']['capacity_KiB']==cap
        assert b['SRAM_calibration']['macro_characterized']
        sources[folder.name]=dict(folder=str(folder),files_sha256={n:sha(folder/n) for n in ('RESULT.json','BUDGET.json','VALIDATION.json','SEAL.json')},
            code_sha256=r['code_sha256'],config_sha256=r['macro_config_sha256'],bindings_sha256=r['bindings_sha256'],
            host_manifest_sha256=r['snapshot_manifest_sha256'])
        phases=Counter()
        for x in r['phases']:phases[x['stage']]+=x['duration_ns']/1000
        pair.append((r,b,dict(clock_MHz=mhz,capacity_KiB=cap,banks=cap//4,layers=r['layers'],
            head_probe_rows=384,time_ms=r['time_ms'],phases_us=dict(phases),
            SRAM_area_mm2=b['SRAM_calibration']['area_mm2'],
            SRAM_energy_mJ=b['SRAM_calibration']['total_including_CIM_mJ'],
            covered_components_area_mm2=b['covered_component_area_mm2'],
            covered_components_energy_mJ=b['covered_component_energy_mJ'],
            SRAM_read_words=r['SRAM']['counts']['read_words'],SRAM_write_words=r['SRAM']['counts']['write_words'],
            bank_head_conflicts=r['SRAM']['counts'].get('bank_head_conflicts',0))))
    base,bb,br=pair[0];small,sb,sr=pair[1]
    assert base['kernel_active']==small['kernel_active']
    assert base['process28_counts']==small['process28_counts']
    arithmetic=('SC_equivalent_MAC','digital_BF16_MAC','attention_QK_MAC','PV_ADD','samples',
                'unique_V','common_R8_words','GU_logical_R8_ports','NL_logical_R8_ports','common_state32_vectors')
    for k in arithmetic:assert base['actions'].get(k)==small['actions'].get(k),(mhz,k)
    assert base['memory']['by_kind'].keys()==small['memory']['by_kind'].keys()
    for k,v in base['memory']['by_kind'].items():
        for field,value in v.items():
            if field=='issued_bytes' or 'address_sum' in field or 'address_xor' in field:
                assert small['memory']['by_kind'][k][field]==value,(mhz,k,field)
    sr.update(time_change_pct=(sr['time_ms']/br['time_ms']-1)*100,
        SRAM_area_saved_mm2=br['SRAM_area_mm2']-sr['SRAM_area_mm2'],
        SRAM_energy_change_pct=(sr['SRAM_energy_mJ']/br['SRAM_energy_mJ']-1)*100,
        checks='PASS_BOUNDS_DRAINED_MATCHED_WORK_AND_EXTERNAL_BYTES',
        performance='within1percent' if sr['time_ms']<=br['time_ms']*1.01 else 'measured_slowdown_over1percent')
    assert math.isclose(sr['SRAM_area_saved_mm2'],32*.01188012105,abs_tol=1e-12)
    rows.extend([br,sr])
summary=dict(status='FOUR_COMPLETED_LOCAL_PAIRED_REPLAYS_VERIFIED',owner='rayggxia',issue=225,PR=249,
    model='Qwen3-4B',context=2048,candidates=128,samples=64,GU_samples=16,Wd_samples=32,seed=17,
    backend='analytic136.4606GBps_30ns',PVT='SRAM28 TT0.9V25C',rows=rows,sources=sources,
    scope='250two_layers_and500one_layer_plus384row_head;not full36/full_vocab/nativeLPDDR/PPL/physicalchip',
    default_changed=False,new_circuit_PPA=False,full_token_speedup_not_claimed=True)
(OUT/'SRAM832_VALIDATION_20261109.json').write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode())
doc='''# 832KiB SRAM：两频有限bank配对验证

2026-11-09，Issue225 / PR249。宿主TLM可独立完成这一轮验证，用户不需要先找模块对话批准。

固定Qwen3-4B/B1/2K/K128/S64/GU16/Wd32、同参考seed17、同真实SRAM事件价、同外存136.4606GB/s与30ns解析模型。250MHz采用3核/2层，500MHz采用2核/1层；均附384词条head探针检查尾块和输出。每对同代码，仅容量/映射改变。

832KiB候选：激活128→96KiB；八组Attention各48→36KiB，输出47→34KiB；32KiB K/V缓存和2KiB分数保持。真实物理bank240→208，前端144→136、Attention96→72；不保留被删除的端口，也未增加概率寄存器。

|版本|容量|本次小流程时间|相对同频960KiB|SRAM宏面积|
|---|---:|---:|---:|---:|
'''
for x in rows:
    delta='参考' if x['capacity_KiB']==960 else f"{x['time_change_pct']:+.4f}%"
    doc+=f"|{x['clock_MHz']}MHz|{x['capacity_KiB']}KiB|{x['time_ms']:.6f}ms|{delta}|{x['SRAM_area_mm2']:.6f}mm²|\n"
doc+='''
四份SEAL/原件SHA、源码/配置SHA、完整实际层流程、128尾词条块、所有区域bounds及队列排空检查通过。核帧数、转换/尺度操作、采样、MAC、PV加法、V唯一读取与外存各类字节/地址摘要配对核对。物理SRAM读写量和冲突可随调度改变，已在JSON逐项保留。

这确认832KiB在当前两频小流程内具备容量和执行可行性，不能把小流程时间直接称完整token时间。完整36层/151936词表、原生LPDDR、其他模型/上下文及最终物理互连未在本轮验证。默认仍960KiB，832作为有执行证据的候选；是否改变默认由后续整机评估口径决定。

按相同4KiB宏，SRAM面积少0.380164mm²。仅容量计价，原无15%预留的28nm250/500条件整机面积可由7.138610/7.165151降至6.758447/6.784987mm²；这是候选预算，未把小流程的变化直接放大为全token结论。已覆盖组件能量小计只用于局部对账，不冒称整机功耗。

后续分工见`architecture_tlm/module_handoff/SRAM_REDUCTION_COORDINATION_ZH_20261109.md`：当前布局由宿主负责；进一步CIM槽减半时向FFN确认接口/存储归属，扩展其他Attention模式时确认最大活跃数据；仍用S0宏不需新增SRAM PT。
'''
(OUT/'SRAM832_VALIDATION_20261109_ZH.md').write_bytes(doc.encode())
print(json.dumps(dict(status=summary['status'],candidate_rows=[x for x in rows if x['capacity_KiB']==832]),ensure_ascii=False))
