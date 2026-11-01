"""Audit the frozen initial replacement estimate; no new execution model."""
from pathlib import Path
import json,hashlib,math,argparse

GROUPS={
 'FFN_GU_and_down_compute_restore':(['FFN_counter','FFN_postscale_restore_proxy'],['FFN_counter','FFN_postscale_restore_proxy','NL_Wd_active','NL_Wd_inactive_scenario']),
 'shared_digital_MAC':(['ordinary_BF16_MACs'],['ordinary_BF16_MACs']),
 'onchip_storage_and_DMA_buffers':(['shared_SRAM','local_CIM_SRAM_base','digital_local_buffers','DMA_response_buffers'],['shared_SRAM','local_CIM_SRAM_base','digital_local_buffers','DMA_response_buffers']),
 'attention_sampler_PV_and_screen':(['Attention_existing_PRNG_endpoints','PV_vector_adders'],['Attention_complete_sampler_S128_reserved_for_S64','PV_vector_adders','Attention_SparQ_logic']),
 'FFN_random_and_remaining':(['wide_partial_activity_proxy','FFN_shared64_input_frontend','FFN_nonlinear_10_local_PRNG_endpoints','FFN_and_selector_sigmoid_tables','other_vector_and_nonlinear_proxy'],['wide_partial_activity_proxy','FFN_shared64_input_frontend','FFN_external_RNG_reserved_old_endpoint_budget','FFN_and_selector_sigmoid_tables','other_vector_and_nonlinear_proxy'])}

def run(root):
    ip=root/'INPUTS.json';rp=root/'results/RESULTS.json';ap=root/'ANALYSIS_INPUTS.json'
    i=json.loads(ip.read_bytes());r=json.loads(rp.read_bytes());a=json.loads(ap.read_bytes());c=r['cases'][0];corners=c['corners'];old=i['baseline']['modules']
    rows=[]
    for name,(ok,nk) in GROUPS.items():
        original=sum(old[k]['energy_mJ_per_token'] for k in ok)
        new=[sum(x['modules_mJ'][k] for k in nk) for x in corners]
        rows.append(dict(group=name,old_mJ=original,new_mJ=[min(new),max(new)],saving_mJ=[original-max(new),original-min(new)]))
    assert math.isclose(sum(x['old_mJ'] for x in rows),i['baseline']['fma']['covered_onchip_mJ_per_token'],rel_tol=1e-12)
    for cc in corners:
        assert math.isclose(sum(sum(cc['modules_mJ'][k] for k in nk) for _,nk in GROUPS.values()),cc['onchip_mJ'],rel_tol=1e-12)
    sampler_active_s=i['attention']['groups_per_token']*4*a['sampler_reference_mean_cycles']/i['attention']['clock_hz']
    idle=[]
    for cc in corners:
        inactive=max(0,8*cc['time_ms']*1e-3-sampler_active_s)
        extra=inactive*a['sampler_idle_diagnostic_W']*1000
        idle.append(dict(time_ms=cc['time_ms'],extra_sampler_idle_mJ=extra,with_idle_onchip_mJ=cc['onchip_mJ']+extra))
    # This retains the S128 work duration as an allowance, not actual S64 timing.
    p=i['baseline']['phase_ns'];ffn_old=sum(p[k] for k in ['FFN_gate_up','FFN_nonlinear_encoding','FFN_AND_direct_down','ffn_output_conversion','ffn_residual'])*1e-6
    fixed_projection=(p['QKV_projection']+p['O_projection'])*1e-6
    counter=[cc['modules_mJ']['FFN_counter']+cc['modules_mJ']['FFN_postscale_restore_proxy'] for cc in corners]
    nl=[cc['modules_mJ']['NL_Wd_active']+cc['modules_mJ']['NL_Wd_inactive_scenario'] for cc in corners]
    result=dict(date='2026-11-01',scope='audit of frozen estimate; no new TLM/DRAMSys/RTL/model/PPL',
        energy_groups=rows,remaining_GU_count_restore_mJ=[min(counter),max(counter)],new_NL_Wd_with_idle_mJ=[min(nl),max(nl)],
        time_ms=dict(FFN_old=ffn_old,FFN_new=[ffn_old,ffn_old+c['exposed_NL_increase_allowance_ms']],GU_unchanged=p['FFN_gate_up']*1e-6,QKV_O_unchanged=fixed_projection,lm_head_unchanged=p['lm_head_and_argmax']*1e-6,attention_old=p['attention_core']*1e-6,attention_new=c['attention_ms']),
        attention_idle_existing_data_sensitivity=idle,attention_idle_diagnostic_is_gated_leakage=False,
        old_estimate_files_modified=False,whole_chip_area=None,
        inference=['largest retained compute quote is GU, based on legacy shared B7-scaled counter pool','new Attention time gain depends on8 independent local services, not a completed shared-backend experiment','extra NL kernels are separate from preserved GU pool; unchanged output column count does not imply equal area','nonlinearity128->64 and attention algorithm/source/sample/parallel changes are confounded, not a same-quality microarchitecture ablation'],
        input_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ip,rp,ap]})
    out=root/'results/CHANGE_ANALYSIS.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).parent);a=p.parse_args();run(a.root)
