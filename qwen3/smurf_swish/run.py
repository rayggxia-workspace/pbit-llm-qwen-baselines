"""Run frozen function probes locally; bounded CPU experiment, no GPU/model."""
import hashlib,json,platform,subprocess,time
from pathlib import Path
import numpy as np
import scipy
from scipy.special import expit
from core import fit,stationary,moments,simulate,target

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'qwen3/results/smurf_swish_20261024'


def digest(b):return hashlib.sha256(b).hexdigest()
def save(p,obj):
    with p.open('w',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def metrics(y,truth):
    delta=y-truth[:,None]
    return dict(mae=float(np.abs(delta).mean()),rmse=float(np.sqrt((delta**2).mean())),
                mean_curve_mae=float(np.abs(y.mean(1)-truth).mean()),
                p95_abs_error=float(np.quantile(np.abs(delta),.95)),
                point_mean=y.mean(1).tolist(),point_variance=y.var(1).tolist())


def experiment(codes,q,t,seeds,trials,init='mid',mode='iid',scale=1,sign=1):
    ys=[];rhos=[];byseed=[]
    truth=target(q/256,scale,sign)
    for seed in seeds:
        y,rho=simulate(codes,q,t,seed,trials,init,mode)
        byseed.append({k:v for k,v in metrics(y,truth).items() if not k.startswith('point_')})
        ys.append(y);rhos.append(rho)
    y=np.concatenate(ys,axis=1)
    out=metrics(y,truth)
    out.update(seed_metrics=byseed,lag1_pearson_mean=float(np.mean(rhos)))
    if mode=='iid':
        mean,var=moments(codes,q,t,init)
        out.update(exact_finite_mean_mae=float(np.abs(mean-truth).mean()),
                   exact_finite_rmse=float(np.sqrt((var+(mean-truth)**2).mean())),
                   measured_vs_exact_mean_rmse=float(np.sqrt(((y.mean(1)-mean)**2).mean())),
                   exact_mean=mean.tolist())
    return out


def main():
    start=time.time();config=json.loads((HERE/'config.json').read_text())
    # Freeze source before producing scored data; do not silently score dirty code.
    source_files=['core.py','run.py','test_core.py','config.json']
    rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    for f in source_files:
        b=(HERE/f).read_bytes()
        committed=subprocess.check_output(['git','show',rev+':qwen3/smurf_swish/'+f],cwd=ROOT)
        assert b==committed, 'Unfrozen source: '+f
    OUT.mkdir(parents=True,exist_ok=True)
    q=np.arange(257);seeds=config['seeds'];trials=config['trials_per_seed']
    rows=[];coeffs=[]
    for n in config['states']:
        codes,raw=fit(n)
        coeffs.append(dict(family='paper_positive',states=n,scale=1,sign=1,codes=codes.tolist(),unquantized=raw.tolist()))
        for t in config['cycles']:
            r=dict(family='paper_positive',states=n,cycles=t,init='mid',mode='iid',scale=1,sign=1,
                   stationary_mae=float(np.abs(stationary(q/256,n)@(codes/256)-target(q/256)).mean()))
            r.update(experiment(codes,q,t,seeds,trials));rows.append(r)
            print(n,t,r['mae'],r['exact_finite_mean_mae'],flush=True)
    codes,_=fit(4)
    for init,mode in [('zero','iid'),('top','iid'),('mid','ordered32'),('mid','shuffle32')]:
        r=dict(family='sensitivity',states=4,cycles=64,init=init,mode=mode,scale=1,sign=1)
        r.update(experiment(codes,q,64,seeds,trials,init,mode));rows.append(r)
    # Same stochastic arithmetic without an FSM, sigmoid table generated offline.
    for t in config['cycles']:
        truth=target(q/256);prob=np.rint(expit(q/256)*256).astype(np.int16)
        ys=[]
        for seed in seeds:
            a,b=np.random.SeedSequence(seed).spawn(2)
            a=np.random.default_rng(a);b=np.random.default_rng(b)
            counts=np.zeros((q.size,trials),dtype=np.int16)
            for _ in range(t):
                counts+=(a.integers(0,256,size=counts.shape,dtype=np.int16)<q[:,None]) & (b.integers(0,256,size=counts.shape,dtype=np.int16)<prob[:,None])
            ys.append(counts/t)
        r=dict(family='two_stream_AND_LUT',states=0,cycles=t,scale=1,sign=1,mode='iid',init='none')
        r.update(metrics(np.concatenate(ys,axis=1),truth));rows.append(r)
    q2=np.arange(0,257,2)
    for n in config['extension_states']:
        for scale in config['signed_scale_extension']:
            for sign in (-1,1):
                codes,raw=fit(n,scale,sign)
                coeffs.append(dict(family='signed_scale',states=n,scale=scale,sign=sign,codes=codes.tolist(),unquantized=raw.tolist()))
                r=dict(family='signed_scale',states=n,cycles=64,init='mid',mode='iid',scale=scale,sign=sign)
                r.update(experiment(codes,q2,64,seeds,config['extension_trials_per_seed'],scale=scale,sign=sign))
                r['mae_original_units']=scale*r['mae'];rows.append(r)
        print('scale extension',n,'done',flush=True)
    interface=dict(w8_planes_checked='test_core.py signed sum',
                   example_w=2,example_x_probability=.5,
                   silu_of_mean=float(expit(1)),mean_of_per_clock_silu=float(expit(2)),
                   conclusion='Weighted sum must precede nonlinearity; ordinary FSM expects normalized single-bit input.')
    result=dict(status='completed',source_commit=rev,config=config,rows=rows,coefficients=coeffs,
                interface=interface,environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform()),
                runtime_seconds=time.time()-start)
    save(OUT/'RESULTS.json',result)
    save(OUT/'MANIFEST.json',dict(status='completed',source_commit=rev,model='N/A function probe',data='synthetic q=0..256 grid',
         source_sha256={f:digest((HERE/f).read_bytes()) for f in source_files},
         inputs_sha256=digest(np.arange(257,dtype='<u2').tobytes()),
         documents={'RESULTS.json':digest((OUT/'RESULTS.json').read_bytes())}))
    print('completed',len(rows),'configurations',result['runtime_seconds'],flush=True)

if __name__=='__main__':main()
