"""Independent arithmetic and GF joint-structure audit of saved output arrays."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def relation(masks):
    basis={}
    for i,value in enumerate(masks):
        dep=1<<i
        while value:
            pivot=value.bit_length()-1
            if pivot not in basis: basis[pivot]=(value,dep);break
            v,d=basis[pivot];value^=v;dep^=d
        if not value:return [i for i in range(len(masks)) if dep>>i&1]
    return None


def rank(rows):
    basis={}
    for a in rows:
        v=sum(int(x)<<i for i,x in enumerate(a))
        while v:
            k=v.bit_length()-1
            if k not in basis:basis[k]=v;break
            v^=basis[k]
    return len(basis)


def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);a=p.parse_args()
    result=json.loads((a.results/'RESULTS.json').read_text(encoding='utf-8'))
    root=Path(__file__).resolve().parents[3]
    manifest=json.loads((a.results/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    for path,h in manifest.items():
        if sha(root/Path(path.replace('\\','/')))!=h:raise ValueError('executed source changed: '+path)
    mapping=json.loads((root/'architecture_tlm/random_service/shared64_mapping.json').read_text(encoding='utf-8'))
    support=relation([int(row[7],16) for row in mapping['output_rows_lsb_first']])
    assert support
    rows=[];checks=0
    for r in result['cases']:
        path=Path(r['raw_artifact']['path']);assert sha(path)==r['raw_artifact']['sha256']
        with np.load(path) as data:
            x=data['a'];y=data['b'];cycles=data['accepted_cycles']
            assert len(x)==len(y)==len(cycles);assert np.all(np.diff(cycles)>0)
            checks+=3
            if 'output' not in r:continue
            assert abs(float((x[:,0]<128).mean())-r['output']['first_lane']['p1'])<1e-14
            assert abs(float(((x[:,0]<64)&(y[:,0]<192)).mean())-r['probes']['and_measured'])<1e-14
            assert len(x)==r['counts']['a']['prng_updates'];checks+=3
            bits=x<128
            rk=rank(bits[1:257]^bits[0])
            record=dict(case_id=r['case_id'],backend=r['backend'],xor_difference_rank=rk,columns=x.shape[1])
            if r['backend']=='lfsr32_shared64':
                parity=np.bitwise_xor.reduce(bits[:,support],axis=1)
                expected=len(support)%2
                assert np.all(parity==expected);assert rk<=32;checks+=2
                record.update(parity_support_lanes=support,expected_parity=expected,
                              frames_satisfying_relation=int(np.sum(parity==expected)))
            if r['duplicate_seed']:
                assert np.array_equal(x,y);checks+=1
            rows.append(record)
    out=dict(arithmetic_and_structure_checks=checks,raw_files=len(result['cases']),
        source_files=len(manifest),gf_relation=support,rows=rows,
        note='GF relation follows exact mapping; ranks of other streams are diagnostics, not proof of independence',
        audit_script_sha256=sha(__file__),results_sha256=sha(a.results/'RESULTS.json'))
    (a.results/'AUDIT.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in out.items() if k!='rows'}))

if __name__=='__main__':main()
