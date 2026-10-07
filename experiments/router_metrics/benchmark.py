import json
from pathlib import Path
from types import SimpleNamespace
import torch
import triton
from torch.nn import functional as F
from transformers.models.qwen2.modeling_qwen2 import repeat_kv
from attention import Controller
from metrics import cache
from sparse import sparse_attention


@torch.inference_mode()
def main():
    rows=[]
    variants=[(m,'stochastic') for m in ('mean_softmax','mean_sigmoid','max2','max4','bound','mix')]
    variants += [('max2','adaptive'),('max4','adaptive'),('mix','adaptive'),('max4','deterministic')]
    variants += [('max2','moment'),('max4','moment')]
    for length,batch in ((2048,16),(8192,4)):
        snap=torch.load(f'artifacts/snapshot_ctx{length}.pt',map_location='cuda',weights_only=True)
        q=snap['q'][:batch].contiguous();k=snap['k'][:batch].contiguous();v=snap['v'][:batch].contiguous()
        dense=lambda:F.scaled_dot_product_attention(q,repeat_kv(k,7),repeat_kv(v,7),is_causal=False)
        dense();base=triton.testing.do_bench(dense,warmup=50,rep=150)
        for method,selection in variants:
            ctl=Controller(method,1,.3,0,context=length,selection=selection)
            attn=SimpleNamespace(layer_idx=12)
            state=cache(attn,k,method)
            def select():
                # Repeated fixed-step timing. Only reset the last sum; no full-cache clone/scan.
                if state[0] is not None:state[0][:,:,-1,-1]-=k[:,:,-1].float()
                attn._metrics_cache=(length-1,state)
                return ctl.select(attn,q,k)
            mask=select()
            def total():return sparse_attention(q,k,v,select())
            total()
            select_ms=triton.testing.do_bench(select,warmup=50,rep=150)
            sparse_ms=triton.testing.do_bench(lambda:sparse_attention(q,k,v,mask),warmup=50,rep=150)
            total_ms=triton.testing.do_bench(total,warmup=50,rep=150)
            row={'context':length,'batch':batch,'method':method,'selection':selection,'budget':.3,'SDPA_ms':base,'selector_ms':select_ms,'sparse_ms':sparse_ms,'total_ms':total_ms,'snapshot_selected_fraction':mask.float().mean().item()}
            rows.append(row);print(json.dumps(row),flush=True)
    Path('results/benchmark.json').write_text(json.dumps({'gpu':torch.cuda.get_device_name(),'scope':'One layer/query step, real layer12 snapshots from previous mean-router run; warmed serial CUDA events. Includes tiny reset subtraction in selector. Baseline repeat_kv+SDPA; not a native-GQA optimum. Prefix summary initialization and full model projections/FFNs excluded.','results':rows},indent=2))


if __name__=='__main__':main()
