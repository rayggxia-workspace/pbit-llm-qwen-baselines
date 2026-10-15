"""Controlled block-scale extension, separate from the paper-style baseline."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path('results/pbit_qk_block_20261006')
EXP=Path('experiments/pbit_qk_block')


def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(p.suffix+'.tmp'); temp.write_text(json.dumps(obj,indent=2)+'\n'); temp.replace(p)


def main():
    if (ROOT/'protocol.json').exists(): raise RuntimeError('Already launched')
    memory=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.used','--format=csv,noheader,nounits'],text=True)
    gpus=[int(line.split(',')[0]) for line in memory.splitlines() if int(line.split(',')[1])<500]
    if not gpus: raise RuntimeError('No idle GPU')
    jobs=[]
    for ctx,examples,batch in ((2048,32,16),(8192,16,4)):
        for mode in ('sdpa','dense'): jobs.append((ctx,examples,batch,mode,64,4,0))
        for block in (64,16,8):
            for B in (4,8,16,32):
                for seed in (0,1,2): jobs.append((ctx,examples,batch,'stratified',block,B,seed))
    write(ROOT/'protocol.json',{'date':'2026-10-06','scope':'all24 decode QK; original FFNs, dense PV, exact prefill; no training',
        'paper_relation':'block64 recovers previous paper-style baseline; block16/8 are our extension, not original paper method',
        'partition':'contiguous coordinates after RoPE; no feature permutation; scale max(abs(q_block))',
        'blocks':[64,16,8],'samples':[4,8,16,32],'seeds':[0,1,2],
        'hardware_note':'4/8 scales per head instead of 1; separate block score scaling and reduction required; dense reference only',
        'jobs':jobs,'gpus':gpus,'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in EXP.glob('*.py')}})
    write(ROOT/'status.json',{'stage':'testing','total':len(jobs)})
    for script in ('test_sampling.py','test_integration.py'):
        with (ROOT/script.replace('.py','.json')).open('w') as out:
            subprocess.run([sys.executable,str(EXP/script)],check=True,stdout=out,
                env={**os.environ,'CUDA_VISIBLE_DEVICES':str(gpus[0]),'OMP_NUM_THREADS':'4'})
    write(ROOT/'status.json',{'stage':'evaluating','total':len(jobs)})
    def worker(gpu,queue):
        for ctx,examples,batch,mode,block,B,seed in queue:
            name=f'ctx{ctx}_{mode}_g{block}_b{B}_seed{seed}'
            cmd=[sys.executable,str(EXP/'evaluate.py'),'--context',str(ctx),'--examples',str(examples),
                 '--decode','128','--batch',str(batch),'--mode',mode,'--block-size',str(block),
                 '--samples',str(B),'--seed',str(seed),'--output',str(ROOT/'evaluation'/(name+'.json'))]
            write(ROOT/'commands'/(name+'.json'),{'command':cmd,'gpu':gpu})
            write(ROOT/'progress'/(name+'.json'),{'stage':'running','gpu':gpu,'start':time.time()})
            log=ROOT/'logs'/(name+'.log'); log.parent.mkdir(parents=True,exist_ok=True)
            with log.open('w') as out:
                subprocess.run(cmd,check=True,stdout=out,stderr=subprocess.STDOUT,
                    env={**os.environ,'CUDA_VISIBLE_DEVICES':str(gpu),'OMP_NUM_THREADS':'4','TOKENIZERS_PARALLELISM':'false'})
            write(ROOT/'progress'/(name+'.json'),{'stage':'complete','gpu':gpu})
    with ThreadPoolExecutor(max_workers=len(gpus)) as pool:
        fs=[pool.submit(worker,g,jobs[i::len(gpus)]) for i,g in enumerate(gpus)]
        for f in fs: f.result()
    write(ROOT/'status.json',{'stage':'complete','evaluations':len(jobs)})


if __name__=='__main__':
    try: main()
    except Exception as e:
        write(ROOT/'failure.json',{'error':str(e),'time':time.time()})
        raise
