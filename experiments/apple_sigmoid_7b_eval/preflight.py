from pathlib import Path
import argparse,json,math
import numpy as np
import torch
from model import Gala,Tokenizer

def main():
    p=argparse.ArgumentParser();p.add_argument('--converted',type=Path,required=True);p.add_argument('--kind',required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--device',default='cpu');p.add_argument('--dtype',default='float32');args=p.parse_args()
    model=Gala(args.converted,args.kind,args.device,getattr(torch,args.dtype))
    ref=np.load(args.reference);ids=torch.as_tensor(ref['input_ids'],device=args.device,dtype=torch.long)
    got=model(ids).float();expected=torch.from_numpy(ref['logits']).to(args.device)
    e=(got-expected).abs();nll=torch.nn.functional.cross_entropy(got[0,:-1],ids[0,1:]).item();nll_ref=torch.nn.functional.cross_entropy(expected[0,:-1],ids[0,1:]).item()
    prefix=model(ids[:,:8]).float();causal=(got[:,:8]-prefix).abs().max().item()
    padded=torch.nn.functional.pad(ids,(0,7),value=0);paderr=(model(padded)[:,:ids.shape[1]].float()-got).abs().max().item()
    thresholds={'logit_max':0.003 if args.dtype=='float32' else 1.0,'logit_rms':0.0003 if args.dtype=='float32' else 0.1,'nll_delta':0.0003 if args.dtype=='float32' else 0.03,'causal_max':0.003 if args.dtype=='float32' else 0.3,'padding_max':0.003 if args.dtype=='float32' else 0.3}
    metrics={'logit_max':e.max().item(),'logit_rms':e.square().mean().sqrt().item(),'nll_delta':abs(nll-nll_ref),'causal_max':causal,'padding_max':paderr}
    checks={k:math.isfinite(v) and v<=thresholds[k] for k,v in metrics.items()}
    out={'kind':args.kind,'dtype':args.dtype,'device':args.device,'reference':str(args.reference),'input_tokens':int(ids.shape[-1]),'metrics':metrics,'thresholds':thresholds,'checks':checks,'nll':nll,'native_nll':nll_ref,'passed':all(checks.values())}
    args.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2),flush=True)
    assert out['passed'],out

if __name__=='__main__':main()
