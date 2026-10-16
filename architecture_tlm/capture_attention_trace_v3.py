"""Optional offline QK trace collector, to call inside an existing decode runner.

Capture after Q/K RoPE and after appending K to the cache, before repeat_kv.
No monkeypatch of a guessed Transformers version. This helper is intentionally
independent of model loading; integrate at the verified attention forward point.
The extra dense reference QK is capture overhead, never simulated sparse work.
"""
import json
from pathlib import Path


class DecodeTraceCollector:
    def __init__(self,provenance):
        self.rows=[];self.provenance=dict(provenance)

    def add(self,token,layer,q,k):
        # q [1,H,1,D], k [1,KV,L,D], post-RoPE; causal unpadded decode only.
        import torch
        if q.ndim!=4 or k.ndim!=4 or q.shape[0]!=1 or k.shape[0]!=1 or q.shape[2]!=1:
            raise ValueError('capture requires batch1 single-token decode')
        if q.shape[-1]!=k.shape[-1] or q.shape[1]%k.shape[1]:raise ValueError('GQA dimensions')
        with torch.no_grad():
            key=k.float().repeat_interleave(q.shape[1]//k.shape[1],dim=1)
            logits=(q.float()@key.transpose(-1,-2))/(q.shape[-1]**.5)
            for head,row in enumerate(logits[0,:,0].cpu().tolist()):
                self.rows.append(dict(token=int(token),layer=int(layer),head=head,logits=row))

    def save(self,path):
        Path(path).write_text(json.dumps(dict(provenance=self.provenance,rows=self.rows)),encoding='utf-8')
