"""Offline verification of archived PPL ledgers; Python standard library only."""
from pathlib import Path
import gzip, hashlib, json, math

HERE=Path(__file__).resolve().parent
def digest(b): return hashlib.sha256(b).hexdigest()
def plan(context,full,decode):
    n=299078; rows=[]
    if full:
        previous=0
        for begin in range(0,n,1024):
            end=min(begin+context,n); first=max(previous,begin+1)
            if first<end:
                rows.append(dict(segment_id=len(rows),begin=begin,end=end,first_target=first,
                    last_target_exclusive=end,prefill_tokens=first-begin-1,scored_tokens=end-first))
            previous=end
            if end==n:break
    else:
        starts=[round((n-context-decode)*i/7) for i in range(8)]
        rows=[dict(segment_id=i,begin=b,end=b+context+decode,first_target=b+context,
            last_target_exclusive=b+context+decode,prefill_tokens=context-1,scored_tokens=decode)
            for i,b in enumerate(starts)]
    return rows

def main():
    index=json.loads((HERE/'INDEX.json').read_bytes()); counts=[0,0]
    for item in index['batches']:
        z=(HERE/item['file']).read_bytes(); assert digest(z)==item['gzip_sha256']
        raw=gzip.decompress(z); assert digest(raw)==item['payload_sha256']
        batch=json.loads(raw); assert len(batch['results'])==item['cases']
        assert batch['source_identity']==item['source_identity'] and len(item['source_identity'])==64
        decode=256 if item['batch'].startswith('joint_') else 1024
        expected=plan(item['context'],item['full_WT2'],decode)
        targets=sum(x['scored_tokens'] for x in expected)
        assert targets==(299077 if item['full_WT2'] else decode*8)
        for r in batch['results']:
            rows=r['records']; assert len(rows)==len(expected)
            assert all(all(row[k]==v for k,v in p.items()) for row,p in zip(rows,expected))
            assert r.get('targets',r.get('scored_tokens'))==targets
            nll=math.fsum(x['nll_sum'] for x in rows)
            assert math.isclose(nll,r['nll_sum'],rel_tol=1e-12)
            assert math.isclose(math.exp(nll/targets),r.get('ppl',r.get('perplexity')),rel_tol=1e-12)
            for key in ('targets_per_layer','tokens_per_layer','scored_tokens_per_layer'):
                if key in r: assert r[key]==[targets]*36,(item['batch'],key)
            counts[0 if item['full_WT2'] else 1]+=1
        print(item['batch'],len(batch['results']),'PASS',len(expected),'windows',targets,'targets')
    assert counts==[index['full_cases'],index['short_cases']]==[58,23]
    assert sum(counts)==index['accepted_cases']==81
    print('PASS: 81 entries (58 full WT2, 23 short), exact plan coverage, hashes and NLL-to-PPL')

if __name__=='__main__':main()
