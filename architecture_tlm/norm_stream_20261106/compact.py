"""Remove unused physical SRAM macros before the first transaction.

The 2MiB stream layout uses2008KiB. Pack its front-end into246x4KiB banks,
retain256 Attention banks, and charge502 banks/2008KiB, not512 phantom ports.
All tensor sizes and logical addresses remain unchanged.
"""
from types import MethodType
import math
from .model import make_model as norm_model


def compact_memory(hub, model):
    mem=hub.mem
    if hub.now or hub.events or hub.descriptors or mem.queue:
        raise ValueError('SRAM remapping only before any transaction')
    if mem.word!=16 or mem.capacity!=2*1024**2 or mem.nbank!=512:
        raise ValueError('expected unmodified2MiB norm-stream configuration')
    rows=sorted(mem.regions.values(),key=lambda r:r.base)
    front=[r for r in rows if not r.name.startswith('Attention_KVgroup')]
    attention=[r for r in rows if r.name.startswith('Attention_KVgroup')]
    if len(attention)!=8 or any(r.size!=131072 for r in attention):
        raise ValueError('only current eight-group128KiB Attention contract')
    front_bytes=sum(r.size for r in front)
    front_banks=math.ceil(front_bytes/4096)
    total_banks=front_banks+len(attention)*32
    allocations=[0]*total_banks;cursor=0;physical={}
    for r in front:
        if r.size%64:raise ValueError('unaligned tensor region')
        banks=tuple((cursor+j)%front_banks for j in range(front_banks))
        words=r.size//mem.word
        r.banks=banks
        bases={}
        for j,b in enumerate(banks):
            n=words//front_banks+(j<words%front_banks)
            bases[b]=allocations[b]//mem.word
            allocations[b]+=n*mem.word
        physical[r.name]=bases
        cursor=(cursor+words)%front_banks
    for i,r in enumerate(attention):
        banks=tuple(range(front_banks+32*i,front_banks+32*(i+1)))
        r.banks=banks
        physical[r.name]={b:0 for b in banks}
        for b in banks:allocations[b]=r.size//32
    if any(n>4096 for n in allocations):raise ValueError('packed bank overflow')
    capacity=total_banks*4096
    if mem.top>capacity:raise ValueError('logical allocation exceeds compact capacity')
    original_capacity,original_banks=mem.capacity,mem.nbank
    mem.capacity=capacity;mem.nbank=total_banks
    mem.bank_depths=(4096,)*total_banks;mem.bank_allocated=allocations
    hub.return_banks=front_banks  # unused legacy FIFO still has real backing
    model.sram_bank_row_bases=physical
    contract=dict(profile='stream_compact2008k_502bank',capacity_bytes=capacity,
        allocated_bytes=sum(allocations),unallocated_bytes=capacity-sum(allocations),
        removed_capacity_bytes=original_capacity-capacity,removed_banks=original_banks-total_banks,
        physical_banks=total_banks,front_banks=front_banks,attention_banks=256,
        bank_word_bytes=16,bank_ports='one read OR write per cycle per physical bank',
        attention_groups_unchanged=8,Attention_bank_ports_unchanged=32,
        old_and_new_tensor_sizes_equal=True,all_tensor_logical_addresses_equal=True,
        private_24KiB_ingress_holding_retained=True,
        mapping='region-striped front pool with cyclic remainder balancing; disjoint local row bases',
        caveat='fewer front ports are simulated; no new interconnect/decoder RTL PPA')
    model.sram_compaction_contract=contract
    parent=model.run
    def run(self):
        result=parent()
        result['sram_compaction_contract']=dict(contract)
        # The inherited common report had a historical fixed64..127 range;
        # actual allocation is authoritative after the new pool mapping.
        result['common_FFN']['state_bank_range']=[min(self.common_state.banks),max(self.common_state.banks)]
        result['common_FFN']['state_physical_bank_count']=len(self.common_state.banks)
        return result
    model.run=MethodType(run,model)
    return contract


def make_model(backend,profile='stream_2m',**kwargs):
    if profile!='stream_2m':raise ValueError('compact profile requires norm-stream base')
    h,m=norm_model(backend,profile=profile,**kwargs)
    compact_memory(h,m)
    return h,m
