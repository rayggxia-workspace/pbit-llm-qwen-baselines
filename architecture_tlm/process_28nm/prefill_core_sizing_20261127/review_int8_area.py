"""Reprice earlier throughput targets from measured native cores; no new TLM/PPA."""
from pathlib import Path
import hashlib,json,math

def main():
    D=Path(__file__).parent;p=D/'AREA_REVIEW_INPUTS.json';i=json.loads(p.read_bytes())
    oldraw=(D/'RESULTS.json').read_bytes();assert hashlib.sha256(oldraw).hexdigest()==i['previous_result_sha256']
    old=json.loads(oldraw);work=old['workload'];sc=i['SC_GU'];dc=i['DCIM_B1']
    def native_top(x):return x['task_DOT64']*64*2/x['task_ns']/1000
    densities=dict(SC_GU_TOPS_per_mm2=native_top(sc)/sc['area_mm2'],
                   DCIM_B1_TOPS_per_mm2=native_top(dc)/dc['area_mm2'])
    densities['DCIM_over_SC_GU']=densities['DCIM_B1_TOPS_per_mm2']/densities['SC_GU_TOPS_per_mm2']
    sram=i['SRAM'];cases=[]
    for C,lanes,rows in [(96,16384,128),(192,32768,256)]:
        target=lanes*250e6*2/1e12
        point=next(x for x in old['cases'] if x['cores']==C and x['FMA_lanes']==lanes)
        variants=[]
        for key in ['DCIM_B16','WS_B16']:
            x=i[key];rate=native_top(x);copies=math.ceil(target/rate-1e-10)
            variants.append(dict(backend=key,copies=copies,compute_area_mm2=copies*x['area_mm2'],
                 measured_native_TOPS=rate,pool_TOPS=copies*rate,
                 scope='replicated compute-only budget; operands,scale,reduction,memory and routing external'))
        a9=i['A9'];arate=128/a9['ns_per_unit']/1000;acopies=math.ceil(target/arate-1e-10)
        bare=dict(copies=acopies,area_mm2=acopies*a9['area_mm2'],scope='bare dot64 replication; no matrix supply or state; not main whole-path price')
        state=point['planning_state_payload_bytes'];macros={k:math.ceil(state/v['bytes'])*v['area_mm2'] for k,v in sram.items()}
        ff_area=C*sc['area_mm2'];fp_area=lanes/i['BF16_FMA16']['lanes']*i['BF16_FMA16']['area_mm2']
        # Example multicast layout: eight token clusters process distinct rows.
        fanout=8;local_rows=rows//fanout;assert local_rows*fanout==rows
        payload=C*local_rows*128*8
        # Retain aggregate state bandwidth by striping data over enough 4KiB banks.
        port_GBs=16*250e6/1e9;nb=max(math.ceil(payload/sram['S0']['bytes']),math.ceil(point['state_port_aggregate_GBs']/port_GBs))
        physical=nb*sram['S0']['bytes'];state_area=nb*sram['S0']['area_mm2']
        # Keep the current bank32 contract:16x512B subarrays/core, each S0/8 proxy.
        cim_area=C*16*(sram['S0']['area_mm2']/8)
        multicast=dict(status='proposed_not_bank_simulated',fanout=fanout,global_weight_reuse_tokens=rows,
            rows_per_core=local_rows,state_payload_bytes=payload,ordinary_4KiB_banks=nb,
            physical_state_bytes=physical,state_area_mm2=state_area,
            aggregate_state_GBs=nb*port_GBs,dram_weight_bytes_unchanged=True,
            local_CIM_write_bytes_multiplier=fanout,
            compute_plus_program_s=point['floors']['FFN_compute_s']+fanout*point['floors']['FFN_program_s'])
        totals=[dict(backend=v['backend'],four_component_subtotal_mm2=ff_area+v['compute_area_mm2']+state_area+cim_area) for v in variants]
        cases.append(dict(cores=C,attention_peak_target_TOPS=target,previous_BF16_matrix_area_mm2=fp_area,
            PCIM_compute_area_mm2=ff_area,old_state_payload_bytes=state,old_state_capacity_area_mm2=macros,
            INT8_variants=variants,bare_A9_reference=bare,multicast=multicast,
            CIM_capacity_only_proxy_mm2=cim_area,four_component_subtotals=totals,
            excludes='other activation/attention buffers, state/codec/control logic, distribution, PHY/pads/CTS;21bit price delta'))
    out=dict(status='measured_component_and_literature_review_not_new_integrated_PPA',
        date='2026-11-27',model=old['model'],prompt=2048,clock_MHz=250,
        operations=2*(work['ffn_mac']+work['qkvo_mac']+work['attention_mac']),
        dense_compute_required_TOPS_for_2s=(work['ffn_mac']+work['qkvo_mac']+work['attention_mac'])/1e12,
        densities=densities,SC_GU_energy_saving_vs_DCIM=1-sc['pJ_per_DOT64']/dc['pJ_per_DOT64'],
        cases=cases,primary_sources=i['papers'],input_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        flags=dict(old_results_unchanged=True,attention_INT8_quality='not evaluated',host_default_unchanged=True,
                   no_new_TLM_or_PPA=True,no_free_clock_scaling=True,old_SC_price_bits=19,new21bit_PPA_unknown=True))
    dest=D/'INT8_AREA_REVIEW.json';raw=(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode();dest.write_bytes(raw)
    dest.with_suffix('.sha256').write_text(hashlib.sha256(raw).hexdigest()+'\n',encoding='ascii')
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
