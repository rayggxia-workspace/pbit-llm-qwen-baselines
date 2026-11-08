"""Prepare current28nm macro contracts;no full-system timing or55nm scaling.

Reads owner handoffs without modifying them. Re-run after new measured results
arrive, then freeze the generated bindings with each future scheduler run.
"""
from pathlib import Path
import argparse,hashlib,json

INPUTS={
 'ffn':'architecture_tlm/module_handoff/ffn_tlm28_250_500_20261108/profile.json',
 'aux':'architecture_tlm/module_handoff/ffn_tlm28_250_500_20261108/COMPONENT_RESULTS.json',
 'digital':'architecture_tlm/module_handoff/ffn_tlm28_250_500_20261108/DIGITAL_RESULTS.json',
 'attention':'architecture_tlm/module_handoff/attention_tlm28_250_500_20261108/PROFILE.json',
 'earlier':'architecture_tlm/module_handoff/ffn_tsmc28_three_classes_20261107/POWER_RESULTS_20261108.json',
}

def short_aux(c):
    return {k:c.get(k) for k in ('status','timing_qualified','clock_MHz','area_mm2',
        'unit','idle_W','latency_cycles','macro_latency_cycles','input_II_cycles',
        'setup_uncertainty_ns','hold_uncertainty_ns','setup_slack_ns','hold_slack_ns',
        'unknown_TIE_power_W')}|{'modes':{m:{k:v.get(k) for k in (
        'gross_pJ_per_unit','incremental_pJ_per_unit','gross_pJ_per_FMA',
        'measurement_ns_per_unit')} for m,v in c['modes'].items()}}

def short_attention(c):
    assert c['qualified_module_price'] and c['timing_pass']
    assert c['area_factor']==1
    return {k:c.get(k) for k in ('top','MHz','area28_mm2','clock_period_ns',
        'query_latency_cycles','mean_query_cycles_excluding_interquery_gap',
        'output_count','operation_definition','source_manifest_sha256','reports_sha256',
        'slacks_ns','warnings')}|{'modes':c['modes'],'qualified_module_price':True}

def ffn_core_cost(core,frames,cores,wall_ns):
    """Gross active + remaining core residency idle, in pJ;one shared GU/Wd pool."""
    busy=sum(frames[m]*core['modes'][m]['frame_ns'] for m in ('GU','Wd'))
    assert cores>0 and cores*wall_ns+1e-6>=busy,'insufficient core capacity'
    active=sum(frames[m]*core['modes'][m]['gross_pJ_per_frame'] for m in frames)
    return dict(core_busy_ns=busy,activity_pJ=active,
        idle_pJ=(cores*wall_ns-busy)*core['waiting_power_W']*1000,
        area_mm2=cores*core['area_mm2'])

