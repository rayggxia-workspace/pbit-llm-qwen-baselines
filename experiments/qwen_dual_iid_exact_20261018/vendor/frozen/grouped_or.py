"""Exact IID temporal compression for small-group signed OR.

Each group has 2**g active masks. Counts are sampled jointly as a multinomial,
then reused for every output/weight bit. No Gaussian or independent-plane noise.
"""
import torch
from core import StochasticMatrixFFN, GROUP

def mask_probabilities(p):
    g=p.shape[-1]
    return torch.stack([torch.where(
        torch.tensor([(mask>>j)&1 for j in range(g)],device=p.device,dtype=torch.bool),
        p,1-p).prod(-1) for mask in range(2**g)],-1)

def multinomial_counts(probs, cycles, generator):
    # Conditional binomial draws give an exact multinomial law (up to FP rounding).
    probs=probs.double();probs=probs/probs.sum(-1,keepdim=True)
    tail=probs.flip(-1).cumsum(-1).flip(-1)
    remaining=torch.full_like(probs[...,0],float(cycles));counts=[]
    for k in range(probs.shape[-1]-1):
        q=(probs[...,k]/tail[...,k].clamp_min(1e-300)).clamp(0,1)
        n=torch.binomial(remaining,q,generator=generator)
        counts.append(n);remaining=remaining-n
    counts.append(remaining)
    return torch.stack(counts,-1).float()

def signed_or_table(codes, group):
    # [outputs, input_groups, group] -> [3**group, input_groups, outputs]
    # Ternary digits: 0 inactive, 1 positive input, 2 negative input.
    state=torch.arange(3**group,device=codes.device)[:,None,None]
    pos=torch.zeros((3**group,codes.shape[1],codes.shape[0]),device=codes.device,dtype=codes.dtype)
    neg=torch.zeros_like(pos)
    for j in range(group):
        digit=(state//(3**j))%3
        w=codes[...,j].T[None,:,:]
        positive=((digit==1)&(w>0))|((digit==2)&(w<0))
        negative=((digit==1)&(w<0))|((digit==2)&(w>0))
        pos=pos|torch.where(positive,w.abs(),0)
        neg=neg|torch.where(negative,w.abs(),0)
    return pos-neg

class GroupedORFFN(StochasticMatrixFFN):
    def __init__(self,*args,or_group=4,**kwargs):
        super().__init__(*args,**kwargs)
        assert or_group in (1,2,4)
        self.or_group=or_group

    def _or_projection(self,probability,sign,input_scale,name,generator):
        group=self.or_group
        spec=self._spec(name)
        inputs=spec.codes.shape[1];outputs=spec.codes.shape[0];ng=inputs//group
        states=3**group;shape=probability.shape
        p=probability.reshape(-1,ng,group)
        s=sign.reshape(-1,ng,group)
        # Input scales must be common within each OR group, as in group_max.
        scales=input_scale.reshape(ng,group)
        assert torch.equal(scales,scales[:,:1].expand_as(scales))
        counts=multinomial_counts(mask_probabilities(p),self.cycles,generator)
        # Convert masks to signed ternary states, without resampling any output.
        state_counts=torch.zeros((p.shape[0],ng,states),device=p.device,dtype=torch.float32)
        digits=torch.where(s>0,1,2)
        for mask in range(2**group):
            index=torch.zeros_like(digits[...,0])
            for j in range(group):
                if (mask>>j)&1:index=index+digits[...,j]*(3**j)
            state_counts.scatter_add_(-1,index[...,None],counts[...,mask,None])
        # All spatial sums and the time mean are exact for the sampled group counts.
        count_matrix=(state_counts/self.cycles).permute(0,2,1).reshape(p.shape[0],states*ng)
        result=torch.empty((p.shape[0],outputs),device=p.device,dtype=torch.float32)
        input_tile=torch.arange(ng,device=p.device)//(GROUP//group)
        for first in range(0,outputs,128):
            stop=min(first+128,outputs)
            c=spec.codes[first:stop].reshape(stop-first,ng,group).to(torch.int32)
            table=signed_or_table(c,group).float()
            output_tile=torch.arange(first,stop,device=p.device)//GROUP
            wscale=spec.tile_scales[output_tile[:,None],input_tile[None,:]].T
            table=table*(scales[:,0,None]*wscale)[None,:,:]
            result[:,first:stop]=count_matrix@table.reshape(states*ng,stop-first)
        return result.reshape(*shape[:-1],outputs)

    def diagnostics(self):
        d=super().diagnostics()
        d.update(or_group=self.or_group,or_joint_law='exact IID multinomial within each group; shared across all outputs and planes')
        return d
