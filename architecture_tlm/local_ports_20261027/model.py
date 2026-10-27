"""Optional memory-topology profile on the existing complete decode TLM."""
from architecture_tlm.scheduling_v2_20261027.model import SchedulingDecode
from .memory import LocalPortSRAM


def configure(c,clock_hz=250_000_000,independent=True,wide=True):
    s=c['sram'];clusters=4;core=c['core_hz'];banks=s['banks']
    if s['capacity_bytes']!=8*1024**2 or banks!=512 or s['word_bytes']!=16:
        raise ValueError('this profile characterizes 8MiB/512 bank/128-bit geometry')
    if c['macs_per_cycle']%clusters or c['vector_lanes']%clusters:
        raise ValueError('consumer lanes must map across four memory interfaces')
    # Input BF16 weights: one new two-byte weight per installed MAC/cycle.
    # Vector: one FP32 value per installed lane/cycle (other operands reused).
    # DMA: 128B per core edge per slice = 256GB/s aggregate @500MHz,
    # matched to the configured standard single-stack HBM2 peak. The actual
    # DRAMSys completion timestamps, not this port peak, govern availability.
    widths=dict(matrix=c['macs_per_cycle']//clusters*2,
                vector=c['vector_lanes']//clusters*4,DMA=128)
    bank_peak=banks*s['word_bytes']*clock_hz/1e9
    s.update(clock_hz=clock_hz,fabric_GBs=bank_peak)
    shared=(widths['matrix']*core/1e9 if wide else 128.)
    # Inherited constructor uses this ONLY as a geometry-validation ceiling;
    # the new independent planner never reserves that aggregate resource.
    s['sliced']=dict(mode='beats',clusters=clusters,credits=2,cluster_GBs=shared,
        endpoint_GBs=shared,network_period_ns=1e9/core,write_credit_release='accept')
    if shared*clusters>bank_peak:
        # At 200MHz the wide consumer can exceed bank rate, which is legal:
        # bank calendars limit supply. Retain the physical-bank sum as the
        # constructor's declared budget and size the inherited shared link
        # at the lesser peak for the shared-link control only.
        s['sliced']['cluster_GBs']=bank_peak/clusters
        s['sliced']['endpoint_GBs']=bank_peak/clusters
    s['local_ports']=dict(core_hz=core,independent_paths=independent,
        path_bytes_per_core_cycle=widths,bank_clock_hz=clock_hz,
        macro_reference='E:256x128 SS; read min period3.468ns, write3.4271ns',
        global_fabric_cap_removed=True,consumer_mapping='four adjacent memory feeds to the existing matrix and vector consumers',
        narrow_shared_control=not wide)
    return c


class LocalPortsDecode(SchedulingDecode):
    def __init__(self,c,shape,scheduler=None):
        if c['attention']['mode'] not in ('exact','pv','screen_exact','screen_pv'):
            raise ValueError('Ising output sink still needs a separate beat adapter')
        factory=LocalPortSRAM
        if c['sram']['local_ports'].get('physical_partition',False):
            from .partition import PartitionedSRAM
            factory=PartitionedSRAM
        super().__init__(c,shape,scheduler=scheduler,memory_factory=factory)

    def run(self):
        r=super().run()
        r['limitations']=[v for v in r['limitations'] if v not in (
            'SRAM blocking descriptors and DRAM bounded windows, no arbitrary multi-DMA reorder',
            'parallel sampling sink owns SRAM fabric for complete FSM; conservative blocking mapping')]
        r['limitations']+=['local scratchpad bank period checked against SS macro; wide endpoint wiring/CDC/CTS are architecture hypotheses',
            'single DMA actor, one response buffer and original operator lifecycle retained; no four-core or direct-burst-DMA claim',
            'finite link buffers retained:16KiB outside 8MiB; endpoint/mux/driver circuit cost not yet calibrated']
        r['unpriced_actions']['local_endpoint_physical_bytes']=sum(self.mem.path_bytes.values())
        r['unpriced_actions']['local_payload_buffer_bytes']=r['SRAM']['sliced']['additional_payload_buffer_bytes']
        return r


def configure_exposed(c,clock_hz=250_000_000):
    configure(c,clock_hz=clock_hz)
    s=c['sram'];s.update(banks=2048,fabric_GBs=2048*16*clock_hz/1e9)
    s['sliced']['quantum_words']=128
    s['local_ports'].update(physical_partition=True,weight_slot_bytes=c['weight_chunk_bytes'],
        exposed_single_port_macros=2048,old_macro_mux_removed=True)
    return c


def widen_burst_ports(c):
    """Matched-width topology control: do not impose HBM average rate twice.

The bounded64KiB response buffer already exists. Its burst read interface
is sized to the same local bank bus; actual HBM completions still gate each
tile. Buffer banking/mux/gearbox is a stated macro hypothesis, not measured
free hardware. All variants retain the SAME payload-credit capacity.
"""
    p=c['sram']['local_ports'];width=p['path_bytes_per_core_cycle']['matrix']
    p['path_bytes_per_core_cycle']=dict(matrix=width,vector=width,DMA=width)
    p.update(matched_endpoint_width=True,
        response_buffer_burst_read_contract='same width as local bank/matrix trunk; banking/driver PPA not yet characterized')
    return c
