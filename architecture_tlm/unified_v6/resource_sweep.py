"""Issue186 timing-only resource ablation; measured SRAM macro timings retained.

All common E profiles have exactly 8MiB = 2048 instances of measured 256x128
macro E at SS/80MHz. More banks expose more parallel ports; mux/NoC/CTS cost
and timing are NOT validated by the macro table. Compute throughput is an
explicit macro design target, not an RTL result.
"""
import copy

PROFILES={
    'anchor_F64':dict(macs=512,banks=64,fabric=64.,depth=4096),
    'c512_m64':dict(macs=512,banks=64,fabric=64.,depth=256),
    'c8192_m64':dict(macs=8192,banks=64,fabric=64.,depth=256),
    'c512_m512':dict(macs=512,banks=512,fabric=512.,depth=256),
    'c8192_m512':dict(macs=8192,banks=512,fabric=512.,depth=256),
    'c8192_m256':dict(macs=8192,banks=256,fabric=256.,depth=256),
    'c8192_m1024':dict(macs=8192,banks=1024,fabric=1024.,depth=256),
    'c32768_m512':dict(macs=32768,banks=512,fabric=512.,depth=256),
}


def apply(config,name,prefill=False):
    if name not in PROFILES:raise ValueError('unknown resource profile')
    c=copy.deepcopy(config);r=PROFILES[name]
    if c['ffn']['mode']!='bf16':raise ValueError('this ablation is a digital BF16 reference')
    c.update(core_hz=100000000,macs_per_cycle=r['macs'],vector_lanes=64,nonlinear_lanes=16,
             digital_shared_prefill=bool(prefill),digital_weight_chunk_bytes=65536,
             digital_operand_bytes=65536,weight_chunk_bytes=65536,double_buffer=True)
    c['sram'].update(capacity_bytes=8*1024**2,banks=r['banks'],fabric_GBs=r['fabric'],
                     macro_depth=r['depth'],word_bytes=16,clock_hz=80000000,corner='SS')
    c['random']['clock_hz']=c['core_hz']
    c['resource_experiment']=dict(profile=name,shared_prefill=prefill,
        boundary='same data/layout/clock/capacity; MAC target and bank/fabric resources vary independently',
        local_operand_bytes=65536,local_operand_banks=1,shared_slots=2,
        macro='F4096x128' if name=='anchor_F64' else 'E256x128',
        topology_PPA='unknown: bank mux, wiring, clock tree, local feed and MAC array not signed off',
        prefill_policy='ready-before-epilogue fill first; otherwise epilogue priority; single local consumer')
    return c
