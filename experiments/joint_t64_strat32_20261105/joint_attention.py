"""Extend frozen Issue198 max-gap sampler to the verified trained FFN.

BF16 QKV/RoPE unchanged, S12/F4 RNE before max, U8/F4 gap saturation,
frozen floor-P8 LUT. Independent candidate RNG, winner slot0/burn0/S64.
"""
from types import MethodType
from experiments.sparq_ising_20261028 import adapter, scoring
from experiments.attention_gap_accuracy_20261102.methods import Patch as GapPatch, configuration

class JointController(adapter.Controller):
    def __init__(self,model,cfg=None,seed=0):
        if model.training or model.config.model_type!='qwen3' or model.config._attn_implementation!='sdpa':
            raise ValueError('eval SDPA Qwen3 required')
        if len(model.model.layers)!=36:raise ValueError('36 layers required')
        self.model,self.cfg,self.seed=model,cfg,seed
        self.prefix=False;self.originals=[];self.state={}
        for i,layer in enumerate(model.model.layers):
            a=layer.self_attn
            if a.layer_idx!=i or a.sliding_window is not None:raise ValueError('unsupported attention')
            # Only the FFN type restriction differs from the existing adapter;
            # the caller separately verifies every trained export and T32 config.
            self.originals.append((a,a.forward))
            self.state[i]=dict(decode_queries=0,prefill_queries=0,calls=0,zero_fallback=0,
                              route_elements=0,selected_k_elements=0,sampled_head_rows=0)
            a.forward=MethodType(self.dispatch,a)
    def report(self):
        r=super().report();r.update(original_ffn=False,ffn='trainedT64 export, stratifiedT32',
            ideal_sigmoid_source=False,numeric='signed12/F4 RNE -> max gap -> saturated U8/F4 -> floor-P8 LUT',
            rng='independent Philox candidate R8 and independent unbiased fair-rank uint32; not GF64')
        return r

class AttentionPatch:
    def __init__(self,enabled):self.enabled=enabled
    def __enter__(self):
        self.previous=scoring.Controller;scoring.Controller=JointController
        self.gap=GapPatch('ising64_gap_s12_p8' if self.enabled else 'bf16')
        self.gap.__enter__()
        self.controller_class=scoring.Controller
        return self
    def controller(self,model,seed):
        return self.controller_class(model,configuration('ising64_gap_s12_p8') if self.enabled else None,seed)
    def __exit__(self,*exc):
        self.gap.__exit__(*exc);scoring.Controller=self.previous
