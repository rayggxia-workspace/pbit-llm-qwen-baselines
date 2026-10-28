from architecture_tlm.scheduling_v2_20261027.model import SchedulingDecode
from .memory import ClusteredSRAM


class SlicedDecode(SchedulingDecode):
    def __init__(self,config,shape,scheduler=None):
        if config['attention']['mode'] not in ('exact','pv','screen_exact','screen_pv'):
            raise ValueError('parallel Ising SRAM sink requires separate beat mapping')
        super().__init__(config,shape,scheduler=scheduler,memory_factory=ClusteredSRAM)

    def run(self):
        r=super().run()
        r['limitations']=[v for v in r['limitations'] if v not in (
            'SRAM blocking descriptors and DRAM bounded windows, no arbitrary multi-DMA reorder',
            'parallel sampling sink owns SRAM fabric for complete FSM; conservative blocking mapping')]
        r['limitations']+=['shared SRAM now has bank/endpoint/link arbitration and finite payload credits; no BookSim/CTS/PPA validation',
            'DRAM single actor, bounded windows and original operator dependencies retained',
            'additional link payload buffers explicitly reported, circuit power not yet priced']
        r['unpriced_actions']['cluster_link_bytes']=sum(self.mem.link_bytes.values())
        r['unpriced_actions']['cluster_payload_buffer_bytes']=r['SRAM']['sliced']['additional_payload_buffer_bytes']
        return r


def configure(c,mode='beats',clusters=4,credits=2):
    c['sram']['sliced']=dict(mode=mode,clusters=clusters,credits=credits,
        cluster_GBs=c['sram']['fabric_GBs']/clusters,
        endpoint_GBs=c['sram']['fabric_GBs']/clusters,
        network_period_ns=1e9/c['core_hz'],write_credit_release='accept')
    return c
