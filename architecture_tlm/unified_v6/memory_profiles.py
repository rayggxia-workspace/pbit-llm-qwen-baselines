"""Documented memory profiles, not fitted arbitrary link performance.

DDR4 uses the real persistent DRAMSys backend. Missing executable is an error,
never a fallback. SRAM re-banking retains the same macro count/capacity/PVT.
"""
import copy
import os
from pathlib import Path

HERE=Path(__file__).resolve().parent
DRAM_CONFIG=HERE/'configs/dramsys/ddr4_2ch_2rank_NoPowerDown_core_limits.json'
PROFILES=('legacy','sram64','prefetch','ddr4','balanced_ddr4','mature_ddr4','mature_hbm2_narrow','mature_hbm2_wide')

def apply(config,profile,bridge=None,output_prefix=None):
    if profile not in PROFILES:raise ValueError('unknown memory profile')
    c=copy.deepcopy(config)
    c['memory_profile']=profile
    if profile in ('sram64','balanced_ddr4','mature_ddr4','mature_hbm2_narrow','mature_hbm2_wide'):
        c['sram'].update(capacity_bytes=8*1024**2,banks=64,fabric_GBs=64.)
        c['ffn']['local_weight_load_bytes_per_cycle']=1024
    if profile in ('prefetch','balanced_ddr4','mature_ddr4','mature_hbm2_narrow','mature_hbm2_wide'):
        c['ffn']['weight_schedule']='dma_prefetch'
        c['ffn']['prefetch_across_input_groups']=True
    if profile in ('ddr4','balanced_ddr4','mature_ddr4','mature_hbm2_narrow','mature_hbm2_wide'):
        executable=bridge or os.environ.get('PBIT_DRAMSYS_BRIDGE')
        if not executable or not Path(executable).is_file():
            raise ValueError('standard DDR4 requires PBIT_DRAMSYS_BRIDGE or --dram-bridge; no link fallback')
        if output_prefix is None:raise ValueError('unique DRAMSys output prefix required')
        c['dram']=dict(backend='dramsys',bridge_executable=str(Path(executable).resolve()),
            configuration=str(DRAM_CONFIG),output_prefix=str(output_prefix),burst_bytes=64,max_pending=32,
            standard='Micron 4Gb DDR4-1866 x8; 2 channels x 2 ranks; 16GiB',
            theoretical_pin_bandwidth_GBs=2*8*2/1.072,
            power_boundary='DRAMPower core current limits; PHY/controller/I/O unknown')
    if profile in ('mature_ddr4','mature_hbm2_narrow','mature_hbm2_wide'):
        c['schedule_policy']='shared_tiles'
        c['digital_weight_chunk_bytes']=c.get('digital_weight_chunk_bytes',65536)
        c['dram'].update(scatter_gather=True,sg_max_spans=256,descriptor_span_ns=1e9/c['core_hz'],strict_time_order=True)
    if profile.startswith('mature_hbm2'):
        wide=profile.endswith('wide')
        c['dram'].update(configuration=str(HERE/'configs/dramsys/hbm2_8ch_16GiB_timing.json'),
            max_pending=128 if wide else 32,host_request_bytes=256 if wide else 64,
            timing_only=True,standard='DRAMSys HBM2 example timings; 8 channels x 2 pseudochannels; 16GiB',
            theoretical_pin_bandwidth_GBs=256.,
            power_boundary='unknown: upstream HBM2 currents are zero placeholders; PowerAnalysis disabled',
            frontend_contract='1ns issue/response floor; adjacent aligned requests coalesced within each span only',
            frontend_response_capacity_bytes=32768 if wide else 2048)
    c['cost_policy']['memory_hierarchy']='DRAM -> shared banked SRAM ping/pong -> full-width local SC weight macro -> counters; no entire-layer residency assumption'
    return c
