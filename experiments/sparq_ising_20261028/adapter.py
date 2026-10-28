"""Native Qwen3 projections/cache; replace only post-RoPE single-query core."""
from dataclasses import asdict
import hashlib
from types import MethodType
import torch
from .core import attention


class Controller:
    def __init__(self,model,cfg=None,seed=0):
        if model.training or model.config.model_type != 'qwen3' or model.config._attn_implementation != 'sdpa':
            raise ValueError('eval native SDPA Qwen3 required')
        self.model,self.cfg,self.seed = model,cfg,seed
        self.prefix = False
        self.originals=[]
        self.state={}
        for i,layer in enumerate(model.model.layers):
            a=layer.self_attn
            if a.layer_idx!=i or a.sliding_window is not None or type(layer.mlp).__name__!='Qwen3MLP':
                raise ValueError('unsupported attention or modified FFN')
            self.originals.append((a,a.forward))
            self.state[i]=dict(decode_queries=0,prefill_queries=0,calls=0,zero_fallback=0,route_elements=0,selected_k_elements=0,sampled_head_rows=0)
            a.forward=MethodType(self.dispatch,a)

    def dispatch(self,a,hidden_states,position_embeddings,attention_mask=None,past_key_value=None,cache_position=None,**kwargs):
        b,length=hidden_states.shape[:2]
        state=self.state[a.layer_idx]
        if self.prefix or length!=1:
            state['prefill_queries']+=b*length
            return self.originals[a.layer_idx][1](hidden_states,position_embeddings,attention_mask,past_key_value=past_key_value,cache_position=cache_position,**kwargs)
        if attention_mask is not None or kwargs.get('output_attentions',False):
            raise ValueError('only unpadded/no-bias cached single queries supported')
        from transformers.models.qwen3.modeling_qwen3 import apply_rotary_pos_emb
        shape=(*hidden_states.shape[:-1],-1,a.head_dim)
        q=a.q_norm(a.q_proj(hidden_states).view(shape)).transpose(1,2)
        k=a.k_norm(a.k_proj(hidden_states).view(shape)).transpose(1,2)
        v=a.v_proj(hidden_states).view(shape).transpose(1,2)
        cos,sin=position_embeddings
        q,k=apply_rotary_pos_emb(q,k,cos,sin)
        if past_key_value is not None:
            k,v=past_key_value.update(k,v,a.layer_idx,{'cos':cos,'sin':sin,'cache_position':cache_position})
        state['decode_queries']+=b
        state['calls']+=1
        if self.cfg is None:
            from transformers.integrations.sdpa_attention import sdpa_attention_forward
            out,_=sdpa_attention_forward(a,q,k,v,None,dropout=0.,scaling=a.scaling,sliding_window=None)
        else:
            # Independent per configuration/layer/call Philox keys; NOT paired S prefixes.
            identity=f'{self.seed}:{a.layer_idx}:{state["calls"]}:{self.cfg}'
            key=int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8],'little') & ((1<<63)-1)
            out,diag=attention(q,k,v,self.cfg,key,True)
            out=out.transpose(1,2)
            state['zero_fallback']+=diag['zero_fallback_groups']
            state['route_elements']+=b*diag['h']*diag['n']*self.cfg.r if diag['n']>self.cfg.k else 0
            state['selected_k_elements']+=b*diag['h']*diag['k']*a.head_dim
            if diag['local_indices'] is not None:
                state['sampled_head_rows']+=b*q.shape[1]
                activity=diag['activity'].sum(0)
                state['_activity']=state.get('_activity',torch.zeros_like(activity))+activity
                unique=diag['unique_v_group_union']
                state['_unique_v']=state.get('_unique_v',torch.zeros_like(unique))+unique
        out=out.reshape(*hidden_states.shape[:-1],-1).contiguous()
        return a.o_proj(out.to(hidden_states.dtype)),None

    def report(self):
        def plain(v):
            return v.detach().cpu().tolist() if isinstance(v,torch.Tensor) else v
        return dict(config=asdict(self.cfg) if self.cfg else None,seed=self.seed,
            layers={str(i):{k:plain(v) for k,v in row.items()} for i,row in self.state.items()},
            original_ffn=True,ideal_sigmoid_source=True,hardware_ppa=None,
            rng='independent SHA256-keyed Philox per seed/config/layer/call; not paired across S',
            counts='ideal logical counts only; zero-fallback costs excluded and flagged')

    def close(self):
        for a,original in self.originals:a.forward=original
        self.originals=[]
