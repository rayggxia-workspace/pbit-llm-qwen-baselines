"""Dynamic decoder frontend: register each memory writer before its readers."""
import math

from .contracts import Operation
from .memory import MemoryRequest
from . import attention, ffn


def build_flow(k,state,data,c,fc,ac,addresses,matrix_addresses,initial,x,state_bytes):
    from .layer import pack,unpack,norm,linear,rope,_RuntimeInitializer
    d=len(x)
    def add(name,resource,**kwargs):
        kwargs.setdefault('cdc_cycles',c.cdc_cycles)
        k.add(Operation('layer.'+name,resource,**kwargs))
        return 'layer.'+name
    def read(name,address,size,dependency,port='sram'):
        return add(name,port,deps=(dependency,),memory=MemoryRequest(address,size),
                   inputs={'layer.local':size},actions={'layer_read_bytes':size})
    def write(name,vector,dependency,callback):
        state['vectors'][name]=vector
        return add(name+'.write','sram',deps=(dependency,),memory=MemoryRequest(addresses[name],d*4,True,pack(vector)),
                   actions={'layer_write_bytes':d*4},on_complete=lambda kernel,op:callback(op.id))

    def start_ffn(dependency):
        fr=read('ffn.input',addresses['norm2'],d*4,dependency)
        rr=read('ffn.residual',addresses['residual'],d*4,dependency)
        def ready(kernel,op):
            mlp={name:data[name] for name in ('wg','wu','wd')}
            mlp.update(x=unpack(kernel.memory_reads[fr]),residual=unpack(kernel.memory_reads[rr]))
            state['ffn_fixture']=mlp
            state['ffn']=ffn.build_ffn(_RuntimeInitializer(kernel,initial,'layer.ffn',op.id,c.cdc_cycles),mlp,fc)
            # A control dependency may name a future dynamic output. Do not
            # register a memory reader before the producer's writer exists.
            def done(kernel,op):
                import struct
                raw=kernel.read_memory('sram',state['ffn']['output_address'],state['ffn']['output_bytes'])
                output=([struct.unpack('<f',b'\x00\x00'+raw[i:i+2])[0] for i in range(0,len(raw),2)]
                        if fc.output_bf16 else unpack(raw))
                if output!=state['ffn']['output']: raise AssertionError('layer output bytes mismatch')
                state.update(output=output,output_bytes=raw,complete_ps=kernel.now_ps)
            add('complete','control',deps=('ffn.output.write',),on_complete=done,outputs={'layer.state':state_bytes})
        add('ffn_start','control',deps=(fr,rr),on_complete=ready,outputs={'layer.local':d*8})

    def norm2(dependency):
        nr=read('norm2.input',addresses['residual'],d*4,dependency)
        gr=read('norm2.gamma',addresses['gamma2'],d*4,dependency)
        def done(kernel,op):
            write('norm2',norm(unpack(kernel.memory_reads[nr]),unpack(kernel.memory_reads[gr]),c.epsilon),op.id,start_ffn)
        add('norm2','vector',deps=(nr,gr),latency_cycles=5+math.ceil(d/16),on_complete=done,
            outputs={'layer.local':d*8},actions={'rmsnorm_values':d})

    def residual(dependency):
        wr=read('residual.wo',addresses['wo'],d*4,dependency)
        rr=read('residual.x',addresses['x'],d*4,dependency)
        def done(kernel,op):
            value=[ffn.fp32(a+b) for a,b in zip(unpack(kernel.memory_reads[wr]),unpack(kernel.memory_reads[rr]))]
            write('residual',value,op.id,norm2)
        add('residual','vector',deps=(wr,rr),on_complete=done,
            outputs={'layer.local':d*8},actions={'residual_add':d})

    def wo(dependency):
        ar=read('wo.input',0x74000000,d*4,dependency)
        wr=read('wo.weights',matrix_addresses['wo'],d*d*4,dependency,'dram')
        def done(kernel,op):
            flat=unpack(kernel.memory_reads[wr])
            write('wo',linear(unpack(kernel.memory_reads[ar]),[flat[i*d:(i+1)*d] for i in range(d)]),op.id,residual)
        add('wo.project','digital_matrix',deps=(ar,wr),latency_cycles=3+math.ceil(d*d/c.digital_mac_lanes)-1,
            on_complete=done,outputs={'layer.local':(d*d+d)*4},actions={'digital_mac':d*d})

    def start_attention(dependency):
        reads={name:read(name+'.attention_input',addresses[name],d*4,dependency) for name in ('qrope','krope','v')}
        def ready(kernel,op):
            qv,kv,vv=[unpack(kernel.memory_reads[reads[n]]) for n in ('qrope','krope','v')]
            query={'q':qv,'k':data['past_k']+[kv],'v':data['past_v']+[vv],
                   'candidate_ids':list(range(len(data['past_k'])+1))}
            state['query_fixture']=query
            state['attention']=attention.build_attention(_RuntimeInitializer(kernel,initial,'layer.attention',op.id,c.cdc_cycles),query,ac)
            add('attention_ready','control',deps=('attention.output.write',),on_complete=lambda kernel,op:wo(op.id))
        add('attention_start','control',deps=tuple(reads.values()),on_complete=ready,
            outputs={'layer.local':d*12},actions={'kv_append_values':2*d,'all_candidate_indices':len(data['past_k'])+1})

    def apply_rope(dependency):
        qr=read('q.rope_read',addresses['q'],d*4,dependency)
        kr=read('k.rope_read',addresses['k'],d*4,dependency)
        def done(kernel,op):
            q=rope(unpack(kernel.memory_reads[qr]),len(data['past_k']),c.rope_theta)
            key=rope(unpack(kernel.memory_reads[kr]),len(data['past_k']),c.rope_theta)
            write('qrope',q,op.id,lambda dep:write('krope',key,dep,start_attention))
        add('rope','vector',deps=(qr,kr),latency_cycles=4+math.ceil(d/16),on_complete=done,
            outputs={'layer.local':d*8},actions={'rope_values':2*d})

    def projection(index,dependency):
        # Conservative serial Q/K/V: no unproven weight prefetch or overlap.
        if index==3:
            apply_rope(dependency)
            return
        name=('q','k','v')[index]
        ir=read(name+'.input',addresses['norm1'],d*4,dependency)
        wr=read(name+'.weights',matrix_addresses['w'+name],d*d*4,dependency,'dram')
        def done(kernel,op):
            flat=unpack(kernel.memory_reads[wr])
            value=linear(unpack(kernel.memory_reads[ir]),[flat[i*d:(i+1)*d] for i in range(d)])
            write(name,value,op.id,lambda dep:projection(index+1,dep))
        add(name+'.project','digital_matrix',deps=(ir,wr),latency_cycles=3+math.ceil(d*d/c.digital_mac_lanes)-1,
            on_complete=done,outputs={'layer.local':(d*d+d)*4},actions={'digital_mac':d*d})

    reserve=add('reserve','control',inputs={'layer.state':state_bytes})
    xr=read('x.read',addresses['x'],d*4,reserve)
    gr=read('gamma1.read',addresses['gamma1'],d*4,reserve)
    def normalized(kernel,op):
        value=norm(unpack(kernel.memory_reads[xr]),unpack(kernel.memory_reads[gr]),c.epsilon)
        write('norm1',value,op.id,lambda dep:projection(0,dep))
    add('norm1','vector',deps=(xr,gr),latency_cycles=5+math.ceil(d/16),on_complete=normalized,
        outputs={'layer.local':d*8},actions={'rmsnorm_values':d})
    return k,state
