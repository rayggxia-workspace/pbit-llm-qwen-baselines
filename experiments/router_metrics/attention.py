import math
from types import MethodType
import torch
from transformers.models.qwen2.modeling_qwen2 import apply_rotary_pos_emb,repeat_kv
from metrics import cache,score,sizes,mandatory,probabilities,macs
from sparse import sparse_attention


class Controller:
    def __init__(self,mode,reps,ratio,seed,backend='sparse',context=2048,selection='stochastic'):
        self.mode,self.ratio,self.backend,self.selection=mode,ratio,backend,selection
        self.generator=torch.Generator(device='cuda').manual_seed(seed)
        self.stats=torch.zeros(7,dtype=torch.float64,device='cuda')
        self.params=None
        if mode!='sdpa':
            name=f'{context}_{ratio}_{mode}'
            path='artifacts/moment.pt' if selection=='moment' else ('artifacts/distilled.pt' if mode=='distill' else 'artifacts/calibrated.pt')
            self.params=torch.load(path,map_location='cuda',weights_only=True)[name]

    def select(self,attn,q,k):
        p=self.params;i=attn.layer_idx
        state=cache(attn,k,self.mode);n=sizes(k.shape[-2],q.device)
        scores=score(q,state,k.shape[-2],self.mode,p['alpha'][i][None,:,None],p['scales'][i][None,:,None])
        if self.selection=='deterministic':
            count=max(min(3,n.numel()),math.ceil(self.ratio*n.numel()))
            ranked=scores.masked_fill(mandatory(n),torch.inf)
            mask=torch.zeros_like(scores,dtype=torch.bool).scatter_(-1,ranked.topk(count,-1).indices,True)
        elif self.selection=='moment':
            fixed=mandatory(n);free=(~fixed).float()
            mu=(scores*free).sum(-1,keepdim=True)/free.sum()
            std=((scores-mu).square()*free).sum(-1,keepdim=True)/free.sum()
            normalized=(scores-mu)/std.sqrt().clamp_min(.01)
            pi=((normalized+p['parameter'][i][None,:,None])/p['temperature'][i][None,:,None]).sigmoid().masked_fill(fixed,1.)
            mask=torch.rand(pi.shape,device=q.device,generator=self.generator)<pi
        elif self.selection=='adaptive':
            # Diagnostic query-wise expected-budget matching. No test labels.
            # Extra reductions/root solving are explicitly charged in timing.
            tau=p['temperature'][i][None,:,None]
            lo=-scores.amax(-1,keepdim=True)-32*tau
            hi=-scores.amin(-1,keepdim=True)+32*tau
            fixed=mandatory(n)
            for _ in range(16):
                mid=(lo+hi)/2
                pi=((scores+mid)/tau).sigmoid().masked_fill(fixed,1.)
                fraction=(pi*n).sum(-1,keepdim=True)/k.shape[-2]
                lo=torch.where(fraction<self.ratio,mid,lo)
                hi=torch.where(fraction>=self.ratio,mid,hi)
            pi=((scores+(lo+hi)/2)/tau).sigmoid().masked_fill(fixed,1.)
            mask=torch.rand(pi.shape,device=q.device,generator=self.generator)<pi
        else:
            pi=probabilities(scores,n,self.mode,p['temperature'][i][None,:,None],p['parameter'][i][None,:,None])
            mask=torch.rand(pi.shape,device=q.device,generator=self.generator)<pi
        return mask.contiguous()

    def record(self,mask,length):
        n=sizes(length,mask.device);chosen=(mask*n).sum();rows=mask.shape[0]*mask.shape[1]
        union=(mask.reshape(mask.shape[0],2,7,-1).any(2)*n).sum()
        self.stats+=torch.stack((chosen,chosen.new_tensor(rows*length),union,chosen.new_tensor(rows*length/7),mask.sum(),chosen.new_tensor(mask.numel()),chosen.new_tensor(mask.numel()*macs(self.mode)))).double()

    def summary(self):
        a=self.stats.tolist()
        if not a[1]:return {}
        return {'selected_token_fraction':a[0]/a[1],'GQA_union_fraction':a[2]/a[3],'selected_block_fraction':a[4]/a[5],
            'selector_MAC_ratio_to_dense_QK_PV':a[6]/(128*a[1]),'total_QK_PV_selector_MAC_ratio':(128*a[0]+a[6])/(128*a[1]),
            'cost_scope':'selected QK/PV plus score dot products; excludes cache maintenance, reductions, nonlinearities, RNG, topk, memory and launches; mix counted as TWO dot products, no cache fusion claimed'}


def forward(self,hidden_states,attention_mask=None,position_ids=None,past_key_value=None,output_attentions=False,use_cache=False,cache_position=None,position_embeddings=None):
    ctl=self._controller
    if hidden_states.shape[1]!=1 or ctl.mode=='sdpa':
        if hidden_states.shape[1]!=1:self._metrics_cache=None
        return self._original(hidden_states,attention_mask=attention_mask,position_ids=position_ids,past_key_value=past_key_value,output_attentions=output_attentions,use_cache=use_cache,cache_position=cache_position,position_embeddings=position_embeddings)
    if attention_mask is not None or output_attentions:raise ValueError('unpadded causal decode only')
    b,n,_=hidden_states.shape
    q=self.q_proj(hidden_states).view(b,n,14,64).transpose(1,2)
    k=self.k_proj(hidden_states).view(b,n,2,64).transpose(1,2)
    v=self.v_proj(hidden_states).view(b,n,2,64).transpose(1,2)
    cos,sin=self.rotary_emb(v,position_ids) if position_embeddings is None else position_embeddings
    q,k=apply_rotary_pos_emb(q,k,cos,sin)
    if past_key_value is not None:k,v=past_key_value.update(k,v,self.layer_idx,{'sin':sin,'cos':cos,'cache_position':cache_position})
    mask=ctl.select(self,q,k)
    if ctl.backend=='sparse':out=sparse_attention(q,k,v,mask)
    else:
        z=q.float()@repeat_kv(k,7).float().transpose(-1,-2)/8
        p=z.masked_fill(~mask.repeat_interleave(64,-1)[...,:k.shape[-2]].unsqueeze(-2),-torch.inf).softmax(-1)
        out=(p@repeat_kv(v,7).float()).to(q.dtype)
    ctl.record(mask,k.shape[-2])
    return self.o_proj(out.transpose(1,2).contiguous().reshape(b,n,896)),None,past_key_value


def install(model,ctl):
    for layer in model.model.layers:
        attn=layer.self_attn;attn._original=attn.forward;attn._controller=ctl
        attn.forward=MethodType(forward,attn)
