from pathlib import Path
import argparse,hashlib,json,sys

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--trace-root',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--dependency',type=Path,required=True)
    a=ap.parse_args();sys.path.insert(0,str(a.dependency))
    import numpy as np
    from audit import analyze,summarize
    p=a.trace_root/'RESULT.json';raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==p.with_suffix('.sha256').read_text().strip()
    old=json.loads(raw);assert old['status']=='completed';rows=[]
    assert not a.output.exists();a.output.mkdir(parents=True)
    for t in old['traces']:
        p=a.trace_root/'trace'/t['name'];assert hashlib.sha256(p.read_bytes()).hexdigest()==t['sha256']
        with np.load(p,allow_pickle=False) as z:r=analyze({k:z[k] for k in z.files})
        rows.append(r)
    out=dict(status='completed',source_result_sha256=hashlib.sha256(raw).hexdigest(),cases=len(rows),
             summary=summarize(rows),scope=old['scope'],no_new_model_forward=True)
    raw=(json.dumps(out,indent=2)+'\n').encode();(a.output/'RESULT.json').write_bytes(raw)
    (a.output/'RESULT.sha256').write_text(hashlib.sha256(raw).hexdigest()+'\n')
    print(json.dumps(out))

if __name__=='__main__':main()
