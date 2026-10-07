from concurrent.futures import ThreadPoolExecutor
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from metrics import METHODS


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',default='screen',choices=('screen','distill','adaptive','moment'));args=ap.parse_args()
    assert json.loads(Path('results/kernel_checks.json').read_text())['status']=='passed'
    mem=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.used','--format=csv,noheader,nounits'],text=True)
    gpus=[int(s.split(',')[0]) for s in mem.splitlines() if int(s.split(',')[1])<500];assert gpus
    if os.environ.get('ROUTER_GPUS'):gpus=[g for g in gpus if str(g) in os.environ['ROUTER_GPUS'].split(',')]
    assert gpus
    jobs=[]
    for ctx,ex,batch in ((2048,32,16),(8192,16,4)):
        base={'context':ctx,'examples':ex,'batch':batch,'decode':128}
        if args.stage=='screen':jobs.append({**base,'mode':'sdpa','ratio':.15,'selection':'stochastic','seed':0})
        methods=METHODS if args.stage=='screen' else (('mean_sigmoid','max2','max4','mix') if args.stage=='adaptive' else (('max2','max4') if args.stage=='moment' else ('distill',)))
        for method in methods:
            for budget in (.15,.3):
                for selection in ((args.stage,) if args.stage in ('adaptive','moment') else ('stochastic','deterministic')):
                    if method=='mean_softmax' and selection=='deterministic':continue
                    for seed in ((0,1,2) if selection!='deterministic' else (0,)):
                        jobs.append({**base,'mode':method,'ratio':budget,'selection':selection,'seed':seed})
    out=Path('results')/args.stage;out.mkdir(exist_ok=True)
    Path(f'results/{args.stage}_protocol.json').write_text(json.dumps({'jobs':jobs,'gpus':gpus,'FFN':'original frozen','budget':'stochastic validation-matched expectation, not guaranteed test count; deterministic fixed count','started':time.time()},indent=2))
    def worker(gpu,queue):
        for j in queue:
            name=f"ctx{j['context']}_{j['mode']}_budget{j['ratio']}_{j['selection']}_seed{j['seed']}";dest=out/(name+'.json')
            if dest.exists():continue
            cmd=[sys.executable,'experiments/router_metrics/evaluate.py']
            for k,v in j.items():cmd.extend(['--'+k,str(v)])
            cmd.extend(['--output',str(dest)])
            with (out/(name+'.log')).open('w') as log:
                subprocess.run(cmd,env={**os.environ,'CUDA_VISIBLE_DEVICES':str(gpu),'OMP_NUM_THREADS':'4','TOKENIZERS_PARALLELISM':'false'},stdout=log,stderr=subprocess.STDOUT,check=True)
            print(name,flush=True)
    with ThreadPoolExecutor(max_workers=len(gpus)) as pool:
        futures=[pool.submit(worker,g,jobs[i::len(gpus)]) for i,g in enumerate(gpus)]
        for f in futures:f.result()
    Path(f'results/{args.stage}_status.json').write_text(json.dumps({'status':'complete','runs':len(jobs),'finished':time.time()}))


if __name__=='__main__':main()
