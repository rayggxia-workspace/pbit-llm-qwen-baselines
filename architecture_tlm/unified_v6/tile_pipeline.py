"""Finite tile lifecycle shared by digital and stochastic matrix engines.

One DMA response slot, two shared-SRAM slots, one active consumer. Default
overlap is DMA-only. The explicit digital_shared_prefill option overlaps next
shared fill too, without a second local consumer or actor rewind. Arithmetic
and local-port timing remain operator contracts.
"""
from collections import Counter

class TilePipeline:
    def __init__(self, owner):
        self.o=owner;self.pending=None;self.active=None;self.staged=None;self.serial=0
        self.digital_prefill=owner.c.get('digital_shared_prefill',False)
        self.generations=[0,0];self.records={'digital':[],'sc':[]}
        self.counts={'digital':Counter(),'sc':Counter()}
        self.capacity=owner.c['weight_chunk_bytes']
        self.digital_capacity=owner.c.get('digital_operand_bytes',owner.c.get('digital_weight_chunk_bytes',self.capacity))
        if self.digital_capacity<owner.c.get('digital_weight_chunk_bytes',self.capacity):
            raise ValueError('digital operand storage smaller than configured tile')
        self.sc_capacity=owner.c['ffn'].get('local_weight_bytes',0)

    def issue(self, ready, name, offset, size, owner, **extra):
        o=self.o
        if self.pending is not None or self.staged is not None:raise ValueError('DMA response/staged queue full')
        if owner not in self.counts or size<1 or size>self.capacity:raise ValueError('tile outside response/staging capacity')
        slot=o.slot_serial%2;o.slot_serial+=1
        ready=max(ready,o.slot_free[slot]);self.generations[slot]+=1;self.serial+=1
        done=o.dram.tensor(ready,name,offset,size)
        ticket=dict(wave_id=self.serial,weight_name=name,name=name,offset=offset,bytes=size,
            owner=owner,slot=slot,generation=self.generations[slot],issue_ns=ready,
            dma_issue_ns=ready,dram_done_ns=done,dma_done_ns=done,**extra)
        self.pending=ticket;c=self.counts[owner];c['issued']+=1;c['bytes']+=size
        c['max_pending']=max(c['max_pending'],1)
        if self.active is not None:
            c['issue_during_previous_compute']+=int(ready<self.active.get('compute_done_ns',ready))
        o.e.action(('SC' if owner=='sc' else 'digital')+'_DMA_response_buffer_write_byte',size,'weight_interface')
        return ticket

    def fill(self, ready, ticket):
        if self.staged is ticket:
            if self.active is not None:raise ValueError('previous consumer must retire before activation')
            self.staged=None;self.active=ticket
            ticket['activation_ns']=max(ready,ticket['fill_done_ns'])
            return ticket['activation_ns'],ticket['slot']
        if self.pending is not ticket:raise ValueError('stale or unowned DMA ticket')
        if self.active is not None:raise ValueError('previous tile must retire before SRAM fill')
        o=self.o;slot=ticket['slot']
        if ticket['generation']!=self.generations[slot]:raise ValueError('stale slot generation')
        start=max(ready,ticket['dma_done_ns'],o.slot_free[slot])
        done=o.mem.transfer(start,o.slots[slot],ticket['bytes'],True,'weight_fill')
        ticket.update(fill_start_ns=start,fill_done_ns=done)
        o.e.action(('SC' if ticket['owner']=='sc' else 'digital')+'_DMA_response_buffer_read_byte',ticket['bytes'],'weight_interface')
        self.pending=None;self.active=ticket;self.counts[ticket['owner']]['filled']+=1
        return done,slot

    def prefill(self,ready,ticket):
        """Fill the other shared slot, retaining one active local consumer.

        Caller orders this descriptor against the current output epilogue;
        no future reservation is inserted ahead of earlier-ready SRAM work.
        This does NOT preload a second local operand bank.
        """
        if not self.digital_prefill or ticket['owner']!='digital':raise ValueError('prefill not enabled for this owner')
        if self.pending is not ticket or self.staged is not None:raise ValueError('prefill ticket ownership')
        if self.active is None or self.active['slot']==ticket['slot']:raise ValueError('prefill needs a distinct shared slot')
        if 'compute_done_ns' not in self.active:raise ValueError('active tile computation not scheduled')
        o=self.o;slot=ticket['slot']
        if ticket['generation']!=self.generations[slot]:raise ValueError('stale slot generation')
        start=max(ready,ticket['dma_done_ns'],o.slot_free[slot])
        done=o.mem.transfer(start,o.slots[slot],ticket['bytes'],True,'weight_fill')
        ticket.update(fill_start_ns=start,fill_done_ns=done,prefilled=True)
        o.e.action('digital_DMA_response_buffer_read_byte',ticket['bytes'],'weight_interface')
        self.pending=None;self.staged=ticket;c=self.counts['digital'];c['filled']+=1;c['prefilled']+=1
        c['prefill_ready_before_previous_compute_end']+=int(start<self.active['compute_done_ns'])
        return done

    def compute(self,ticket,start,done):
        if self.active is not ticket or start+1e-6<max(ticket['fill_done_ns'],ticket.get('activation_ns',0)) or done<start:
            raise ValueError('compute must own a filled tile')
        ticket.update(compute_start_ns=start,compute_done_ns=done)
        self.o.slot_free[ticket['slot']]=done

    def retire(self,ticket,done):
        if self.active is not ticket or done+1e-6<ticket['compute_done_ns']:
            raise ValueError('retire must follow owned computation')
        ticket['retire_done_ns']=done
        self.o.slot_free[ticket['slot']]=max(self.o.slot_free[ticket['slot']],done)
        self.active=None;owner=ticket['owner'];self.counts[owner]['retired']+=1
        if len(self.records[owner])<self.o.c['trace_event_limit']:self.records[owner].append(dict(ticket))

    def report(self):
        result=dict(contract=('one response ticket, two shared slots, one active operand tile; digital next shared fill may overlap MAC; local load remains after previous retirement'
            if self.digital_prefill else 'one response ticket, two shared slots, one active operand tile; DMA-only overlap'),
            shared_response_capacity_bytes=self.capacity,full_area_mm2=None,full_energy_J=None)
        for owner in self.counts:
            result[owner]=dict(records=self.records[owner],counts=dict(self.counts[owner]),
                pending=self.pending is not None and self.pending['owner']==owner,
                active=self.active is not None and self.active['owner']==owner,
                staged=self.staged is not None and self.staged['owner']==owner,
                response_capacity_bytes=self.capacity,
                operand_capacity_bytes=self.digital_capacity if owner=='digital' else self.sc_capacity,
                records_truncated=self.counts[owner]['retired']>len(self.records[owner]))
        return result
