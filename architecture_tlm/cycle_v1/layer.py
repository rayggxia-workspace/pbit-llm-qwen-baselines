"""Reduced single-head decoder block in ONE online execution kernel.

RMSNorm -> QKV -> RoPE -> KV append -> all-candidate Attention -> Wo ->
residual -> RMSNorm -> stochastic FFN -> residual. This is a reduced synthetic
architecture closure test, not a Qwen/Llama full layer or quality result.
The first implementation intentionally uses an all-candidate digital baseline,
no learned/summarized screening and no multihead/GQA sharing claim.
"""
from dataclasses import dataclass, asdict
import math
import struct

from . import attention, ffn
from .contracts import Clock, Resource, Buffer, Operation
from .kernel import Kernel
from .memory import MemoryPort, MemoryRequest


def pack(values):
    return struct.pack('<'+'f'*len(values), *values)


def unpack(data):
    return list(struct.unpack('<'+'f'*(len(data)//4), data))


def norm(values, gamma, epsilon):
    scale = ffn.fp32(1/math.sqrt(math.fsum(x*x for x in values)/len(values)+epsilon))
    return [ffn.fp32(ffn.fp32(x*scale)*g) for x,g in zip(values,gamma)]


def linear(values, weights):
    return [ffn.fp32(math.fsum(x*w for x,w in zip(values,row))) for row in weights]


def rope(values, position, theta):
    half = len(values)//2
    result = [0.]*len(values)
    for i in range(half):
        angle = position/(theta**(2*i/len(values)))
        cosine, sine = ffn.fp32(math.cos(angle)), ffn.fp32(math.sin(angle))
        result[i] = ffn.fp32(ffn.fp32(values[i]*cosine)-ffn.fp32(values[i+half]*sine))
        result[i+half] = ffn.fp32(ffn.fp32(values[i+half]*cosine)+ffn.fp32(values[i]*sine))
    return result


@dataclass(frozen=True)
class LayerConfig:
    epsilon: float = 1e-6
    rope_theta: float = 10000.
    local_bytes: int = 8192
    working_bytes: int = 4096
    digital_mac_lanes: int = 64
    cdc_cycles: int = 3


def synthetic_layer():
    d, mid, context = 16, 70, 9
    matrix = lambda rows,cols,p: [[math.sin(i*.17+j*.31+p)*.12 for j in range(cols)] for i in range(rows)]
    return dict(provenance={'kind':'reduced_synthetic_decoder','hidden':d,'heads':1,'intermediate':mid,
                            'past_tokens':context,'not_a_qwen_layer':True},
        x=[math.cos(i*.27)*.3 for i in range(d)],
        norm1=[1.+math.sin(i)*.01 for i in range(d)],norm2=[1.-math.cos(i)*.01 for i in range(d)],
        wq=matrix(d,d,.1),wk=matrix(d,d,.4),wv=matrix(d,d,.8),wo=matrix(d,d,1.1),
        past_k=matrix(context,d,.2),past_v=matrix(context,d,.7),
        wg=matrix(mid,d,1.7),wu=matrix(mid,d,2.1),wd=matrix(d,mid,2.7))


class _RuntimeInitializer:
    """Convert dynamic builder initialization into timed writes, never teleport.

    Immutable initial weights/cache are preloaded before execution. Every new
    activation, appended KV value and zeroed histogram is a real online memory
    write. Kernel's RAW scoreboard orders subsequent reads behind those writes.
    """
    def __init__(self,kernel,initial,prefix):
        self.kernel,self.initial,self.prefix=kernel,initial,prefix
        self.serial=0

    def __getattr__(self,name):
        return getattr(self.kernel,name)

    def load_memory(self,port,address,data):
        if (port,address) in self.initial:
            if self.initial[port,address] != data:
                raise AssertionError(f'dynamic builder changed initial payload at {port}/{address:#x}: {len(self.initial[port,address])} versus {len(data)} bytes')
            return
        self.serial+=1
        self.kernel.add(Operation(f'{self.prefix}.initialize.{self.serial}',port,
            memory=MemoryRequest(address,len(data),write=True,data=data),
            actions={'boundary_write_bytes':len(data)},
            metadata={'kind':'online producer-to-consumer initialization','payload_bytes':len(data)}))


def make_layer(fixture=None,layer_config=None,ffn_config=None,attention_config=None,memory_latency=4):
    data=fixture or synthetic_layer()
    c=layer_config or LayerConfig()
    fc=ffn_config or ffn.FFNConfig()
    ac=attention_config or attention.AttentionConfig()
    fc.validate(); ac.validate()
    if c.epsilon<=0 or c.rope_theta<=0 or min(c.local_bytes,c.working_bytes,c.digital_mac_lanes)<1:
        raise ValueError('invalid layer configuration')
    x=[ffn.fp32(v) for v in data['x']]
    d=len(x)
    if d<2 or d%2 or any(len(data[n])!=d for n in ('norm1','norm2')):
        raise ValueError('even hidden size and matching normalization scales required')
    for name in ('wq','wk','wv','wo'):
        if len(data[name])!=d or any(len(row)!=d for row in data[name]):
            raise ValueError('this reduced single-head closure requires square QKVO matrices')
    if len(data['past_k'])!=len(data['past_v']) or any(len(row)!=d for row in data['past_k']+data['past_v']):
        raise ValueError('matching single-head past KV required')
    if len(data['wd'])!=d:
        raise ValueError('FFN output must return hidden width')
    state_bytes=12*d*4
    if state_bytes>c.working_bytes:
        raise ValueError('layer live vector state exceeds finite working storage')
    resources={r.name:r for r in ffn.default_resources(fc)}
    for resource in attention.default_resources(ac):
        if resource.name not in resources:
            resources[resource.name]=resource
    # Sharing is explicit: one digital matrix unit and one vector pipeline.
    resources['digital_matrix']=Resource('digital_matrix',Clock('core',10000),3,capacity=4)
    resources['vector']=Resource('vector',Clock('core',10000),3,capacity=4)
    buffers=ffn.default_buffers(fc)+attention.default_buffers(ac)+[
        Buffer('layer.local',c.local_bytes,c.local_bytes,'byte credit'),
        Buffer('layer.state',c.working_bytes,c.working_bytes,'byte credit')]
    k=Kernel(resources.values(),buffers,memory_ports=[
        MemoryPort('dram',Clock('dram',12500),latency_cycles=memory_latency,window=4,strict_reads=True),
        MemoryPort('sram',Clock('sram',12500),latency_cycles=2,window=4,strict_reads=True)])
    initial={}
    def preload(port,address,payload):
        k.load_memory(port,address,payload)
        initial[port,address]=payload
    matrix_addresses={name:0x80000000+i*0x100000 for i,name in enumerate(('wq','wk','wv','wo'))}
    for name,address in matrix_addresses.items():
        preload('dram',address,pack([v for row in data[name] for v in row]))
    # Identical immutable tile packing to the standalone FFN frontend.
    for name,base in (('wg',0x10000000),('wu',0x20000000),('wd',0x30000000)):
        mat=ffn.matrix_spec(data[name])
        for r in range(0,mat['rows'],64):
            for start in range(0,mat['cols'],64):
                codes=[v for row in mat['codes'][r:r+64] for v in row[start:start+64]]
                payload=struct.pack('<'+'b'*len(codes),*codes)
                address=base+(r//64*math.ceil(mat['cols']/64)+start//64)*4160
                preload('dram',address,payload)
                preload('dram',address+4096,pack([mat['scales'][r//64][start//64]]))
    for physical,row in enumerate(data['past_k']): preload('dram',0x71000000+physical*d*4,pack(row))
    for physical,row in enumerate(data['past_v']): preload('dram',0x72000000+physical*d*4,pack(row))
    addresses={name:0x90000000+i*0x10000 for i,name in enumerate(
        ('x','gamma1','gamma2','norm1','q','k','v','qrope','krope','wo','residual','norm2'))}
    preload('sram',addresses['x'],pack(x))
    preload('sram',addresses['gamma1'],pack(data['norm1']))
    preload('sram',addresses['gamma2'],pack(data['norm2']))
    state={'output':None,'vectors':{},'attention':None,'ffn':None,
           'provenance':{**data.get('provenance',{}),'scope':'reduced single-head decoder in one online kernel',
               'selection':'all candidates; no screening or GQA',
               'arithmetic':'FP32 boundaries with double fsum reference digital kernels; not bit-true full RTL',
               'timing':'uncharacterized configured contracts','global_memory_capacity':'not allocated'},
           'configs':{'layer':asdict(c),'ffn':asdict(fc),'attention':asdict(ac)}}
    from .layer_flow import build_flow
    return build_flow(k,state,data,c,fc,ac,addresses,matrix_addresses,initial,x,state_bytes)
