"""832KiB mixed macros, preserving shared front-end striping.

30x8KiB +148x4KiB =832KiB,178 real1RW ports. Front106 macros share
544KiB; the unchanged eight Attention groups retain72 separate4KiB macros.
The first424KiB stripes across106 lower halves; the final120KiB uses the
upper halves of30 larger macros. A physical macro has one port across BOTH.
"""
from collections import Counter
from types import MethodType


def install(model, config):
    h=model.h;mem=h.mem
    assert h.now==0 and not h.events and not mem.queue and mem.nbank==208
    front=[r for r in sorted(mem.regions.values(),key=lambda r:r.base)
           if not r.name.startswith('Attention_KVgroup')]
    offsets={};cursor=0
    for r in front:offsets[id(r)]=cursor;cursor+=r.size//16;r.banks=tuple(range(106))
    assert cursor*16==544*1024
    for g,r in enumerate(model.att):r.banks=tuple(range(106+9*g,106+9*(g+1)))
    def location(region, word):
        if id(region) in offsets:
            linear=offsets[id(region)]+word
            if linear<106*256:
                row,bank=divmod(linear,106)
            else:
                upper,bank=divmod(linear-106*256,30);row=256+upper
            return bank,row
        return region.banks[word%9],word//9
    depths=(8192,)*30+(4096,)*148
    seen=set();allocation=[0]*178
    for r in mem.regions.values():
        for word in range(r.size//16):
            bank,row=location(r,word)
            assert 0<=bank<178 and 0<=row<depths[bank]//16
            assert (bank,row) not in seen
            seen.add((bank,row));allocation[bank]+=16
    assert len(seen)==832*1024//16 and allocation==list(depths)
    mem.capacity=mem.top=832*1024;mem.nbank=178;mem.bank_depths=depths;mem.bank_allocated=allocation
    mem.physical_bank_resolver=lambda region,word:location(region,word)[0]
    mem.physical_location=location;mem.bank_model_ids=('S2',)*30+('S0',)*148
    mem.bank_activity=[Counter() for _ in depths]
    model.sram_bank_row_bases={} # mixed row lookup is piecewise, not old uniform bases.
    prior_report=mem.report
    def report(self,end):
        value=prior_report(end)
        value['depth_model']='30real8KiB+148real4KiB;106sharedfront+72Attentionports'
        value['depth_wrapper_PPA']='fixed piecewise address decode/control estimate,not new STA'
        return value
    mem.report=MethodType(report,mem)
    h.return_banks=106
    model.compact_memory.update(physical_4KiB_banks=None,physical_macro_count=178,
        physical_macro_counts={'S2_8KiB':30,'S0_4KiB':148},front_banks=106,attention_banks=72,
        bank_depths_bytes=list(depths),profile='832_mixed30x8_148x4_shared106',
        macro_area55_mm2=None)
    model.candidate_sram_contract.update(bank_count=178,front_banks=106,attention_banks=72,
        mixed_macros=True,CIM_capacity_accounting={'S2_8KiB':30,'S0_4KiB':4},
        shared_front_capacity_KiB=544,physical_macro_counts={'S2_8KiB':30,'S0_4KiB':148},
        mapping='lower424KiB/106banks;upper120KiB/30banks;one1RWport_per_physical_macro',
        physical_words_unique=len(seen),CIM_not_exclusive34_ports=True)
