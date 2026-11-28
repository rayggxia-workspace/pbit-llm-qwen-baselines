"""Independent workload/manifest audit for a completed session."""
import argparse,hashlib,json
from pathlib import Path


def verify(root):
    load=lambda p:json.loads(p.read_bytes())
    seal=load(root/'SEAL.json')
    assert seal['status']=='completed'
    for name,digest in seal['sha256'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
    r=load(root/'RESULT.json');p=r['plan'];m=p['model']
    L,G=p['prompt'],p['generated'];tokens=L+G-1
    gu=m['layers']*tokens*(m['ffn']//64)*(m['hidden']//64)
    wd=m['layers']*tokens*(m['hidden']//128)*(m['ffn']//64)
    assert sum(n for k,n in r['frames'].items() if k.endswith('/GU'))==gu
    assert sum(n for k,n in r['frames'].items() if k.endswith('/WD'))==wd
    mac=r['engines']['digital']['actions']
    assert mac['QKV']==tokens*m['layers']*m['hidden']*(m['q_heads']+2*m['kv_heads'])*m['head_dim']
    assert mac['O']==tokens*m['layers']*m['hidden']*m['q_heads']*m['head_dim']
    assert mac['LM_HEAD']==G*m['vocab']*m['hidden']
    assert r['actions']['head_streamed_logits']==G*m['vocab']
    assert r['actions']['causal_queries']==tokens*m['layers']*m['q_heads']
    assert len(r['output_times_ms'])==G and r['kv_lengths']==[tokens]*m['layers']
    assert r['state_peak_slots']<=load(root/'HARDWARE.json')['state_slots']
    for layer in range(m['layers']):
        length=0
        for row in (x for x in r['kv_audit'] if x['layer']==layer):
            assert row['begin']==length and row['end']>length
            length=row['end']
        assert length==tokens
    return dict(status='PASS',layers=m['layers'],prompt=L,generated=G,
                GU_frames=gu,WD_frames=wd,causal_queries=r['actions']['causal_queries'],
                scope='shape/control/byte audit;not numerical PPL or native DRAM validation')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args()
    print(json.dumps(verify(a.root),indent=2))
