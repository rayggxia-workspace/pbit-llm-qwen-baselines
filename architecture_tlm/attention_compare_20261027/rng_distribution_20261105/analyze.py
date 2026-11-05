from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import numpy as np
import json,hashlib,itertools
P=Path(__file__).resolve().parent;R=P.parents[2];WS=R.parents[1];A=WS/'project_archives/attention_rng198_20261105'
def save(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
rows=json.loads((A/'rows_private.json').read_bytes());manifest=json.loads((A/'INPUT_MANIFEST.json').read_bytes());modes=manifest['modes']
def transition(p):
 # Gaussian quadrature integrates the degree N-2 polynomial exactly (roundoff aside).
 x,w=np.polynomial.legendre.leggauss((len(p)+1)//2);x=(x+1)/2;w=w/2
 f=1-p[None,:]+x[:,None]*p[None,:];prod=f.prod(axis=1);iv=1/f
 integral=(iv.T*(w*prod))@iv
 t=(1-p[:,None])*p[None,:]*integral;np.fill_diagonal(t,0);np.fill_diagonal(t,1-t.sum(axis=1));return t
def enumerate_transition(p,shared=False):
 n=len(p);t=np.zeros((n,n))
 events=[]
 if shared:
  cuts=sorted(set([0.,1.]+list(p)))
  for lo,hi in zip(cuts,cuts[1:]):events.append((p>((lo+hi)/2),hi-lo))
 else:
  for mask in itertools.product([False,True],repeat=n):
   bits=np.array(mask);events.append((bits,np.where(bits,p,1-p).prod()))
 for bits,prob in events:
  ix=np.flatnonzero(bits)
  for i in range(n):
   if bits[i] or not len(ix):t[i,i]+=prob
   else:t[i,ix]+=prob/len(ix)
 return t
p=np.array([.125,.25,.375,.5]);small=transition(p);assert np.max(abs(small-enumerate_transition(p)))<1e-13
assert np.allclose(enumerate_transition(np.full(4,.5),True),np.eye(4))
finite=[];checks=[]
for r in rows:
 p=np.array(r['threshold'])/256;pi=np.array(r['pi_p8']);t=transition(p)
 residual=float(np.max(abs(pi@t-pi)));assert residual<1e-13 and t.min()>-1e-13
 d=np.eye(128)[0];acc=np.zeros(128);means={}
 for s in range(1,257):
  d=d@t;acc+=d
  if s in [16,32,64,128,256]:means[s]=acc.copy()/s
 finite.append(means);checks.append(residual)
expected=json.loads((A/'verify_expected.json').read_bytes());actual=[[v[0]]+list(map(int,v[1:])) for v in (x.split() for x in (A/'verify_out.txt').read_text().splitlines())];assert actual==expected
summary={'scope':manifest['scope'],'modes':modes,'validation':dict(gf_basis_random=133,bivium_states=278,archived_contexts=24,archived_queries=288,archived_outputs=18432,exact_smallN_transition=True,stationarity_max_residual=max(checks)), 'short':[],'long':[],'synthetic':[]}
details=[]
for phase in ['short','long']:
 meta=np.loadtxt(A/(phase+'_meta.tsv'),delimiter='\t',skiprows=1,dtype=np.int64)
 hist=np.memmap(A/(phase+'_hist.bin'),dtype='<u4',mode='r',shape=(len(meta),128))
 assert np.all(hist.sum(axis=1)==meta[:,3])
 S=[16,32,64,128,256] if phase=='short' else [32768]
 for mode in range(7):
  for s in S:
   ds=[]
   for ri,r in enumerate(rows):
    idx=np.flatnonzero((meta[:,0]==mode)&(meta[:,1]==ri)&(meta[:,3]==s))
    if not len(idx):continue
    h=np.array(hist[idx],dtype=np.float64)/s;pool=h.mean(axis=0);pi=np.array(r['pi_p8']);sm=np.array(r['softmax']);ref=finite[ri][s] if phase=='short' else pi
    maximum=np.array(r['threshold'])==max(r['threshold'])
    d=dict(phase=phase,mode=modes[mode],row=r['id'],kind=r['kind'],S=s,reps=len(idx),pooled_TV_p8=float(abs(pool-pi).sum()/2),pooled_TV_softmax=float(abs(pool-sm).sum()/2),pooled_TV_IID_expected=float(abs(pool-ref).sum()/2),mean_single_TV_p8=float(np.mean(abs(h-pi).sum(axis=1)/2)),mean_L2_squared_p8=float(np.mean(((h-pi)**2).sum(axis=1))),max_threshold_mass=float(pool[maximum].sum()),target_max_mass=float(pi[maximum].sum()),unique_mean=float(meta[idx,4].mean()),switch_rate=float(meta[idx,5].mean()/s),empty_rate=float(meta[idx,6].mean()/s),active_mean=float(meta[idx,7].mean()/s),zero_switch_fraction=float(np.mean(meta[idx,5]==0)),init_bias_IID_TV=float(abs(ref-pi).sum()/2))
    ds.append(d);details.append(d)
    if r['kind']=='synthetic' and s in [64,32768]:summary['synthetic'].append(d)
   real=[d for d in ds if d['kind']=='captured']
   metrics=['pooled_TV_p8','pooled_TV_softmax','pooled_TV_IID_expected','mean_single_TV_p8','mean_L2_squared_p8','max_threshold_mass','target_max_mass','unique_mean','switch_rate','empty_rate','active_mean','zero_switch_fraction','init_bias_IID_TV']
   aggregate=dict(mode=modes[mode],S=s,rows=len(real),reps=real[0]['reps'])
   for k in metrics:aggregate[k]=float(np.mean([d[k] for d in real]))
   summary[phase].append(aggregate)
 # Binary sizes are part of the conservation check.
 assert (A/(phase+'_hist.bin')).stat().st_size==len(meta)*128*4
 del hist
# Mixing diagnostics on score and top-one occupancy, never integer token IDs.
meta=np.loadtxt(A/'long_meta.tsv',delimiter='\t',skiprows=1,dtype=np.int64)
seq=np.memmap(A/'long_seq.bin',dtype='u1',mode='r',shape=(len(meta),32768));ess=[]
def effective(x):
 x=x-x.mean();v=np.dot(x,x)
 if v<1e-20:return None
 n=len(x);f=np.fft.rfft(x,2*n);ac=np.fft.irfft(f*f.conjugate(),2*n)[:n]/v
 pair=ac[1:4095:2]+ac[2:4096:2];stop=np.flatnonzero(pair<=0);pair=pair[:stop[0]] if len(stop) else pair
 pair=np.minimum.accumulate(pair);tau=max(1.,1+2*pair.sum());return float(n/tau)
for mode in range(7):
 values=[];constant=0
 for k in np.flatnonzero((meta[:,0]==mode)&(meta[:,1]>=6)):
  r=rows[meta[k,1]];z=np.array(r['logits']);x=(seq[k]==int(np.argmax(z))).astype(float);v=effective(x)
  if v is None:constant+=1
  else:values.append(v)
 ess.append(dict(mode=modes[mode],top1_indicator_ESS_median=None if not values else float(np.median(values)),constant_chains=constant,total_chains=int(np.sum((meta[:,0]==mode)&(meta[:,1]>=6))),warning='Single-chain diagnostic only; biased/reducible sources cannot be validated by ESS.'))
summary['mixing']=ess
summary['quantization_TV_mean']=float(np.mean([abs(np.array(r['pi_p8'])-r['softmax']).sum()/2 for r in rows[6:]]))
save(A/'DETAILS_PRIVATE.json',details);save(P/'SUMMARY.json',summary)
save(P/'VALIDATION.json',dict(status='pass',**summary['validation'],short_query_runs=7*102*128,long_chains=7*12*8,short_snapshot_conservation=True,physical_TRNG='not_run',fresh_BF16_PPL='not_applicable_offline_score_replay',actual_PV='not_run_missing_V',synthesis='not_run',timing='not_run',power='not_run'))
print(json.dumps(dict(short64=[d for d in summary['short'] if d['S']==64],long=summary['long'],mixing=ess,quantization_TV_mean=summary['quantization_TV_mean']),indent=2))
