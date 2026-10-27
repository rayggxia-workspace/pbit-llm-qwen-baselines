"""Banked scratchpad with consumer-sized local ports, no chipwide fabric cap.

Physical cells remain single port. DMA ingress and local read trunks are
separate resources, and still arbitrate at the exact same bank ports. This
uses the existing bounded beat and payload-credit scheduler, not a free NoC.
"""
import math
from collections import Counter
from architecture_tlm.sliced_sram_20261027.memory import ClusteredSRAM


class LocalPortSRAM(ClusteredSRAM):
    def __init__(self,cfg,spec,scheduler,ledger):
        super().__init__(cfg,spec,scheduler,ledger)
        self.top=cfg['local_ports']
        self.paths=self.top['path_bytes_per_core_cycle']
        self.core_hz=self.top['core_hz']
        if set(self.paths)!={'DMA','matrix','vector'} or min(self.paths.values())<=0:
            raise ValueError('missing or invalid physical endpoint width')
        self.directional=bool(self.top['independent_paths'])
        self.path_bytes=Counter()

    def _plan(self,ready,cl,banks,endpoint,size,write,access):
        if endpoint not in self.paths:raise ValueError('unmapped endpoint '+endpoint)
        if not self.directional:
            return super()._plan(ready,cl,banks,endpoint,size,write,access)
        bandwidth=self.paths[endpoint]*self.core_hz/1e9
        dur=math.ceil(size/bandwidth/self.net_period-1e-10)*self.net_period
        br=['sram_bank:'+str(b) for b in banks]
        direction='W' if write else 'R'
        # Point-to-point trunks terminate at local bank muxes. There is no
        # chipwide link shared by a vector read and an unrelated DMA fill.
        # A read/write on the SAME bank still uses the SAME br resource.
        lr=['sram_path:'+endpoint+':'+direction+':'+str(cl)]
        candidates=[]
        for slot in range(self.credits):
            buf='sram_payload_buffer:'+str(cl)+':'+str(slot);probe=ready
            while True:
                if write:
                    ls=self._earliest(probe,dur,lr,self.net_period)
                    bs=self._earliest(ls+dur,self.period,br,self.period)
                    first,last=ls,bs
                else:
                    bs=self._earliest(probe,self.period,br,self.period)
                    ls=self._earliest(bs+access,dur,lr,self.net_period)
                    first,last=bs,ls+dur
                free=self._earliest(first,last-first,[buf])
                if free<=first+1e-8:break
                probe=free
            candidates.append((last,first,slot,bs,ls,dur,br,lr,buf))
        return min(candidates,key=lambda x:(x[0],x[1],x[2]))

    def transfer(self,ready,address,size,write,tag):
        if size:
            words=(address+size+self.word-1)//self.word-address//self.word
            self.path_bytes[self.endpoint(tag,write)+('_W' if write else '_R')]+=words*self.word
        return super().transfer(ready,address,size,write,tag)

    def report(self,end_ns):
        r=super().report(end_ns)
        r['fabric_combined_read_write_GBs']=None
        r['scheduling']='single-port bank arbitration plus explicitly sized local endpoint trunks'
        r['local_ports']=dict(self.top,peak_per_slice_GBs=self.bpc*self.word/self.period,
            peak_bank_aggregate_GBs=self.c['banks']*self.word/self.period,
            endpoint_GBs_per_slice={k:(v*self.core_hz/1e9 if self.directional else self.endpoint_bw) for k,v in self.paths.items()},
            endpoint_width_contract='independent path widths' if self.directional else 'shared-link endpoint width; independent width hypotheses inactive',
            physical_path_bytes=dict(self.path_bytes),true_multiport_bitcells=False,
            capacity_replication_bytes=0,clock_period_checked_against_macro=True,
            scope='four memory slices feeding the existing single scheduled matrix/vector consumers; not four independently scheduled cores',
            gate_cost='endpoint/mux/driver/CDC/CTS not newly characterized; macro cells and action energy unchanged',
            end_to_end_PPA_calibrated=False)
        r['sliced']['aggregate_link_GBs']=None
        r['sliced']['cluster_link_GBs']=None if self.directional else self.bw
        r['sliced']['routing']=('word-striped physical banks; independent endpoint trunks' if self.directional else 'word-striped physical banks; per-slice shared R/W trunk')+'; no mesh or global wire cap'
        return r
