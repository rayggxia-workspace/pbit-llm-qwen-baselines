"""Documented memory profiles, not fitted arbitrary link performance.

DDR4 uses the real persistent DRAMSys backend. Missing executable is an error,
never a fallback. SRAM re-banking retains the same macro count/capacity/PVT.
"""
import copy
import os
from pathlib import Path

HERE=Path(__file__).resolve().parent
DRAM_CONFIG=HERE/'configs/dramsys/ddr4_2ch_2rank_NoPowerDown_core_limits.json'
PROFILES=('legacy','sram64','prefetch','ddr4','balanced_ddr4')

def apply(config,profile,bridge=None,output_prefix=None):
    if profile not in PROFILES:raise ValueError('unknown memory profile')
    c=copy.deepcopy(config)
    c['memory_profile']=profile
    if profile in ('sram64','balanced_ddr4'):
        c['sram'].update(capacity_bytes=8*1024**2,banks=64,fabric_GBs=64.)
        c['ffn']['local_weight_load_bytes_per_cycle']=1024
    if profile in ('prefetch','balanced_ddr4'):
        c['ffn']['weight_schedule']='dma_prefetch'
    if profile in ('ddr4','balanced_ddr4'):
        executable=bridge or os.environ.get('PBIT_DRAMSYS_BRIDGE')
        if not executable or not Path(executable).is_file():
            raise ValueError('standard DDR4 requires PBIT_DRAMSYS_BRIDGE or --dram-bridge; no link fallback')
        if output_prefix is None:raise ValueError('unique DRAMSys output prefix required')
        c['dram']=dict(backend='dramsys',bridge_executable=str(Path(executable).resolve()),
            configuration=str(DRAM_CONFIG),output_prefix=str(output_prefix),burst_bytes=64,max_pending=32,
            standard='Micron 4Gb DDR4-1866 x8; 2 channels x 2 ranks; 16GiB',
            theoretical_pin_bandwidth_GBs=2*8*2/1.072,
            power_boundary='DRAMPower core current limits; PHY/controller/I/O unknown')
    c['cost_policy']['memory_hierarchy']='DRAM -> shared banked SRAM ping/pong -> full-width local SC weight macro -> counters; no entire-layer residency assumption'
    return c
