"""Pinned batch actor, with explicit GU16/Wd32 and unified 4ns service.
32 programming slots, two results/core and two state ports are retained.
The parent delay API accepts legacy 10ns cycle encodings, not physical ns.
"""
from collections import Counter,deque
from architecture_tlm.unified_v6.shared_memory import Signal,align_time

def common_stage(self,layer,mode):
    tiles,outs,blocks=self._tiles(mode);tasks=deque(enumerate(tiles));n=len(tiles)
    h=self.h;ready={};retire=deque();expected=[0]*outs;occupied=set();credits=[0]*self.common_cores
    state_slots=min(self.output_batch,outs) if mode=='GU' else outs
    owners=[None]*state_slots
    def state_slot(out):return out%state_slots
    input_key=[None]*self.common_cores;completed=[0];changed=[Signal()];stats=Counter();ports=self.state_port_free
    started=h.now;coverage=set();previous_commit=[-1]*outs
    def notify():
        prior=changed[0];changed[0]=Signal();prior.set()
    def loader(slot):
        while tasks:
            ix,(out,k)=tasks.popleft();key=(layer,slot,out,k)
            if mode=='GU' and key in self.common_prefetched:
                self.common_prefetched.remove(key);stats['prefetch_hits']+=1
            else:
                yield from self.load('common_'+str(slot),self._weight_spans(layer,mode,out,k),slot//16,(slot%16)*8192,'GU_weights' if mode=='GU' else 'down_weights')
            if mode=='GU':
                yield from h.transfer(self.vector,65536+(out*blocks+k)*2,2,False,'GU_weight_scale_metadata')
            else:
                base=65536+2*(self.model['ffn']//64)*(self.model['hidden']//64)
                for plane in range(2):
                    yield from h.transfer(self.vector,base+(2*out+plane)*blocks+k,1,False,'Wd_weight_scale_metadata')
            free=Signal();ready[slot]=(ix,out,k,free);stats['peak_resident_ready_tiles']=max(stats['peak_resident_ready_tiles'],len(ready));notify()
            yield free
    def worker(core):
        while completed[0]<n:
            eligible=[(row[0],slot,row) for slot,row in ready.items() if row[2]==expected[row[1]] and row[1] not in occupied and owners[state_slot(row[1])] in (None,row[1]) ]
            if credits[core]>=2 or not eligible:
                why='drain' if stats['dispatched_frames']==n else 'result_credit' if credits[core]>=2 else 'state_dependency' if ready else 'weight_ready'
                t=h.now;yield changed[0];stats['wait_'+why+'_core_ns']+=h.now-t;continue
            _,slot,(ix,out,k,free)=min(eligible,key=lambda item:((input_key[core]!=item[2][2]) if mode=='GU' else False,item[0]));del ready[slot];occupied.add(out)
            cell=state_slot(out)
            if owners[cell] is None:
                assert k==0
                owners[cell]=out
                stats['peak_owned_state_groups']=max(stats['peak_owned_state_groups'],sum(v is not None for v in owners))
            assert owners[cell]==out
            stats['dispatched_frames']+=1
            credits[core]+=1;stats['peak_core_reserved_results']=max(stats['peak_core_reserved_results'],credits[core]);notify()
            if input_key[core]!=k:
                offset,size=(k*80,80) if mode=='GU' else (8192+k*128,128)
                t=h.now;yield from h.transfer(self.vector,offset,size,False,'GU_x_codes' if mode=='GU' else 'NL_gu_codes')
                if mode=='Wd':yield from h.transfer(self.vector,65536+20000+k,1,False,'NL_gu_scale')
                stats['input_load_core_ns']+=h.now-t;stats['input_cache_loads']+=1;input_key[core]=k
            samples=16 if mode=='GU' else 32
            yield from self.delay((samples+2)*10,'common_'+mode+'_core')
            stats['sample_core_ns']+=(samples+2)*4;stats['sample_frames']+=1
            self.kernel_active['GU_frames' if mode=='GU' else 'Wd_M128_frames']+=1
            self.actions['GU_logical_R8_ports' if mode=='GU' else 'NL_logical_R8_ports']+=64*samples*(1 if mode=='GU' else 3)
            self.actions['common_R8_words']+=samples*(1 if mode=='GU' else 3)
            self.actions['SC_equivalent_MAC']+=8192
            assert ix not in coverage;coverage.add(ix)
            retire.append((core,out,k));stats['peak_captured_results']=max(stats['peak_captured_results'],len(retire));free.set();notify()
    def state_worker(port):
        while completed[0]<n:
            if not retire:yield changed[0];continue
            core,out,k=retire.popleft();offset=state_slot(out)*1024
            assert owners[state_slot(out)]==out
            assert previous_commit[out]==k-1
            if k:
                yield from h.transfer(self.common_state,offset,1024,False,'common_'+mode+'_state_read')
            begin=max(align_time(h.now,4),ports[port]);ports[port]=begin+16
            if begin>h.now:yield from h.delay(begin-h.now)
            yield from self.delay(40,'common_state32_port')
            self.actions['common_state32_vectors']+=4;self.actions['crossK_updates']+=128
            if k+1<blocks:
                yield from h.transfer(self.common_state,offset,1024,True,'common_'+mode+'_state_write')
            else:
                yield from self.delay(10,'GU_fixed8_quant_macro' if mode=='GU' else 'final_BF16_macro')
                if mode=='GU':
                    yield from h.transfer(self.vector,8192+out*128,128,True,'GU_quantized_output')
                    yield from h.transfer(self.vector,65536+20000+out,1,True,'GU_scale_output')
                else:yield from h.transfer(self.vector,out*256,256,True,'FFN_BF16_output')
            previous_commit[out]=k;expected[out]=k+1;occupied.remove(out)
            if k+1==blocks:owners[state_slot(out)]=None
            credits[core]-=1;completed[0]+=1;notify()
    yield from self._parallel([loader(i) for i in range(min(32,n))]+[worker(i) for i in range(self.common_cores)]+[state_worker(i) for i in range(self.state_ports)])
    assert len(coverage)==completed[0]==n and not ready and not retire and not occupied and not any(credits)
    assert all(k==blocks for k in expected) and not self.common_prefetched and all(v is None for v in owners)
    elapsed=h.now-started
    row=dict(layer=layer,mode=mode,state_slots=state_slots,state_capacity_bytes=self.common_state.size,output_batch=self.output_batch,frames=n,output_groups=outs,Kblocks=blocks,physical_common_cores=self.common_cores,elapsed_ns=elapsed,
        core_sampling_utilization=stats['sample_core_ns']/(self.common_cores*elapsed),**dict(stats))
    self.common_stats.append(row)
