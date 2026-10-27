"""Bank-port and link reservations for a sliced shared SRAM.

No global fabric mutex. This is a finite-buffer event/TLM model, not BookSim
or placed routing. It preserves the original word/bank mapping and energy.
"""
import math
from collections import Counter
from architecture_tlm.unified_v6.core import SRAM,ceildiv


class ClusteredSRAM(SRAM):
    def __init__(self,cfg,spec,scheduler,ledger):
        super().__init__(cfg,spec,scheduler,ledger)
        self.opt=cfg['sliced'];self.clusters=int(self.opt.get('clusters',4))
        self.mode=self.opt.get('mode','beats');self.credits=int(self.opt.get('credits',2))
        if self.mode not in ('descriptor','beats') or self.clusters<1 or cfg['banks']%self.clusters or self.credits<1:
            raise ValueError('invalid SRAM slice geometry')
        self.bpc=cfg['banks']//self.clusters
        self.bw=float(self.opt.get('cluster_GBs',cfg['fabric_GBs']/self.clusters))
        self.net_period=float(self.opt.get('network_period_ns',2.))
        self.quantum=min(self.bpc,int(self.opt.get('quantum_words',self.bpc)))
        self.endpoint_bw=float(self.opt.get('endpoint_GBs',self.bw))
        if min(self.bw,self.endpoint_bw,self.net_period,self.quantum)<=0 or self.bw*self.clusters>cfg['fabric_GBs']+1e-9:
            raise ValueError('slice links exceed the original aggregate bandwidth')
        if self.mode=='beats' and not hasattr(scheduler,'calendar'):
            raise ValueError('beat model requires an interval scheduler')
        self.stats=Counter();self.link_bytes=Counter();self.bank_ops=Counter()

    def _earliest(self,ready,duration,resources,period=0.):
        t=max(ready,self.s.floor)
        if period:t=math.ceil(t/period-1e-10)*period
        while True:
            old=t
            for r in resources:t=self.s._fit(r,t,duration,period)
            if t<=old+1e-8:return t

    def _plan(self,ready,cl,banks,endpoint,size,write,access):
        dur=math.ceil(max(size/self.bw,size/self.endpoint_bw)/self.net_period-1e-10)*self.net_period
        br=['sram_bank:'+str(b) for b in banks]
        lr=['sram_link:'+str(cl),'sram_port:'+endpoint+':'+str(cl)]
        candidates=[]
        for slot in range(self.credits):
            buf='sram_payload_buffer:'+str(cl)+':'+str(slot);probe=ready
            while True:
                if write:
                    ls=self._earliest(probe,dur,lr,self.net_period)
                    bs=self._earliest(ls+dur,self.period,br,self.period)
                    first,last=ls,bs+self.period
                else:
                    bs=self._earliest(probe,self.period,br,self.period)
                    ls=self._earliest(bs+access,dur,lr,self.net_period)
                    first,last=bs,ls+dur
                free=self._earliest(first,last-first,[buf])
                if free<=first+1e-8:break
                probe=free
            candidates.append((last,first,slot,bs,ls,dur,br,lr,buf))
        return min(candidates,key=lambda x:(x[0],x[1],x[2]))

    def endpoint(self,tag,write):
        if tag.endswith('_fill') or tag in ('weight_fill','embedding','summary_fill'):
            return 'DMA'
        if tag.startswith('weight') or tag in ('matrix_activation','matrix_result'):
            return 'matrix'
        return 'vector'

    def _validate(self,address,size,tag):
        if size<0 or address<0 or address+size>self.capacity:
            raise ValueError('SRAM request outside configured capacity')
        if self.regions is not None and not any(r['address']<=address and address+size<=r['address']+r['bytes'] for r in self.regions.values()):
            raise ValueError('SRAM request crosses live tensor region: '+tag)

    def _account(self,size,nwords,write):
        kind='write' if write else 'read'
        self.traffic[kind+'_logical_bytes']+=size
        self.traffic[kind+'_physical_bytes']+=nwords*self.word
        self.traffic[kind+'_words']+=nwords
        self.e.action('sram_'+kind,nwords,'SRAM_internal',self.spec[kind+'_internal_pJ'])

    def transfer(self,ready,address,size,write,tag):
        if not size:return ready
        self._validate(address,size,tag)
        lo=address//self.word;hi=ceildiv(address+size,self.word);words=hi-lo
        access=self.spec['write_access_ns' if write else 'read_access_ns']
        endpoint=self.endpoint(tag,write);done=ready
        if self.mode=='descriptor':
            # First control removes only the global mutex; bank ownership stays
            # coarse. No payload credits are provisioned in this control.
            for cl in range(self.clusters):
                counts=[(hi+self.c['banks']-1-b)//self.c['banks']-(lo+self.c['banks']-1-b)//self.c['banks'] for b in range(cl*self.bpc,(cl+1)*self.bpc)]
                active=[cl*self.bpc+i for i,v in enumerate(counts) if v]
                if not active:continue
                n=sum(counts);dur=max((max(counts)-1)*self.period+access,n*self.word/self.bw)+self.c['cdc_ns']
                rs=['sram_bank:'+str(b) for b in active]+['sram_link:'+str(cl),'sram_port:'+endpoint+':'+str(cl)]
                t=self.s.reserve('sram_'+tag,ready,dur,rs,self.period,write=write,bytes=n*self.word,cluster=cl,descriptor_control=True)
                done=max(done,t);self.link_bytes[cl]+=n*self.word;self.stats['slice_descriptors']+=1
                for b,n in zip(range(cl*self.bpc,(cl+1)*self.bpc),counts):self.bank_ops[b]+=n
        else:
            # Every stripe is a single bank word per bank. Small requests use
            # only their actual banks. CDC is once per descriptor, not held on
            # a bank or global wire for its whole latency.
            for stripe in range(lo//self.c['banks'],(hi-1)//self.c['banks']+1):
                for cl in range(self.clusters):
                    left=max(lo,stripe*self.c['banks']+cl*self.bpc)
                    right=min(hi,stripe*self.c['banks']+(cl+1)*self.bpc)
                    for first in range(left,right,self.quantum):
                        last=min(right,first+self.quantum);banks=list(range(first%self.c['banks'],first%self.c['banks']+last-first))
                        n=last-first;size_word=n*self.word
                        consumed,start,slot,bs,ls,dur,bank_rs,link_rs,buf=self._plan(ready+self.c['cdc_ns']/2,cl,banks,endpoint,size_word,write,access)
                        if write:
                            wire_end=self.s.reserve('sram_link_write',ls,dur,link_rs,self.net_period,cluster=cl,endpoint=endpoint,bytes=size_word,tag=tag)
                            bank_end=self.s.reserve('sram_bank_write',bs,self.period,bank_rs,self.period,cluster=cl,words=n,tag=tag)
                            ready_out=bank_end-self.period+access
                        else:
                            bank_end=self.s.reserve('sram_bank_read',bs,self.period,bank_rs,self.period,cluster=cl,words=n,tag=tag)
                            data_ready=bank_end-self.period+access
                            wire_end=self.s.reserve('sram_link_read',ls,dur,link_rs,self.net_period,cluster=cl,endpoint=endpoint,bytes=size_word,tag=tag)
                            ready_out=wire_end
                        self.s.reserve('sram_payload_credit',start,consumed-start,[buf],0.,cluster=cl,capacity_bytes=self.quantum*self.word,bytes=size_word,tag=tag)
                        done=max(done,ready_out+self.c['cdc_ns']/2)
                        self.link_bytes[cl]+=size_word
                        for b in banks:self.bank_ops[b]+=1
                        self.stats['bank_word_transactions']+=n;self.stats['payload_quanta']+=1
        self._account(size,words,write);self.stats['logical_descriptors']+=1
        return done

    def serial_histogram(self,ready,base,indices,core_period):
        t=ready
        for i in indices:
            t=self.transfer(t,base+i*4,4,False,'histogram_RMW_read')
            t=self.s.reserve('histogram_increment',t,core_period,['vector'],core_period)
            t=self.transfer(t,base+i*4,4,True,'histogram_RMW_write')
        self.e.action('vector_op',len(indices),'digital')
        return t

    def report(self,end_ns):
        r=super().report(end_ns)
        r.update(scheduling='sliced bank ports plus per-cluster shared read/write links',
            sliced=dict(mode=self.mode,clusters=self.clusters,banks_per_cluster=self.bpc,bank_word_bytes=self.word,
                bank_period_ns=self.period,cluster_link_GBs=self.bw,aggregate_link_GBs=self.bw*self.clusters,
                endpoint_GBs=self.endpoint_bw,network_period_ns=self.net_period,quantum_words=self.quantum,
                credits_per_cluster=self.credits if self.mode=='beats' else 0,
                additional_payload_buffer_bytes=self.clusters*self.credits*self.quantum*self.word if self.mode=='beats' else 0,
                shared_SRAM_capacity_unchanged=True,stats=dict(self.stats),link_bytes=dict(self.link_bytes),
                per_bank_word_operations=dict(self.bank_ops),
                buffer_PPA='additional finite link buffers; not yet circuit priced',
                routing='same striped addresses, bank//banks_per_cluster selects SRAM slice; no actual multicast or BookSim',
                arbitration='earliest legal statically reserved beats in interval calendars'))
        return r
