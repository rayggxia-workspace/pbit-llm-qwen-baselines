"""Expose the existing 2048 single-port E macros, without replicating bits.

Each memory slice has128 ping,128 pong and256 workspace macros. This
deliberately reserves capacity for bandwidth: each64KiB weight slot owns2MiB
of physical bank capacity. The unused rows are NOT a second free workspace.
"""
from .memory import LocalPortSRAM


class PartitionedSRAM(LocalPortSRAM):
    def __init__(self,cfg,spec,scheduler,ledger):
        super().__init__(cfg,spec,scheduler,ledger)
        if cfg['banks']!=2048 or self.bpc!=512 or cfg['macro_depth']!=256 or self.macros!=2048:
            raise ValueError('partition requires2048 existing4KiB single-port macros')
        self.slot_bytes=self.top['weight_slot_bytes'];self.workspace_base=2*self.slot_bytes
        if self.slot_bytes%2048 or self.slot_bytes>2*1024**2:raise ValueError('invalid weight slot')
        self._physical=False

    def _validate(self,address,size,tag):
        if self._physical:
            if size<0 or address<0 or address+size>self.capacity:raise ValueError('physical SRAM overflow')
            return
        super()._validate(address,size,tag)
        if address>=self.workspace_base and address+size>self.workspace_base+4*1024**2:
            raise ValueError('workspace exceeds its reserved4MiB physical partition')
        if address<self.workspace_base and size and address//self.slot_bytes!=(address+size-1)//self.slot_bytes:
            raise ValueError('crosses weight slot')

    def map_word(self,word):
        """Virtual allocation word → actual row*2048+bank, no aliasing."""
        address=word*16
        if address<self.workspace_base:
            slot=address//self.slot_bytes;w=(address%self.slot_bytes)//16
            cl=(w//128)%4;local=slot*128+w%128;row=w//512
        else:
            w=(address-self.workspace_base)//16
            if w>=4*1024**2//16:raise ValueError('workspace word beyond physical partition')
            cl=(w//256)%4;local=256+w%256;row=w//1024
        if row>=256:raise ValueError('row beyond E macro')
        return row*2048+cl*512+local

    def transfer(self,ready,address,size,write,tag):
        if not size:return ready
        self._validate(address,size,tag);end=address+size
        lo=address//16;hi=(end+15)//16;done=ready
        self._physical=True
        try:
            while lo<hi:
                group=128 if lo*16<self.workspace_base else 256
                relative=lo if lo*16<self.workspace_base else lo-self.workspace_base//16
                # Weight slots are multiples of128 words in all supported
                # profiles. Splitting at a group boundary also bounds runs.
                stop=min(hi,lo+group-relative%group)
                left=max(address,lo*16);right=min(end,stop*16)
                physical=self.map_word(lo)*16+left-lo*16
                done=max(done,super().transfer(ready,physical,right-left,write,tag))
                lo=stop
        finally:self._physical=False
        return done

    def report(self,end_ns):
        r=super().report(end_ns)
        r['local_ports']['macro_partition']=dict(macros_per_slice=512,ping_macros_per_slice=128,
            pong_macros_per_slice=128,workspace_macros_per_slice=256,
            ping_physical_reserved_bytes=2*1024**2,pong_physical_reserved_bytes=2*1024**2,
            workspace_physical_reserved_bytes=4*1024**2,
            each_live_weight_slot_bytes=self.slot_bytes,
            all_bank_peak_GBs=r['bank_peak_GBs'],one_active_weight_slot_peak_GBs=512*16/self.period,
            note='unused ping/pong rows not reused as workspace; distinct macros permit concurrent preload/current reads')
        return r
