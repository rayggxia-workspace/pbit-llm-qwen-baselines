"""Keep DRAM/SRAM physical timing independent from the compute clock."""
from architecture_tlm.unified_v6.config import load
from architecture_tlm.unified_v6.memory_profiles import apply
from architecture_tlm.unified_v6.ffn_locality import configure

def configuration(case, bridge, output):
    c,m=load('qwen3_4b')
    hz=case.get('core_hz',500_000_000)
    c.update(core_hz=hz, context_tokens=2048, seed=case.get('seed',0),
             digital_weight_chunk_bytes=65536, weight_chunk_bytes=65536)
    c['random'].update(clock_hz=hz, energy_reference_hz=100_000_000)
    c['ffn']['mode']=case.get('ffn','sc')
    c['attention']['mode']=case.get('attention','screen_pv')
    c=apply(c,'mature_hbm2_pipelined',bridge,output)
    if case.get('expanded_compute'):
        c['macs_per_cycle']=2048
        c['ffn'].update(restore_lanes=64,accumulate_lanes=128,bucket_reduce_lanes=256)
    if c['ffn']['mode']=='sc':
        engines=32 if case.get('expanded_compute') else 8
        configure(c,tile=64,engines=engines,retain=8,source_groups=1)
        c['ffn']['nonlinear_samples']=case.get('nonlinear_samples',128)
        c['local_pipeline']=dict(overlap=True,weight_bypass=True)
    if case.get('expanded_sram'):
        c['sram'].update(capacity_bytes=8*1024**2, macro_depth=256,
                         banks=512,fabric_GBs=512.,clock_hz=80_000_000)
    c['clock_gating']=dict(enabled=case.get('clock_gating',False),idle_cycles=8,wake_cycles=1,
        boundary='compute clock branches only; no power gating, SRAM/DRAM/RNG clocks unchanged')
    if case.get('scope')=='one_layer':m['num_hidden_layers']=1
    return c,m
