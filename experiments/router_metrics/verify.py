import json
from pathlib import Path
from types import SimpleNamespace
import torch
from transformers.models.qwen2.modeling_qwen2 import repeat_kv
from metrics import METHODS,build,cache,score,mandatory,sizes
from sparse import sparse_attention


@torch.inference_mode()
def main():
    torch.manual_seed(21);rows=[]
    for length in (65,127,128,129,2048):
        k=torch.randn(2,2,length,64,device='cuda',dtype=torch.bfloat16);v=torch.randn_like(k)
        q=torch.randn(2,14,1,64,device='cuda',dtype=torch.bfloat16)
        for method in METHODS:
            a=SimpleNamespace();cache(a,k[:,:,:length-1],method);state=cache(a,k,method)
            b=SimpleNamespace();expected=cache(b,k,method)
            for x,y in zip(state,expected):
                if x is not None:assert torch.allclose(x,y,atol=1e-5)
            scores=score(q,state,length,method,.5,torch.ones(2,device='cuda'))
            assert torch.isfinite(scores).all()
            if method=='bound':
                exact=(q.float()@repeat_kv(k,7).float().transpose(-1,-2)/8).squeeze(-2)
                for block in range(scores.shape[-1]):assert (scores[:,:,block]+1e-5>=exact[:,:,block*64:(block+1)*64].amax(-1)).all()
        mask=torch.rand(2,14,(length+63)//64,device='cuda')<.3
        mask=mask.masked_fill(mandatory(sizes(length,q.device)),True)
        got=sparse_attention(q,k,v,mask)
        z=q.float()@repeat_kv(k,7).float().transpose(-1,-2)/8
        p=z.masked_fill(~mask.repeat_interleave(64,-1)[...,:length].unsqueeze(-2),-torch.inf).softmax(-1)
        expected=(p@repeat_kv(v,7).float()).to(q.dtype)
        assert torch.allclose(got.float(),expected.float(),atol=.002,rtol=.01)
        rows.append({'length':length,'max_error':(got.float()-expected.float()).abs().max().item()})
    Path('results/kernel_checks.json').write_text(json.dumps({'status':'passed','cache':'incremental/full agree for all six methods','bound':'dominates actual token score','sparse':rows},indent=2))
    print('checks passed',flush=True)


if __name__=='__main__':main()
