"""Instrument the installed Qwen3 graph, preserving its operation order."""
import ast
from collections import defaultdict
import functools
import inspect
import textwrap
import types

import torch
from transformers.cache_utils import DynamicCache
from transformers.models.qwen3 import modeling_qwen3 as q3


class Rewrite(ast.NodeTransformer):
    def __init__(self,op,category):self.op=op;self.category=category;self.count=0
    def visit_BinOp(self,node):
        self.generic_visit(node)
        if isinstance(node.op,self.op):
            self.count+=1
            function='add' if self.op is ast.Add else 'mul'
            return ast.copy_location(ast.Call(func=ast.Name(id='_gpu212_call',ctx=ast.Load()),
                args=[ast.Constant(value=self.category),ast.Constant(value=function),
                    ast.Attribute(value=ast.Name(id='torch',ctx=ast.Load()),attr=function,ctx=ast.Load()),
                    node.left,node.right],keywords=[]),node)
        return node


class Instrument:
    def __init__(self,model,capture=False,annotations=False):
        self.model=model;self.capture=capture;self.annotations=annotations
        self.calls=defaultdict(list);self.restores=[]
        self.source={}

    def call(self,category,name,fn,*args,**kwargs):
        if self.capture:self.calls[category].append((name,fn,args,kwargs))
        if self.annotations:
            with torch.profiler.record_function('gpu212::'+category):return fn(*args,**kwargs)
        return fn(*args,**kwargs)

    def wrap(self,obj,attribute,category,name):
        old=getattr(obj,attribute)
        @functools.wraps(old)
        def wrapped(*args,**kwargs):return self.call(category,name,old,*args,**kwargs)
        setattr(obj,attribute,wrapped)
        self.restores.append(lambda o=obj,a=attribute,f=old:setattr(o,a,f))

    def rewrite(self,module,op,category,expected):
        old=module.forward
        source=textwrap.dedent(inspect.getsource(type(module).forward))
        self.source[type(module).__name__]=source
        tree=ast.parse(source)
        for n in tree.body:
            if isinstance(n,ast.FunctionDef):n.decorator_list=[]
        transform=Rewrite(op,category);tree=transform.visit(tree);ast.fix_missing_locations(tree)
        if transform.count!=expected:raise RuntimeError('installed Qwen3 operation pattern changed')
        namespace=dict(old.__func__.__globals__);namespace['_gpu212_call']=self.call
        exec(compile(tree,'<gpu212-installed-forward>','exec'),namespace)
        module.forward=types.MethodType(namespace['forward'],module)
        self.restores.append(lambda m=module,f=old:setattr(m,'forward',f))

    def __enter__(self):
        try:
            self.wrap(self.model.model.embed_tokens,'forward','Embedding','embedding')
            self.wrap(self.model.model.rotary_emb,'forward','RoPE','rotary_setup')
            self.wrap(q3,'apply_rotary_pos_emb','RoPE','rotary_apply')
            for i,layer in enumerate(self.model.model.layers):
                self.rewrite(layer,ast.Add,'Residual_add',2)
                self.rewrite(layer.mlp,ast.Mult,'FFN_SwiGLU',1)
                for name in ['q_proj','k_proj','v_proj']:
                    self.wrap(getattr(layer.self_attn,name),'forward','QKV_projection',str(i)+'.'+name)
                for name in ['q_norm','k_norm']:
                    self.wrap(getattr(layer.self_attn,name),'forward','QK_RMSNorm',str(i)+'.'+name)
                self.wrap(layer.self_attn.o_proj,'forward','Wo_projection',str(i)+'.o_proj')
                for name in ['gate_proj','up_proj']:
                    self.wrap(getattr(layer.mlp,name),'forward','FFN_gate_up',str(i)+'.'+name)
                self.wrap(layer.mlp.act_fn,'forward','FFN_SwiGLU',str(i)+'.silu')
                self.wrap(layer.mlp.down_proj,'forward','FFN_down',str(i)+'.down_proj')
                for name in ['input_layernorm','post_attention_layernorm']:
                    self.wrap(getattr(layer,name),'forward','Layer_RMSNorm',str(i)+'.'+name)
            self.wrap(self.model.model.norm,'forward','Final_RMSNorm','final_norm')
            self.wrap(self.model.lm_head,'forward','lm_head','lm_head')

            registry=q3.ALL_ATTENTION_FUNCTIONS
            old=registry['sdpa']
            def attention(*args,**kwargs):return self.call('Attention_core','sdpa_helper',old,*args,**kwargs)
            if isinstance(registry,dict):
                registry['sdpa']=attention
                self.restores.append(lambda:registry.__setitem__('sdpa',old))
            else:
                registry.register('sdpa',attention)
                self.restores.append(lambda:registry.register('sdpa',old))

            old_update=DynamicCache.update
            def update(cache,key,value,layer_idx,cache_kwargs=None):
                # from_legacy_cache initializes by calling update; this performs
                # no append computation and is not a decode-layer occurrence.
                if layer_idx>=len(cache.key_cache) or not isinstance(cache.key_cache[layer_idx],torch.Tensor):
                    return old_update(cache,key,value,layer_idx,cache_kwargs)
                previous=(cache.key_cache[layer_idx],cache.value_cache[layer_idx])
                if self.capture:
                    def append(k0,v0,k1,v1):return torch.cat((k0,k1),dim=-2),torch.cat((v0,v1),dim=-2)
                    self.calls['KV_append'].append((str(layer_idx)+'.cache_update',append,(*previous,key,value),{}))
                if self.annotations:
                    with torch.profiler.record_function('gpu212::KV_append'):
                        return old_update(cache,key,value,layer_idx,cache_kwargs)
                return old_update(cache,key,value,layer_idx,cache_kwargs)
            DynamicCache.update=update
            self.restores.append(lambda:setattr(DynamicCache,'update',old_update))
            return self
        except Exception:
            self.__exit__(None,None,None)
            raise

    def __exit__(self,*args):
        for restore in reversed(self.restores):restore()
        self.restores=[]

    def replay(self,category):
        for name,fn,args,kwargs in self.calls[category]:result=fn(*args,**kwargs)

    def inventory(self):
        out={}
        for category,calls in self.calls.items():
            weights={}
            shapes=[]
            for name,fn,args,kwargs in calls:
                owner=getattr(fn,'__self__',None)
                if isinstance(owner,torch.nn.Module):
                    for p in owner.parameters(recurse=False):weights[p.data_ptr()]=p.numel()*p.element_size()
                shapes.append({'name':name,'tensor_shapes':[list(a.shape) for a in args if isinstance(a,torch.Tensor)]})
            out[category]={'calls_per_decode':len(calls),'weight_working_set_bytes':sum(weights.values()),'calls':shapes}
        return out
