"""Inference port of Apple's paired Gala checkpoints; validate against AXLearn first.

Architecture sources: apple/axlearn gala.py, gala_sigmoid.py, attention.py,
layers.py and embedding.py. Original Zarr arrays remain unmodified.
"""
from pathlib import Path
import hashlib, json, math
import sentencepiece as spm
import torch
import torch.nn.functional as F
from safetensors.torch import load_file


class Tokenizer:
    def __init__(self, path):
        self.sp = spm.SentencePieceProcessor(model_file=str(path))
        # Official BPE is 32,000 pieces; Gala pads embedding/logit capacity to 32,768.
        assert self.sp.vocab_size() == 32000
        assert (self.sp.pad_id(),self.sp.eos_id(),self.sp.unk_id()) == (0,1,2)

    def encode(self, text):
        return self.sp.encode(text.replace('\n', '<n>'), out_type=int)

    def decode(self, ids):
        return self.sp.decode(ids).replace('<n>', '\n')


def rms(x, scale):
    # Gala explicitly sets forward_dtype=None. Preserve operation boundaries.
    m = (x * x).mean(-1, keepdim=True)
    return (x * torch.rsqrt(m + 1e-5)) * scale


class Gala:
    def __init__(self, converted, kind, device='cuda', dtype=torch.bfloat16):
        assert kind in ('sigmoid', 'softmax')
        self.kind, self.device, self.dtype = kind, torch.device(device), dtype
        root = Path(converted)
        self.config = json.loads((root/'config.json').read_text())
        assert self.config['layers'] == 32 and self.config['training_seq_len'] == 4096
        self.w = {}
        for row in self.config['arrays']:
            h=hashlib.sha256()
            with (root/row['file']).open('rb') as f:
                for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
            assert h.hexdigest()==row['sha256'],row['file']
            state = load_file(str(root/row['file']), device=str(device))
            self.w[row['path']] = state['weight'].to(dtype)
        self.emb = self.w['emb/token_emb/weight']
        self.final_scale = self.w['output_norm/scale']
        self.layers = []
        prefix = 'transformer/repeat/layer/'
        for i in range(32):
            d = {k[len(prefix):]: v[i] for k,v in self.w.items() if k.startswith(prefix)}
            # F.linear expects [output,input]; AXLearn uses [input,output].
            if dtype == torch.float32:
                # Views avoid duplicating 6.4 GB of QKV weights on a 32 GB GPU.
                d['qkv_separate'] = [a.reshape(4096,4096).T for a in d['self_attention/attention/i_proj/qkv_proj/weight'].unbind(0)]
            else:
                d['qkv'] = d['self_attention/attention/i_proj/qkv_proj/weight'].permute(0,2,3,1).reshape(3*4096,4096).contiguous()
            d['out'] = d['self_attention/attention/o_proj/weight'].reshape(4096,4096)
            d['gate'] = d['feed_forward/linear1_0/weight'].T
            d['up'] = d['feed_forward/linear1_1/weight'].T
            d['down'] = d['feed_forward/linear2/weight'].T
            self.layers.append(d)
        # Drop original QKV storage after allocating the transposed, contiguous projection.
        for d in self.layers:
            del d['self_attention/attention/i_proj/qkv_proj/weight']
        self.w = {k:v for k,v in self.w.items() if 'i_proj/qkv_proj' not in k}
        self.slopes = torch.tensor([2**(-0.25*(i+1)) for i in range(32)],device=device,dtype=torch.float32)[None,:,None,None]

    @torch.inference_mode()
    def __call__(self, ids, last_positions=None, query_chunk=256):
        """Uncached causal inference; right padding cannot change earlier positions.

        Keep Sigmoid weights in FP32 as native sigmoid_with_biases does; PV is
        accumulated in FP32 and cast to V dtype before the output projection.
        """
        b,t = ids.shape
        assert 0 < t <= 4096
        x = F.embedding(ids,self.emb)
        pos = torch.arange(t,device=self.device)
        # AXLearn masks trailing padding; interior zero IDs remain in the segment.
        lengths=((pos+1)[None,:]*ids.ne(0)).max(-1).values
        keys_valid = (pos[None,:] < lengths[:,None])[:,None,None,:]
        for d in self.layers:
            n = rms(x,d['self_attention/prenorm/scale'])
            if 'qkv_separate' in d:
                q,k,v = [F.linear(n,w).view(b,t,32,128) for w in d['qkv_separate']]
            else:
                q,k,v = F.linear(n,d['qkv']).view(b,t,3,32,128).unbind(2)
            q = rms(q,d['self_attention/attention/scale_query/norm/scale']) * (128**-0.5)
            k = rms(k,d['self_attention/attention/scale_key/norm/scale'])
            q,k,v = [a.transpose(1,2) for a in (q,k,v)]
            chunks=[]
            for start in range(0,t,query_chunk):
                end=min(start+query_chunk,t)
                qp=pos[start:end,None]
                bias=(pos[None,:]-qp).float()[None,None,:,:]*self.slopes
                mask=(pos[None,:] <= qp)[None,None,:,:] & keys_valid
                bias=bias.masked_fill(~mask,float('-inf'))
                # AXLearn first computes dot in the model dtype, then applies FP32 biases.
                z=torch.matmul(q[:,:,start:end],k.transpose(-1,-2)).float()
                z=z+bias
                p=torch.sigmoid(z-math.log(4096)) if self.kind=='sigmoid' else torch.softmax(z,-1)
                c=torch.matmul(p,v.float()).to(v.dtype)
                chunks.append(c.transpose(1,2))
            c=torch.cat(chunks,dim=1).reshape(b,t,4096)
            a=F.linear(c,d['out'])
            x=x+rms(a,d['self_attention/postnorm/scale'])
            n=rms(x,d['feed_forward/prenorm/scale'])
            g=F.silu(F.linear(n,d['gate']))*F.linear(n,d['up'])
            a=F.linear(g,d['down'])
            x=x+rms(a,d['feed_forward/postnorm/scale'])
        x=rms(x,self.final_scale)
        if last_positions is not None:
            x=x[:,last_positions]
        return F.linear(x,self.emb)