def prepare(workspace):
    raw={k:(workspace/v).read_bytes() for k,v in INPUTS.items()}
    d={k:json.loads(v) for k,v in raw.items()};f=d['ffn'];a=d['attention']
    assert f['area_multiplier']==a['area_factor']==1
    assert f['process']==a['process']=='TSMC28HPC+'
    assert a['geometry']['K']==128
    results={}
    for mhz in (250,500):
        n=str(mhz);core=f['selected_SC_cores'][n]
        assert core['timing_qualified'] and core['area_multiplier']==1
        assert core['clock_MHz']==mhz
        for mode,t in [('GU',16),('Wd',32)]:
            x=core['modes'][mode]
            assert x['samples']==t and x['frame_ns']==x['frame_cycles']*1000/mhz
            assert x['DOT64_per_frame']==128
        services={}
        for kind in ('state','codec','scale'):
            c=d['aux']['components'].get(kind+'_'+n)
            assert c and c['timing_qualified']
            services[kind]=short_aux(c)
        # Only alreadyqualified current28nm cards, never timing-failed diagnostics.
        cards={k:short_attention(v) for k,v in a['cards'].items()
            if v['MHz']==mhz and v.get('qualified_module_price') and v.get('timing_pass')}
        front=cards['front_s12buf_'+n];sampler=cards['gap_sampler_'+n]
        accepted_digital={k:short_aux(v) for k,v in d['digital']['components'].items()
            if v.get('clock_MHz')==mhz and v.get('timing_qualified')}
        if mhz==250:
            v=d['earlier']['qualified_pre_layout_prices']['bf16_250']
            shared_fma=dict(status='QUALIFIED_OLDER_FMA16_C4_CARD_EXACT_CONTEXTPORT_BINDING_PENDING',
                lanes=16,contexts=4,area_mm2=v['area_mm2'],
                gross_pJ_per_FMA=v['modes']['continuous']['gross_pJ_per_DOT64']/64,
                idle_W=v['modes']['idle_hold']['mean_core_power_mW']/1000,
                issue='204',latency_cycles=None,
                note='pipeline/context facts must be bound,not inferred fromwindowlength')
        else:
            candidates={k:v for k,v in accepted_digital.items() if 'bf16' in k}
            shared_fma=dict(status='CURRENT_NEW_CARD_AVAILABLE_BINDING_PENDING' if candidates else 'PPA_PENDING',
                current_candidates=list(candidates),area_mm2=None,gross_pJ_per_FMA=None,latency_cycles=None)
        required=['SRAM28_geometry_ports_access_cycle_energy_area','shared_DMA_FIFO_and_vector_RMSNorm_RoPE_residual',
            'CIM_programming_interface_and_physical_interconnect','shared_FMA_exact_latency_context_resource_binding',
            'finite_memory_credit_backpressure_scheduler_replay','qualified_compact_PV_and_output_codec_binding']
        result=dict(status='COMPONENT_BINDINGS_READY_FULL_SYSTEM_PENDING',process='TSMC28HPC+',PVT='TT0.9V25C',
            clock_MHz=mhz,period_ns=1000/mhz,area_multiplier=1,
            numeric_front='A:S12F4_RNE_sat_then_integer_maxgap_U8_P8',
            FFN_core={k:core[k] for k in ('status','clock_MHz','area_mm2','area_multiplier','modes',
                'waiting_power_W','setup_uncertainty_ns','hold_uncertainty_ns','slacks_ns','price_origin')},
            FFN_shared_aux=services,FFN_shared_services=f['shared_services'],
            FFN_staging_proxy=f['estimated_shared_staging'][n],
            FFN_candidate_core_counts=f['candidate_core_counts'][n],FFN_selected_core_count=None,
            attention_cards=cards,accepted_digital_components=accepted_digital,shared_FMA=shared_fma,
            front_sampler_link=dict(front_cycles=front['query_latency_cycles'],
                backend_query_cycles_observed_mean=sampler['mean_query_cycles_excluding_interquery_gap'],
                shared_load_handshakes=32,shared_handshake_must_not_be_double_counted=True,
                same_trace_integrated_PPA=False,fixed_service_cycle_guarantee=False),
            external_memory=dict(policy='reuse independent LPDDR timing/controller model unchanged',
                scale_rate_with_core_frequency=False,energy_pJ_per_bit='explicit independent scenario'),
            missing_bindings=required,full_system_ready=False,full_system_replay_run=False,
            full_system_area_mm2=None,full_system_energy_mJ_token=None,full_system_time_ms_token=None,
            defaults55nm_changed=False,not_postlayout=True,
            qualification='FFN/aux zero setupunc,Attention10%period;keep separate scenario labels',
            source_sha256={INPUTS[k]:hashlib.sha256(v).hexdigest() for k,v in raw.items()})
        results[n]=result
    return results

def write(workspace,out):
    d=prepare(workspace);out.mkdir(parents=True,exist_ok=True)
    for n,v in d.items():
        p=out/(n+'MHz');p.mkdir(exist_ok=True)
        (p/'BINDINGS.json').write_bytes((json.dumps(v,indent=2)+'\n').encode())
    return d

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--out',type=Path,default=Path(__file__).resolve().parent)
    x=p.parse_args();r=write(x.workspace,x.out)
    print(json.dumps({k:dict(qualified_attention_cards=len(v['attention_cards']),
        FFN_frame_cycles={m:v['FFN_core']['modes'][m]['frame_cycles'] for m in ('GU','Wd')},
        full_system_ready=v['full_system_ready']) for k,v in r.items()}))
