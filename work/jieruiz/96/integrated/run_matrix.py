"""Immutable, full-model 52-case x two-backend comparison. CPU only."""
import argparse
import concurrent.futures
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from architecture_tlm.unified_v6.config import load
from architecture_tlm.unified_v6.model import FullDecode
from architecture_tlm.unified_v6.run import source_record,write,compact


def run_one(spec,folder):
    start=time.monotonic()
    cfg,shape=load(spec['model'])
    cfg.update(context_tokens=spec['context'],seed=spec['seed'],trace_event_limit=12,row_receipt_limit=4)
    cfg['ffn']['mode']=spec['ffn'];cfg['attention']['mode']=spec['attention']
    cfg['random']['backend']=spec['backend'];cfg['random']['clock_hz']=cfg['core_hz']
    identity='{model}_L{context}_seed{seed}_{ffn}_{attention}_{backend}'.format(**spec)
    result=FullDecode(cfg,shape).run()
    result['execution_commit']=spec['execution_commit']
    result['config_sha256']=hashlib.sha256(json.dumps(cfg,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    path=Path(folder)/spec['model']/(identity+'.json');path.parent.mkdir(exist_ok=True)
    write(path,result)
    row=compact(spec['model'],spec['context'],spec['seed'],spec['ffn'],spec['attention'],result)
    row.update(backend=spec['backend'],wall_seconds=time.monotonic()-start,
        path=path.relative_to(folder).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
    return row


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=6)
    a=p.parse_args()
    if a.output.exists():raise ValueError('new output directory required')
    sources=source_record()
    if not 1<=a.workers<=6:raise ValueError('bounded CPU parallelism1..6')
    modes=[('bf16','exact'),('w8','exact'),('sc','exact'),('sc','pv'),('sc','screen_exact'),
           ('sc','screen_pv'),('sc','screen_rejection'),('sc','screen_winner')]
    specs=[]
    for context in [2048,8192]:
        for seed in [0,1,2]:
            for ffn,attn in modes:
                for backend in ['local_prng_interface','integrated_service']:
                    specs.append(dict(model='qwen',context=context,seed=seed,ffn=ffn,attention=attn,backend=backend))
    for model in ['llama1','llama2']:
        for ffn,attn in [('bf16','exact'),('sc','pv')]:
            for backend in ['local_prng_interface','integrated_service']:
                specs.append(dict(model=model,context=2048,seed=0,ffn=ffn,attention=attn,backend=backend))
    # Long jobs start first, making per-case completion a useful progress signal.
    specs.sort(key=lambda s:(s['backend']=='integrated_service',s['attention']=='screen_winner',
                             s['context'],s['attention']=='screen_rejection'),reverse=True)
    for s in specs:s['execution_commit']=sources['commit']
    a.output.mkdir(parents=True)
    write(a.output/'EXECUTION.json',sources)
    write(a.output/'PLAN.json',dict(cases=specs,workers=a.workers,case_count=len(specs),
        physical_clock='source=compute100MHz; SRAM80MHz remains independently constrained',
        scope='complete synthetic decoder scheduling, no weights/PPL/new circuit simulation'))
    rows=[];failures=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        pending={pool.submit(run_one,s,str(a.output)):s for s in specs}
        for future in concurrent.futures.as_completed(pending):
            s=pending[future]
            try:
                row=future.result();rows.append(row)
                write(a.output/('DONE_%03d.json'%len(rows)),row)
                print(json.dumps(dict(completed=len(rows),total=len(specs),case=row['path'],
                    TPOT_ms=row['TPOT_ms'],wall_seconds=round(row['wall_seconds'],2))),flush=True)
            except Exception as exc:
                failure=dict(case=s,error=repr(exc));failures.append(failure)
                write(a.output/('FAILED_%03d.json'%len(failures)),failure)
                print(json.dumps(dict(failed=failure)),flush=True)
    write(a.output/'SUMMARY.json',dict(rows=rows,failures=failures,complete=len(rows)==len(specs),
        numerical_warning='real PRNG/q256 changes sampled addresses; differences are not pure timing overhead',
        energy_warning='calibrated native endpoint subtotal only, full system and full random energy/area unknown'))
    manifest={p.relative_to(a.output).as_posix():dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in a.output.rglob('*') if p.is_file()}
    write(a.output/'ARTIFACT_MANIFEST.json',manifest)
    return int(bool(failures))


if __name__=='__main__':sys.exit(main())
