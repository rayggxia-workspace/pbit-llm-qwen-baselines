"""Saved-score p-bit drive study. No model run, PPL or physical device claim."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from field_quant import FORMATS,limits,quantize_field,accepted_law
from rejection_sampler import rejection_indices

CAPTURE_SHA='2b6c5d851f761fc3d9749e02c9f438db6180afa4e17915f45a3d56ac8d7cb740'
PERCENTILES=[0,.1,1,5,25,50,75,95,99,99.9,100]


def distribution(values):
    x=np.asarray(values);x=x[np.isfinite(x)]
    return dict(count=int(x.size),percentiles={str(p):float(v) for p,v in zip(PERCENTILES,np.percentile(x,PERCENTILES))})


def format_metrics(d,m,f):
    a=d-m*np.log(2.);valid=np.isfinite(d)
    valid[np.arange(len(d)),d.argmax(1)]=False
    target=accepted_law(d,0);q=accepted_law(d,m,quantize_field(a,**f))
    lo,hi=limits(f['bits'],f['step'],f['negative_only'])
    clipped=valid&((a<lo)|(a>hi));tv=np.abs(q-target).sum(1)/2
    return dict(shift=m,mean_row_tv=float(tv.mean()),max_row_tv=float(tv.max()),
        p95_row_tv=float(np.percentile(tv,95)),clipped_site_fraction=float(clipped.sum()/max(1,valid.sum())),
        mean_target_mass_on_clipped_sites=float((target*clipped).sum(1).mean()),
        mean_reference_mass=float(q[np.arange(len(d)),d.argmax(1)].mean()))


def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    before=time.time();capture=Path(args.capture);sha=hashlib.sha256(capture.read_bytes()).hexdigest()
    assert sha==CAPTURE_SHA
    raw=np.load(capture);keys=[f'layer_{i}' for i in range(24)]
    z=np.concatenate([raw[k] for k in keys]).astype(np.float64);d=z-z.max(1)[:,None]
    valid=np.isfinite(d);valid[np.arange(len(d)),d.argmax(1)]=False
    real=np.concatenate([raw[f'layer_{i}'][:14] for i in (0,12,23)]).astype(np.float64)
    rd=real-real.max(1)[:,None]
    exposures=np.zeros((len(real),25),dtype=np.int64)
    edges=np.linspace(-128.,0.,8193);hist=np.zeros(8192,dtype=np.int64)
    n=0;under=0;amin=0.;amax=-np.inf;shift_counts=np.zeros(25,dtype=np.int64)
    def observe(a,v,m,rr):
        nonlocal n,under,amin,amax
        values=a[v];n+=values.size
        if values.size:
            amin=min(amin,float(values.min()));amax=max(amax,float(values.max()))
            under+=int((values < edges[0]).sum());hist[:]+=np.histogram(values,bins=edges)[0]
        np.add.at(exposures,(rr,m),1)
        np.add.at(shift_counts,m,v.sum(1))
    replay=[]
    for seed in [0,1,2]:
        _,stats=rejection_indices(real,64,seed=seed,proposal_observer=observe)
        replay.append(dict(seed=seed,stats=stats))
    quant=[]
    for f in FORMATS:
        # Exact fixed-shift law over all 2688 saved rows; m14 is a stress envelope,
        # not evidence every real row visits that shift.
        stress=[format_metrics(d,m,f) for m in [0,2,4,6,8,10,12,14]]
        # Local conditional-law errors at states visited by the IDEAL replay.
        # These are not the output law of a quantized adaptive trajectory/PPL.
        total=0.;worst=0.;clipped=0;sites=0;mass=0.;count=int(exposures.sum())
        for m in range(25):
            rows=np.flatnonzero(exposures[:,m])
            if not len(rows):continue
            x=rd[rows];a=x-m*np.log(2.);v=np.isfinite(x);v[np.arange(len(x)),x.argmax(1)]=False
            t=accepted_law(x,0);q=accepted_law(x,m,quantize_field(a,**f));tv=abs(q-t).sum(1)/2
            w=exposures[rows,m];lo,hi=limits(f['bits'],f['step'],f['negative_only']);c=v&((a<lo)|(a>hi))
            total+=float(w@tv);worst=max(worst,float(tv.max()))
            clipped+=int(w@c.sum(1));sites+=int(w@v.sum(1));mass+=float(w@((t*c).sum(1)))
        quant.append(dict(format=f,range=limits(f['bits'],f['step'],f['negative_only']),
            observed_ideal_states=dict(mean_local_conditional_tv=total/count,max_local_conditional_tv=worst,
                clipped_site_fraction=clipped/sites,mean_local_target_mass_clipped=mass/count),
            all_saved_rows_fixed_shift_stress=stress))
        print(f['name'],json.dumps(quant[-1]['observed_ideal_states']),flush=True)
    out=dict(issue=78,scope='sigmoid argument only; exact local accepted-law diagnostic, no model PPL/PPA',
        capture_path=str(capture),capture_sha256=sha,capture_shapes={k:list(raw[k].shape) for k in keys},
        capture_limits='first CTMC S64 decode batch; 8 examples x14 heads x24 layers; screened512; original FFN; not fresh BF16 calibration or full WT2',
        formula='a=(z-z_reference)-m*ln(2); correction coin remains 2**(-m)',
        raw_scores=distribution(z),delta_excluding_reference=distribution(d[valid]),
        delta_by_layer={k:distribution((raw[k]-raw[k].max(1)[:,None]).ravel()) for k in keys},
        actual_ideal_replay=dict(rows=42,layers=[0,12,23],heads_per_layer=14,samples=64,seeds=[0,1,2],
            field_min=amin,field_max=amax,field_draws=n,histogram_below_minus128=under,
            histogram_edges=edges.tolist(),histogram_counts=hist.tolist(),shift_site_draw_counts=shift_counts.tolist(),
            row_shift_proposal_exposures=exposures.tolist(),records=replay),
        formats=quant,rounding='nearest even; saturate; invalid sites separately disabled; ideal continuous RNG and sigmoid unchanged',
        local_error_caveat='ideal-trajectory local conditional laws; not an actual quantized adaptive sampler trajectory or model quality result',
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
        elapsed_seconds=time.time()-before)
    with Path(args.output).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(out,f,indent=2,allow_nan=False);f.write('\n')


if __name__=='__main__':main()
