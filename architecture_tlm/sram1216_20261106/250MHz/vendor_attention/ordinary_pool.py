"""Isolated ordinary-pool frequency experiment. SRAM service is250MHz in this isolated variant.
Derived from pinned ordinary_mapping_20261106; unified on-chip clock overlay applied before execution.
"""
import math
from types import MethodType

def install(model, lanes=320, k_parallel=4, early_refill=True, period_ns=4):
    from architecture_tlm.unified_v6.shared_memory import Signal,align_time
    from architecture_tlm.unified_v6.shared_decode import spans_tile
    if model.ffn_mode != 'sc' or lanes not in (128,192,256,320,384,448,512,640):
        raise ValueError('SC host only; digital Wd resources require separate accounting')
    if model.h.now:raise ValueError('install before first prefetch')
    if k_parallel not in (4,8) or lanes % k_parallel:
        raise ValueError("unsupported geometry")
    assert period_ns in (4,10) and (lanes//k_parallel)%16==0
    output_tile=lanes//k_parallel*4
    k_tile=k_parallel*16
    model.mac_lanes=lanes
    model.ordinary_pool_audit=[]
    model.ordinary_pool_contract=dict(lanes=lanes,K_parallel=k_parallel,contexts=4,compute_period_ns=period_ns,SRAM_period_ns=4,
        output_tile=output_tile,K_tile=k_tile,early_refill=early_refill,
        FMA16_broadcast_compatible=(lanes//k_parallel)%16==0,
        numeric_reduction_order_changed=k_parallel!=64,weight_slots=2,
        weight_slot_capacity_bytes=model.weight[0].size,FP32_reduction_adders=128,
        independent_QK_lanes=512,QK_reuse_implemented=False,
        status='candidate_not_global_default',new_PPA=False)
    model.digital_contract.update(ordinary_FMA_lanes=lanes,
        ordinary_output_tile=output_tile,
        K_parallel_lanes_per_output=k_parallel)
    previous_tasks=model.matrix_tasks
    previous_matrix=model.digital_matrix
    def tasks(self,layer,name,outputs,inputs,element=2):
        if name not in ('QKV','O','lm_head'):
            return previous_tasks(layer,name,outputs,inputs,element)
        if element!=2:raise ValueError('BF16 ordinary projection only')
        base=self.lm_base if name=='lm_head' else self.weight_bases[layer,name]
        out=[];tile=output_tile
        for o in range(0,outputs,tile):
            no=min(tile,outputs-o)
            for k in range(0,inputs,k_tile):
                nk=min(k_tile,inputs-k)
                spans=spans_tile(base,o,no,k,inputs,nk,element,self.weight_layout)
                out.append((spans,no*nk,o,no,k+nk==inputs))
        return out
    def matrix(self,layer,name,outputs,inputs,element=2):
        if name not in ('QKV','O','lm_head'):
            yield from previous_matrix(layer,name,outputs,inputs,element);return
        begin=self.h.now;items=self.matrix_tasks(layer,name,outputs,inputs,element)
        ready={};loaders={}
        audit=dict(layer=layer,name=name,lanes=lanes,tasks=len(items),weight_bytes=0,
            MAC=0,input_init_ns=0.,weight_ready_wait_ns=0.,operand_service_ns=0.,
            arithmetic_tail_ns=0.,reduction_output_ns=0.,arithmetic_service_ns=0.,host_boundary_ns=0.)
        def compute_delay(ns,name=None):
            # Compute and memory callbacks use the same4ns edge grid.
            done=Signal();end=align_time(self.h.now,period_ns)+ns
            self.h.later(end,done.set)
            if name:self.compute[name]+=end-self.h.now
            yield done
        def load(ix,slot):
            if (layer,name,ix) in self.prefetched:
                self.prefetched.remove((layer,name,ix));self.actions['ordinary_prefetch_hits']+=1
            else:yield from self._load_matrix(layer,name,items[ix][0],slot)
            ready.setdefault(ix,Signal()).set()
        def driver():
            t=self.h.now
            yield from self.h.transfer(self.vector,0,inputs*2,False,name+'_activation_to_local')
            audit['input_init_ns']+=self.h.now-t
            for ix,(spans,work,out0,nout,last) in enumerate(items):
                slot=ix%2
                if ix==0:
                    for j in range(min(2,len(items))):loaders[j]=load(j,j)
                t=self.h.now;yield ready.setdefault(ix,Signal())
                audit['weight_ready_wait_ns']+=self.h.now-t
                start=self.h.now;nb=sum(n for _,n in spans)
                yield from self.h.transfer(self._pool(layer,name)[slot],0,nb,False,name+'_operand')
                waves=math.ceil(nout/(lanes//k_parallel));terms=math.ceil((work//nout)/k_parallel)
                assert 1<=waves<=4
                cycles=(terms-1)*4+waves+4
                audit['operand_service_ns']+=self.h.now-start
                audit['arithmetic_service_ns']+=cycles*period_ns
                arithmetic_start=align_time(start,period_ns)
                tail_begin=self.h.now
                tail=max(0,arithmetic_start+cycles*period_ns-self.h.now)
                if early_refill:
                    # Do not refill while a future FMA issue might still need
                    # this slot. Both SRAM reads AND nominal final issue must
                    # complete; the four pipeline-drain cycles need no weight.
                    before=max(0,arithmetic_start+(cycles-4)*period_ns-self.h.now)
                    if before:
                        done=Signal();self.h.later(self.h.now+before,done.set);yield done
                    if ix+2<len(items):loaders[ix+2]=load(ix+2,slot)
                    after=max(0,arithmetic_start+cycles*period_ns-self.h.now)
                    if after:
                        done=Signal();self.h.later(self.h.now+after,done.set);yield done
                elif tail:
                    done=Signal();self.h.later(self.h.now+tail,done.set);yield done
                audit['arithmetic_tail_ns']+=self.h.now-tail_begin
                self.actions['digital_BF16_MAC']+=work
                self.work_digest.update(('%s/%d/%d/%d/%d'%(name,layer,ix,work,nb)).encode())
                ready.pop(ix);audit['weight_bytes']+=nb;audit['MAC']+=work
                t=self.h.now
                if last:
                    self.actions['digital_FP32_reduce_ADD']+=nout*(k_parallel-1)
                    yield from compute_delay(self.reduction_cycles(nout,leaves=k_parallel)*period_ns,'digital_final_K_reduction')
                    if name=='lm_head':
                        yield from compute_delay(7*period_ns,'streaming_argmax_macro');self.actions['argmax_compares']+=nout
                    else:
                        yield from compute_delay(4*period_ns,'matrix_BF16_RNE')
                        yield from self.h.transfer(self.vector,out0*2,nout*2,True,name+'_output')
                audit['reduction_output_ns']+=self.h.now-t
                if not early_refill and ix+2<len(items):loaders[ix+2]=load(ix+2,slot)
            self.unpriced['digital_activation_hold_bytes_peak']=max(self.unpriced['digital_activation_hold_bytes_peak'],inputs*2)
        yield from self._managed(driver(),loaders)
        boundary=self.h.now
        if abs(self.h.now/period_ns-round(self.h.now/period_ns))>1e-7:
            yield from self.h.delay(0)
        audit['host_boundary_ns']=self.h.now-boundary
        audit['elapsed_ns']=self.h.now-begin
        subtotal=sum(audit[k] for k in ('input_init_ns','weight_ready_wait_ns','operand_service_ns','arithmetic_tail_ns','reduction_output_ns','host_boundary_ns'))
        if abs(subtotal-audit['elapsed_ns'])>1e-6:raise AssertionError(('exclusive time ledger',audit,subtotal))
        self.ordinary_pool_audit.append(audit)
    model.matrix_tasks=MethodType(tasks,model);model.digital_matrix=MethodType(matrix,model)
    parent=model.run
    def run(self):
        result=parent()
        result['executed_resources']['ordinary_MAC_lanes']=lanes
        result['ordinary_pool_contract']=dict(self.ordinary_pool_contract)
        result['ordinary_pool_audit']=list(self.ordinary_pool_audit)
        result['covered_area_requires_repricing']=True
        return result
    model.run=MethodType(run,model)
    return model
