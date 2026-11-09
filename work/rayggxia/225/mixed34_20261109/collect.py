"""Validate completed finite-port mixed-macro pairs; no full-token extrapolation."""
from pathlib import Path
from collections import Counter
import json,hashlib,math

H=Path(__file__).resolve().parent;ROOT=H.parents[3];DEST=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump=lambda p,x:p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
run=H/'revision2';plan=json.loads((run/'PLAN.json').read_bytes());rows=[];sources={}
for mhz in (250,500):
    pair=[]
    for mixed in (False,True):
        name=f'p{mhz}_'+('mixed' if mixed else 'base');folder=run/name
        reuse=run/(name+'_REUSED.json')
        if reuse.exists():folder=Path(json.loads(reuse.read_bytes())['path'])
        seal=json.loads((folder/'SEAL.json').read_bytes());assert seal['status']=='completed'
        for n,v in seal['files_sha256'].items():assert sha(folder/n)==v
        ret=folder.parent/(name+'_RETURN.json');assert json.loads(ret.read_bytes())['exit_code']==0
        r=json.loads((folder/'RESULT.json').read_bytes());b=json.loads((folder/'BUDGET.json').read_bytes())
        assert r['status']=='completed' and r['head_probe_rows']==384 and r['seed']==17
        s=r['SRAM'];assert s['capacity_bytes']==s['allocated_bytes']==832*1024
        assert s['physical_banks']==(178 if mixed else 208)
        assert not r['memory']['final_pending'] and not r['memory']['final_response_occupied']
        if mixed:
            c=r['SRAM_layout_contract'];assert c['physical_words_unique']==53248
            assert Counter(s['bank_model_ids'])=={'S0':148,'S2':30}
            assert c['front_banks']==106 and c['attention_banks']==72
            assert c['CIM_not_exclusive34_ports'] and not b['SRAM_calibration']['macro_characterized']
            assert abs(b['SRAM_calibration']['event_vs_count_relative_error'])<=b['SRAM_calibration']['binary64_accumulation_error_bound']
        phases=Counter()
        for z in r['phases']:phases[z['stage']]+=z['duration_ns']/1000
        info=dict(clock_MHz=mhz,mixed=mixed,capacity_KiB=832,physical_macros=s['physical_banks'],
            front_ports=106 if mixed else 136,attention_ports=72,layers=r['layers'],head_probe_rows=384,
            time_ms=r['time_ms'],phases_us=dict(phases),SRAM_macro_area_mm2=b['SRAM_calibration']['area_mm2'],
            SRAM_energy_mJ=b['SRAM_calibration']['total_including_CIM_mJ'],
            covered_area_mm2=b['covered_component_area_mm2'],covered_energy_mJ=b['covered_component_energy_mJ'],
            reads=s['counts']['read_words'],writes=s['counts']['write_words'],
            bank_head_conflicts=s['counts'].get('bank_head_conflicts',0),
            energy_price_status=r['macro_config']['SRAM']['price_status'])
        pair.append((r,b,info))
        sources[name]=dict(folder=str(folder),files_sha256={n:sha(folder/n) for n in ('RESULT.json','BUDGET.json','VALIDATION.json','SEAL.json')},
            code_sha256=r['code_sha256'],config_sha256=r['macro_config_sha256'],bindings_sha256=r['bindings_sha256'],
            host_manifest_sha256=r['snapshot_manifest_sha256'],return_receipt_sha256=sha(ret))
    old,ob,oi=pair[0];new,nb,ni=pair[1]
    assert old['kernel_active']==new['kernel_active'] and old['process28_counts']==new['process28_counts']
    for k in ('SC_equivalent_MAC','digital_BF16_MAC','attention_QK_MAC','PV_ADD','samples','unique_V',
              'common_R8_words','GU_logical_R8_ports','NL_logical_R8_ports','common_state32_vectors'):
        assert old['actions'].get(k)==new['actions'].get(k),(mhz,k)
    assert old['memory']['by_kind'].keys()==new['memory']['by_kind'].keys()
    for k,v in old['memory']['by_kind'].items():
        for field,value in v.items():
            if field=='issued_bytes' or 'address_sum' in field or 'address_xor' in field:
                assert new['memory']['by_kind'][k][field]==value,(mhz,k,field)
    saved=oi['SRAM_macro_area_mm2']-ni['SRAM_macro_area_mm2']
    assert math.isclose(saved,.1921071195,abs_tol=1e-12)
    ni.update(time_change_pct=100*(ni['time_ms']/oi['time_ms']-1),
        SRAM_area_saved_mm2=saved,SRAM_area_change_pct=-100*saved/oi['SRAM_macro_area_mm2'],
        SRAM_energy_change_pct=100*(ni['SRAM_energy_mJ']/oi['SRAM_energy_mJ']-1),
        covered_energy_change_pct=100*(ni['covered_energy_mJ']/oi['covered_energy_mJ']-1),
        conditional_subsystem_area_mm2=(6.758446623979166 if mhz==250 else 6.784987237074603)-saved,
        binary64_relative_energy_error=nb['SRAM_calibration']['event_vs_count_relative_error'],
        work_and_external_bytes_conserved=True)
    assert ni['time_ms']<oi['time_ms']*1.01,('review slowdown',mhz,ni['time_change_pct'])
    rows.extend([oi,ni])
result=dict(status='PASS_FINITE_PORT_SHARED_MIXED_MACRO_PAIRS',issue=225,PR=249,owner='rayggxia',
    model='Qwen3-4B',context=2048,candidates=128,samples=64,GU_samples=16,Wd_samples=32,seed=17,
    backend='analytic136.4606GBps_30ns',rows=rows,sources=sources,
    physical_total='30x8KiB+148x4KiB=832KiB;178real1RW128bitports',
    CIM_capacity_accounting='30x8KiB+4x4KiB=256KiB;not isolated34ports',
    mapping='front544KiB uses106 shared physical macros;Attention288KiB retains72 macros',
    ideal_isolated_CIM34_GBs={'250':136,'500':272},isolated_CIM34_timing_tested=False,
    initial_failure=dict(folder=str(H),case='p250_mixed',status='UNSEALED_FAILED_ENERGY_ROUNDOFF_AUDIT',
        log_sha256=sha(H/'p250_mixed.log'),receipt_sha256=sha(H/'p250_mixed_RETURN.json'),
        resolution='positive-price binary64 accumulator vs count multiplication;N*epsilon error bound and exact counts audit;no scheduling change'),
    scope='250two_layers_or500one_layer_plus384row_head;not full36/full_vocab/nativeLPDDR/PPL/physicalPPA',
    S2_power='S0_PT_increment+samePVT_CLK_library_delta_estimate;no S2 PT',default_changed=False,
    new_circuit_PPA=False,full_token_performance_not_claimed=True)
dump(DEST/'SRAM_MIXED34_VALIDATION_20261109.json',result)
print(json.dumps(dict(status=result['status'],mixed_rows=[x for x in rows if x['mixed']]),ensure_ascii=False))
