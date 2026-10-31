"""Probe only: bind the published S12/F4 -> U8/F4 -> P8 LUT law."""
import math
import torch

class Patch:
    def __init__(self,core,kernels,table):
        self.core,self.kernels,self.table=core,kernels,table
        self.old_probability=kernels.probabilities;self.old_readout=core.readout
        self.kind='winner';self.metrics={};self.reset()
    def reset(self):
        self.metrics={};self.calls=0
    def add(self,name,value):
        value=value.detach().to(torch.float64)
        self.metrics[name]=value if name not in self.metrics else self.metrics[name]+value
    def quant(self,z):
        if not bool(torch.isfinite(z).all()):raise ValueError('finite unpadded scores required')
        raw=torch.round(z.float()*16)
        code=raw.clamp(-2048,2047).to(torch.int32)
        ref=code.argmax(-1)
        gap=code.amax(-1,keepdim=True)-code
        addr=gap.clamp(0,255).long()
        threshold=self.table[addr]
        p=threshold.float()/256.
        self.add('score_entries',torch.tensor(z.numel(),device=z.device))
        self.add('score_saturated',(raw!=code).sum())
        self.add('gap_saturated',(gap>255).sum())
        self.add('zero_threshold_entries',(threshold==0).sum())
        self.calls+=1
        return p,ref,threshold
    def probabilities(self,logits,method):
        if method!='winner':raise ValueError('probe does not change rejection law')
        z=logits.float().contiguous();p,ref,_=self.quant(z)
        rows,n=z.shape
        planes=torch.zeros((rows,26,n),device=z.device,dtype=torch.float32)
        planes[:,0,:]=p
        planes[:,25,:].scatter_(1,ref[:,None],1.)
        return planes.contiguous()
    def readout(self,logits,value,cfg,seed):
        if self.kind not in ('mean','iid_p8'):
            return self.old_readout(logits,value,cfg,seed)
        b,h,g,n=logits.shape;flat=logits.reshape(-1,n)
        p,ref,threshold=self.quant(flat)
        odds=p/(1-p);weight=odds/odds.sum(-1,keepdim=True)
        if self.kind=='mean':
            pref=flat.float().softmax(-1)
            self.add('diagnostic_head_rows',torch.tensor(flat.shape[0],device=flat.device))
            self.add('zeroed_reference_mass',pref.masked_fill(threshold!=0,0).sum())
            self.add('stationary_tv',.5*(weight-pref).abs().sum())
            return weight.reshape(b,h,g,n)@value,None,None
        gen=torch.Generator(device=flat.device).manual_seed(seed)
        ids=torch.multinomial(weight,cfg.samples,replacement=True,generator=gen).reshape(b,h,g,cfg.samples)
        bb=torch.arange(b,device=value.device)[:,None,None,None]
        hh=torch.arange(h,device=value.device)[None,:,None,None]
        out=value[bb,hh,ids].sum(-2)/cfg.samples
        stats=torch.zeros((flat.shape[0],6),device=value.device,dtype=torch.int64);stats[:,1]=cfg.samples
        return out,ids,stats
    def __enter__(self):
        self.kernels.probabilities=self.probabilities;self.core.readout=self.readout;return self
    def __exit__(self,*args):
        self.kernels.probabilities=self.old_probability;self.core.readout=self.old_readout
    def report(self):
        r={k:float(v.cpu()) for k,v in self.metrics.items()};r['quantized_calls']=self.calls
        if r.get('diagnostic_head_rows'):
            r['mean_zeroed_reference_mass']=r['zeroed_reference_mass']/r['diagnostic_head_rows']
            r['mean_stationary_tv']=r['stationary_tv']/r['diagnostic_head_rows']
        return r

def selftest(device,core,kernels,table):
    golden=torch.tensor([round(256/(1+math.exp(a/16))) for a in range(256)],device=device,dtype=torch.int64)
    assert torch.equal(table,golden)
    patch=Patch(core,kernels,table)
    z=torch.tensor([[0.,-1.,-6.25,-7.]],device=device)
    p,ref,q=patch.quant(z)
    assert ref.tolist()==[0] and q[0,0]==128 and q[0,2]==0 and q[0,3]==0
    u=torch.linspace(0,1-2**-16,65536,device=device)
    for threshold in (0,1,64,128,255,256):
        assert torch.equal(u<threshold/256.,torch.floor(u*256).long()<threshold)
    # Actual Triton output must equal independent finite-bit rule replay.
    z=torch.tensor([[.2,0.,-1.,-4.],[0.,0.,0.,0.]],device=device)
    rows,n=z.shape;S=8;burn=2;cap=S+burn
    gen=torch.Generator(device=device).manual_seed(222)
    words=torch.randint(256,(rows,cap,n),device=device,generator=gen)
    thresholds=patch.quant(z)[2]
    bits=words<thresholds[:,None,:]
    raw=torch.zeros((rows,cap),device=device,dtype=torch.int64)
    # raw=0 is accepted unbiased-rank draw only when count divides 2^32;
    # use large raw values with computed valid ranks for replay.
    ranks=torch.zeros_like(raw)
    for row in range(rows):
        for t in range(cap):
            count=max(int(bits[row,t].sum()),1)
            raw[row,t]=2**31;ranks[row,t]=(2**31)%count
    expected=core.torch_winner_replay(bits,ranks,thresholds.argmax(-1),burn)
    coin=torch.zeros((rows,cap),device=device)
    with patch:
        actual,stats=kernels.sample(z,S,'winner',burn=burn,seed=7,replay=(words.float()/256,raw,coin))
    assert torch.equal(actual,expected)
    assert bool((stats[:,0]==cap).all()) and bool((stats[:,1]==S).all())
    return dict(lut_entries=256,dyadic_R8_equivalence=True,triton_integer_rule_replay=True)
