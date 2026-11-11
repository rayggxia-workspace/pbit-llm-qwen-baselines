"""Consume the completed 28nm/250MHz handoffs without touching other clocks."""
from pathlib import Path
import argparse,copy,hashlib,json

SOURCES={
 'remap':'architecture_tlm/module_handoff/ffn28_nomargin_20261109/profile.json',
 'digital':'architecture_tlm/module_handoff/ffn28_comparison250_20261109/profile.json',
 'attention':'architecture_tlm/module_handoff/attention28_250_zero_20261109/PROFILE.json',
 'selection':'architecture_tlm/module_handoff/attention28_margin_20261109/TLM_SELECTION.json',
 'area_anchor':'architecture_tlm/module_handoff/attention_tlm28_250_500_20261108/PPA_SUMMARY.json',
}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())

def refreshed(workspace,binding,config):
    b=copy.deepcopy(binding);c=copy.deepcopy(config);raw={k:(workspace/p).read_bytes() for k,p in SOURCES.items()}
    d={k:json.loads(v) for k,v in raw.items()};f=d['remap'];dig=d['digital'];att=d['attention'];sel=d['selection']
    assert b['clock_MHz']==c['clock_MHz']==250 and b['process']=='TSMC28HPC+'
    assert f['status']=='ALL3_QUALIFIED' and f['PPA_collected']==3 and f['PT_windows']==38
    assert dig['main_component_parity_ready'] and dig['PPA_collected']==6 and dig['new_PT_windows']==72
    assert att['required_module_completion']['current_batch_complete']
    assert sha(workspace/SOURCES['attention'])==sel['baseline_profile_sha256']
    core=f['accepted_components']['ffn_250'];bf=f['accepted_components']['bf16_250']
    for card in f['accepted_components'].values():
        assert card['clock_MHz']==250 and card['area_multiplier']==1
        assert all(v>=0 for v in card['static_PT_slacks_ns'].values())
    b['FFN_core'].update(area_mm2=core['area_mm2'],waiting_power_W=core['modes']['idle_source_stopped']['mean_whole_module_mW']/1000,
        slacks_ns=core['static_PT_slacks_ns'],setup_uncertainty_ns=0,hold_uncertainty_ns=0,
        price_origin='same RTL/activity zero-margin DC+gate+PT;38-window completed paired batch',
        mapped_sha256=core['mapped_sha256'],power_archive=core['archive'])
    for mode,key in [('GU','GU_active'),('Wd','Wd_active')]:
        m=b['FFN_core']['modes'][mode];assert m['frame_cycles']==(18 if mode=='GU' else 34)
        m.update(mean_core_power_mW=core['modes'][key]['mean_whole_module_mW'],
            gross_pJ_per_DOT64=core['modes'][key]['gross_pJ_per_unit'],
            gross_pJ_per_frame=128*core['modes'][key]['gross_pJ_per_unit'])
    # The paired BF16 experiment retains the same4096 FMA/1052ns window.
    b['shared_FMA'].update(status='ZERO_MARGIN_PAIRED_FMA16_C4_BOUND',
        area_mm2=bf['area_mm2'],gross_pJ_per_FMA=bf['modes']['continuous']['gross_pJ_per_unit']/64,
        idle_W=bf['modes']['idle_hold']['mean_whole_module_mW']/1000,
        latency_cycles=4,input_II_cycles=1,contexts=4,measurement_ns_per_FMA=1052/4096,
        timing_basis='input hold + two arithmetic pipe regs + commit/reissue;same pairedRTL,C4,II1',
        mapped_sha256=bf['mapped_sha256'],power_archive=bf['archive'],slacks_ns=bf['static_PT_slacks_ns'])
    b['digital_reference_cards']=dict(dig['accepted_new_components'])
    b['digital_reference_cards'].update(f['accepted_components'])
    # Available alternatives do not instantiate another physical FFN or FMA pool.
    b['digital_reference_cards_selected_by_SC']=False
    b['accepted_digital_components']['integer_gu_250']=f['accepted_components']['integer_gu_250']
    for name,card in att['cards'].items():
        if card.get('qualified_module_price') or card.get('qualified_for_TLM_hold_deferred'):
            assert card['slacks_ns']['setup']>=0 and card['slacks_ns']['gate_setup']>=0
            b['attention_cards'][name]=copy.deepcopy(card)
    for name,card in sel['recommended_primary'].items():b['attention_cards'][name]=copy.deepcopy(card)
    b['attention_selection']=dict(primary=['gap_sampler_250','gap_softmax_r8_gf64_250'],
        current_SC='gap_sampler_250',optional=sel.get('optional',{}),systematic='archived;not selected',
        digital_R8_execution='available card;variable-output integrated path must use a matching trace')
    b['PV_backend']=dict(vacc=b['attention_cards']['bf_vacc16_250'],controller=b['attention_cards']['bf_vctrl4_250'],
        heads=32,KV_groups=8,lanes_per_head=2,state_FP32_per_head=128,feedback_cycles=7,
        area_method='retain full vacc16 register+ICG;scale other_logic by2/16;reference Vctrl x8',
        energy_method='vacc16 incremental pJ/ADD + full idle;Vctrl cold/reuse by actual cache misses + full idle',
        clock_gating='per-action increments + full gated residency;gross background removed once',
        qualification='setup passed;vacc/control hold deferred per user;compact2ADD and bank routing are structural proxies',
        area_is_new_compact_PPA=False,output_conversion='covered by named vector/output platform macro')
    # Keep the existing front-end matching the user's PPL contract, not the
    # FP32-first alternate recommended by a different handoff.
    b['numeric_front']='A:S12F4_RNE_sat_then_integer_maxgap_U8_P8'
    b['score_frontend']='s12_max_gap';b['score_front_card']='front_s12buf_250'
    b['front_sampler_link'].update(front_cycles=67,shared_load_handshakes=32,same_trace_integrated_PPA=False)
    anchor=next(x for x in reversed(d['area_anchor']['rows']) if x.get('top')=='bf_vacc16' and x.get('MHz')==250 and x.get('cell_area28_mm2'))
    w=next(x for x in anchor['windows'] if x.get('groups',{}).get('registers',{}).get('cells'))['groups']['registers']
    bitarea=w['area_um2']/w['cells']/1e6
    b['platform_macro']=dict(register_bit_area_mm2=bitarea,
        register_allocations_KiB={'DMA_return':16,'ordinary_operand_FIFO':8,'descriptors_control':4},
        vector_output_area_mm2=.25,CIM_programming_distribution_area_mm2=.15,
        total_activity_and_idle_W=.04,power_sensitivity_W=[.02,.08],
        source='measured28 register-cell mean area;named vector/interface area and20-80mW power scenario',
        includes=['DMA/FIFO/control','RMSNorm/RoPE/residual/vector reductions','PV final divideS andFP32-toBF16','CIM programming/local distribution'],
        excludes=['separately priced FFN staging/codec/state','SRAM macros','PV accum state/adder/controller',
            'external DRAM die/LPDDR PHY/pads/CPU/package/global CTS/SPEF'])
    b.update(status='UPDATED250_CONDITIONAL_TLM_BINDINGS_WITH_EXPLICIT_MACROS',refresh250_version=1,
        FFN_selected_core_count=3,conditional_TLM_ready=True,
        full_system_ready=False,physical_whole_chip_ready=False,full_system_replay_run=False,
        missing_bindings=[],remaining_estimates=['compact2ADD PV reference-width proxy','DMA/FIFO/vector/interface macro',
            'S2 read/write S0PT+same-libraryCLK delta','mean sampler service + reference address trace'],
        outside_model_boundary=['LPDDR PHY/pads/CPU/package','global CTS/SPEF','unmodeled constant TIE power'],
        qualification='zero-margin FFN/FMA;validated original Ising/R8;PV hold deferred;explicit platform macro',
        source_sha256=b.get('source_sha256',{})|{SOURCES[k]:hashlib.sha256(v).hexdigest() for k,v in raw.items()})
    c.update(score_frontend='s12_max_gap',price_profile='REFRESH250_ZERO_MARGIN_PV_MACRO_CLOSED',
        conditional_cost_model_complete=True,physical_full_clock_qualified=False)
    assert c['SRAM']['capacity_KiB']==832 and c['SRAM']['bank_count']==178
    assert (c['FMA_feedback_cycles'],c['PV_feedback_cycles'],c['PV_output_cycles'])==(4,7,16)
    return b,c

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,required=True);ap.add_argument('--out',type=Path)
    a=ap.parse_args();out=a.out or Path(__file__).resolve().parent/'250MHz';out.mkdir(parents=True,exist_ok=True)
    for name in ('BINDINGS','WHOLE_CONFIG'):
        p=out/(name+'_PRE_REFRESH_20261109.json')
        if not p.exists():p.write_bytes((out/(name+'.json')).read_bytes())
    b,c=refreshed(a.workspace,json.loads((out/'BINDINGS_PRE_REFRESH_20261109.json').read_bytes()),
                  json.loads((out/'WHOLE_CONFIG_PRE_REFRESH_20261109.json').read_bytes()))
    save(out/'BINDINGS.json',b);save(out/'WHOLE_CONFIG.json',c)
    # The inspector's original staging summary must not keep obsolete prices.
    p=out/'COMPONENTS.json';old=out/'COMPONENTS_PRE_REFRESH_20261109.json'
    if p.exists() and not old.exists():old.write_bytes(p.read_bytes())
    if old.exists():
        x=json.loads(old.read_bytes());x.update(status=b['status'],default_enabled=True,
            conditional_TLM_ready=True,full_system_ready=False,authority='BINDINGS.json + WHOLE_CONFIG.json')
        x['FFN'].update(area_mm2=b['FFN_core']['area_mm2'],modes=b['FFN_core']['modes'],
            timing=b['FFN_core']['slacks_ns'],source=b['FFN_core']['power_archive'])
        x['BF16']=b['shared_FMA'];x['digital_reference_cards']=b['digital_reference_cards']
        x['A9W8']=b['digital_reference_cards']['a9_endpoint_28_250']
        x['unavailable_power']=[];x['historical_staging_reference']=old.name
        x['PV_backend']=b['PV_backend'];x['remaining_estimates']=b['remaining_estimates']
        save(p,x)
    save(out/'REFRESH_SOURCE_INDEX.json',{k:dict(path=v,sha256=sha(a.workspace/v)) for k,v in SOURCES.items()})
    print(json.dumps(dict(status=b['status'],SC_core_mm2=b['FFN_core']['area_mm2'],
        FMA16_mm2=b['shared_FMA']['area_mm2'],PV_hold_deferred=True,other_clocks_untouched=True)))

if __name__=='__main__':main()
