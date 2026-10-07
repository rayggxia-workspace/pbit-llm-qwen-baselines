"""Offline teacher block mass/contributions, disjoint train-tail validation."""
import hashlib
import json
from pathlib import Path
from types import MethodType
import torch
from torch.nn import functional as F
from transformers import AutoTokenizer,AutoModelForCausalLM
from transformers.models.qwen2.modeling_qwen2 import apply_rotary_pos_emb,repeat_kv
from metrics import build,score


@torch.inference_mode()
def main():
    torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False
    tok=AutoTokenizer.from_pretrained('models/Qwen2.5-0.5B',local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained('models/Qwen2.5-0.5B',torch_dtype=torch.bfloat16,attn_implementation='sdpa',local_files_only=True).cuda().eval()
    path=Path('data/wikitext-2/wiki.train.raw')
    ids=tok(path.read_text(),add_special_tokens=False,return_tensors='pt').input_ids[0]
    split=len(ids)-65536
    starts=torch.linspace(0,split-8192,32).long().tolist()+list(range(split,len(ids)-8192+1,8192))
    rec=[[] for _ in range(24)]
    def wrapped(self,hidden_states,position_ids=None,position_embeddings=None,**kwargs):
        b,l,_=hidden_states.shape
        q=self.q_proj(hidden_states).view(b,l,14,64).transpose(1,2)
        k=self.k_proj(hidden_states).view(b,l,2,64).transpose(1,2)
        v=self.v_proj(hidden_states).view(b,l,2,64).transpose(1,2)
        cos,sin=self.rotary_emb(v,position_ids) if position_embeddings is None else position_embeddings
        q,k=apply_rotary_pos_emb(q,k,cos,sin)
        for length in range(1024,8193,1024):
            qi,ki=q[:,:,length-1:length],k[:,:,:length]
            vi=repeat_kv(v[:,:,:length],7).float()
            p=(qi.float()@repeat_kv(ki,7).float().transpose(-1,-2)/8).softmax(-1).squeeze(-2)
            mass=p.reshape(1,14,-1,64).sum(-1)
            contribution=(p[:,:,:,None]*vi).reshape(1,14,-1,64,64).sum(-2)
            state=build(ki)
            scores=torch.stack([score(qi,state,length,m) for m in ('mean_sigmoid','max2','max4','bound')],-1)
            pad=128-length//64
            rec[self.layer_idx].append((F.pad(scores,(0,0,0,pad))[0].half().cpu(),F.pad(mass,(0,pad))[0].cpu(),F.pad(contribution,(0,0,0,pad))[0].half().cpu(),length//64))
        return self._original(hidden_states,position_ids=position_ids,position_embeddings=position_embeddings,**kwargs)
    for layer in model.model.layers:
        layer.self_attn._original=layer.self_attn.forward;layer.self_attn.forward=MethodType(wrapped,layer.self_attn)
    for i,start in enumerate(starts):
        model.model(input_ids=ids[start:start+8192][None].cuda(),use_cache=False)
        print(json.dumps({'window':i+1,'total':len(starts)}),flush=True)
    out={}
    for field,key in enumerate(('scores','mass','contrib','counts')):
        out[key]=torch.stack([torch.stack([torch.as_tensor(row[field]) for row in layer]) for layer in rec])
    for key in ('scores','mass','contrib'):out[key]=out[key].transpose(1,2).contiguous()
    out['counts']=out['counts'][0];out['train_n']=256
    Path('artifacts').mkdir(exist_ok=True);torch.save(out,'artifacts/teacher.pt')
    Path('results').mkdir(exist_ok=True)
    Path('results/data_protocol.json').write_text(json.dumps({'source':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'split':split,'starts':starts,'train_windows':32,'valid_windows':8,'query_lengths':list(range(1024,8193,1024)),'test_used':False,'contrib_precision':'FP16 stored, FP32 computed'},indent=2))


if __name__=='__main__':main()
