"""Slurm CPU replay, one row per array task; raw errors remain private."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import numpy as np
from samplers import chains,corrected_rejection,distribution,output_metrics

REPO=Path(__file__).resolve().parents[2]
METHODS=[('iid',None,0.,None),('rejection',None,0.,None),
         ('winner0','winner_hold',0.,None),('winner2','winner_hold',2.,None),
         ('winner4','winner_hold',4.,None),('winner0_q8','winner_hold',0.,.125),
         ('two_bits','two_bits',0.,None),('barker','barker',0.,None),
         ('barker_q8','barker',0.,.125),('xor','xor',0.,None)]
GRID=[32,64,128,256,512,1024,2048,4096,8192,16384,32768]


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')


def benchmark_row(z,v,row_id,config):
    repeats=config['repeats_per_seed'];burns=config['burns'];results=[]
    profile=output_metrics(np.zeros((1,1),int),z,v,[0],[1])[1]
    for method_index,(name,kind,shift,drive) in enumerate(METHODS):
        for seed in config['seeds']:
            rng=np.random.default_rng(np.random.SeedSequence([row_id,method_index,seed,20261021]))
            cap=1024 if name=='iid' else 512 if name=='rejection' else config['parallel_output_cap'] if kind=='winner_hold' else config['serial_output_cap']
            budgets=[s for s in GRID if s<=cap];before=time.time()
            if name=='iid':
                ix=rng.choice(len(z),size=(repeats,cap),p=distribution(z));stats=dict(kind='exact_softmax_iid_control')
                used_burns=[0]
            elif name=='rejection':
                ix,stats=corrected_rejection(z,cap,repeats,rng);used_burns=[0]
            else:
                ix,stats=chains(z,cap+max(burns),repeats,rng,kind,shift,drive);used_burns=burns
            curves,_=output_metrics(ix,z,v,used_burns,budgets)
            for c in curves:
                t=c['burn']+c['samples'];s=c['samples']
                if name=='rejection':
                    phases=stats['proposal_phase_at'][:,s-1]
                    c.update(logical_updates_per_repeat=phases.tolist(),pbit_draws_per_repeat=(phases*(len(z)-1)).tolist(),
                        extra_fair_bits_per_repeat=stats['empty_coin_at'][:,s-1].tolist(),rank_calls_per_repeat=[0.]*repeats)
                elif name=='iid':
                    c.update(logical_updates_per_repeat=[s]*repeats,pbit_draws_per_repeat=None,
                             extra_fair_bits_per_repeat=None,rank_calls_per_repeat=None)
                else:
                    c.update(logical_updates_per_repeat=[t]*repeats,
                        pbit_draws_per_repeat=[t*stats['pbit_draws_per_update']]*repeats,
                        extra_fair_bits_per_repeat=stats['fair_bit_prefix'][:,t].tolist(),
                        rank_calls_per_repeat=stats['rank_call_prefix'][:,t].tolist(),
                        switches_per_repeat=stats['switch_prefix'][:,t].tolist())
            results.append(dict(method=name,seed=seed,curves=curves,software_elapsed_seconds=time.time()-before,
                                software_elapsed_is_not_hardware_time=True))
            print(json.dumps(dict(row=row_id,method=name,seed=seed,seconds=time.time()-before)),flush=True)
    # Preserve the old finite-time CTMC as a quality reference, with its own time unit.
    sys.path.insert(0,str(REPO))
    import torch
    torch.set_num_threads(1)
    from experiments.qwen_joint_stratified_attention_20261019.upstream_attention.ctmc import ct_mc_indices
    for seed in config['seeds']:
        for s in (128,512):
            ix,stats=ct_mc_indices(torch.tensor(np.broadcast_to(z,(repeats,len(z))).copy()),s,16.,4.,generator=torch.Generator().manual_seed(20261021+row_id*100+seed))
            curves,_=output_metrics(ix.numpy(),z,v,[0],[s])
            curves[0].update(logical_updates_per_repeat=None,pbit_draws_per_repeat=None,
                extra_fair_bits_per_repeat=None,rank_calls_per_repeat=None,legacy_process_horizon=16+4*s)
            results.append(dict(method='legacy_ctmc',seed=seed,curves=curves,legacy_stats=stats,
                                limitation='dimensionless CTMC time/event compression is not a digital update/clock count'))
    return dict(profile=profile,results=results)


def main():
    p=argparse.ArgumentParser();p.add_argument('--capture-report',required=True);p.add_argument('--output',required=True)
    p.add_argument('--commit',required=True);p.add_argument('--row',type=int,required=True);p.add_argument('--plan',default=str(Path(__file__).with_name('PLAN.json')))
    a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('requires Slurm')
    report=json.loads(Path(a.capture_report).read_text());config=json.loads(Path(a.plan).read_text())
    trace=Path(report['trace']['path']);sha=digest(trace)
    if report['status']!='completed' or sha!=report['trace']['sha256']:raise ValueError('capture SHA/status')
    if not all(w['backbone_bitwise_equal'] and w['last_readout_bitwise_equal'] for w in report['windows']):raise ValueError('capture reference gate')
    row=report['rows'][a.row];rid=row['row_id'];out=Path(a.output)
    if out.exists():raise FileExistsError(out)
    with np.load(trace,allow_pickle=False) as data:
        z=data[rid+'_logits'].astype(np.float64);v=data[rid+'_values'].astype(np.float64)
        if row['pool']=='dense':screen_bias=None
        else:
            full_z=data[rid+'_full_logits'].astype(np.float64);full_v=data[rid+'_full_values'].astype(np.float64)
            full_mu=distribution(full_z)@full_v;candidate_mu=distribution(z)@v
            full_var=float(distribution(full_z)@np.square(full_v-full_mu).sum(1))
            addresses=data[rid+'_addresses'];screen_bias=dict(retained_probability_mass=float(distribution(full_z)[addresses].sum()),
                exact_candidate_to_full_squared_error=float(np.square(candidate_mu-full_mu).sum()),
                normalized_by_full_single_sample_variance=float(np.square(candidate_mu-full_mu).sum()/max(full_var,1e-300)))
    started=time.time();result=benchmark_row(z,v,a.row,config)
    result.update(status='completed',source_commit=a.commit,row=row,candidates=len(z),dimension=v.shape[1],
        capture_report_sha256=digest(a.capture_report),capture_sha256=sha,plan_sha256=digest(a.plan),
        screening_omission_bias=screen_bias,elapsed_seconds=time.time()-started,
        environment=dict(numpy=np.__version__,python=sys.version,slurm_job=os.environ.get('SLURM_JOB_ID'),array_task=os.environ.get('SLURM_ARRAY_TASK_ID')),
        scope='real Qwen QK/V fixed-row ideal response Monte Carlo; not model PPL, physical randomness or PPA')
    out.parent.mkdir(parents=True,exist_ok=True);write(out,result)
    print(json.dumps(dict(status='completed',row=a.row,sha256=digest(out),elapsed_seconds=time.time()-started)),flush=True)


if __name__=='__main__':main()
