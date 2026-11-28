"""Run immutable compiled RTL images and archive small receipts, not waveforms."""
from pathlib import Path
import argparse, hashlib, json, subprocess, time
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true')
    a=p.parse_args();out=ROOT/'results';logs=out/'run';logs.mkdir(exist_ok=True)
    runs=[];matrix=[]
    for kind in ['state','prompt','matrix']:
        build=out/('build_'+kind);receipt=json.loads((build/'BUILD.json').read_text())
        for name,digest in receipt['source_sha256'].items():
            if sha(Path(name))!=digest:raise RuntimeError('Build/source drift: '+name)
        exe=build/(kind+'_sim.exe')
        settings=[]
        for seed in ([17] if a.quick else [17,29,43]):
            if kind=='state':settings.extend([[seed,st,same] for st in [0,1] for same in [0,1,2]])
            elif kind=='prompt':settings.append([seed])
            else:settings.extend([[seed,st,0] for st in [0,1]])
        if kind=='matrix':settings.extend([[17,1,1],[17,0,2]])
        for args in settings:
            stem=kind+'_'+'_'.join(map(str,args));cmd=[str(exe)]+list(map(str,args))
            start=time.time();r=subprocess.run(cmd,capture_output=True,timeout=1200)
            path=logs/(stem+'.log');path.write_bytes(r.stdout+r.stderr)
            entry={'kind':kind,'arguments':args,'command':cmd,'returncode':r.returncode,
                   'seconds':time.time()-start,'log':str(path.relative_to(ROOT)),
                   'log_sha256':sha(path),'log_bytes':path.stat().st_size,
                   'executable_sha256':sha(exe),'executable_bytes':exe.stat().st_size,
                   'build_receipt_sha256':sha(build/'BUILD.json')}
            runs.append(entry);print(stem,r.returncode,round(entry['seconds'],3),flush=True)
            (out/'RUN_MANIFEST.json').write_text(json.dumps({'runs':runs},indent=2)+'\n',encoding='utf-8')
            if r.returncode:raise RuntimeError(path.read_text(errors='replace')[-6000:])
            if kind=='matrix':matrix.extend(json.loads(line) for line in r.stdout.decode().splitlines() if line.startswith('{'))
        for name,digest in receipt['source_sha256'].items():
            if sha(Path(name))!=digest:raise RuntimeError('Source changed during regression: '+name)
    cases=sum(13 if r['kind']=='prompt' else 1 if r['kind']=='state' else 0 for r in runs)+len(matrix)
    result={'status':'RTL_FUNCTIONAL_AND_CYCLE_PASS','full_prefill_model':False,
            'synthesis':False,'sta':False,'power':False,'runs':len(runs),'checks':cases,
            'seeds':[17] if a.quick else [17,29,43],'matrix_cases':matrix}
    (out/'RESULTS.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('PASS',len(runs),'processes',cases,'checks',flush=True)

if __name__=='__main__':main()
