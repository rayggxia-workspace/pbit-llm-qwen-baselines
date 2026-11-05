"""Replay frozen OR4 events; measure prefix range and streaming saturation error.

Numerical derivation only. No new model inference, RTL, synthesis or PT.
"""
from pathlib import Path
import hashlib,json,math,subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
SRC=ROOT/'architecture_tlm/matrix_single_scale_20261028'
SEEDS=(17,503,1009);N=64;T=32;PL=8
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def unpack(line,n,b,signed=False):
 v=int(line,16);out=[(v>>(i*b))&((1<<b)-1) for i in range(n)]
 return np.array([x-(1<<b) if signed and x>=(1<<(b-1)) else x for x in out],dtype=np.int64)
def read(path,n,b,signed=False):return np.stack([unpack(s,n,b,signed) for s in path.read_text().splitlines()])
def load(kind):
 records=[];inputs=[]
 for m in (1,8):
  for seed in SEEDS:
   p=SRC/kind/('m%d_s%d'%(m,seed))
   for name in ('w8.hex','x8.hex','samples.hex','expect3.hex','metrics.json'):
    f=p/name;inputs.append({'path':f.relative_to(ROOT).as_posix(),'sha256':sha(f)})
   w=read(p/'w8.hex',m*N,8,True).reshape(-1,m,N);x=read(p/'x8.hex',N,8,True)
   events=read(p/'samples.hex',N,1).reshape(-1,T,N).astype(bool)
   expected=read(p/'expect3.hex',m,32,True);metrics=json.loads((p/'metrics.json').read_text())
   for f in range(len(w)):
    effective=w[f]*np.where(x[f]<0,-1,1)[None,:]
    planes=((np.abs(effective)[:,:,None]>>np.arange(PL))&1).astype(bool)
    pos=planes&(effective[:,:,None]>0);neg=planes&(effective[:,:,None]<0)
    b=events[f][:,None,:,None]
    gp=(b&pos[None,:,:,:]).reshape(T,m,16,4,PL).any(3)
    gn=(b&neg[None,:,:,:]).reshape(T,m,16,4,PL).any(3)
    delta=gp.sum(2,dtype=np.int64)-gn.sum(2,dtype=np.int64)
    cp=np.cumsum(gp.sum(2,dtype=np.int64),axis=0);cn=np.cumsum(gn.sum(2,dtype=np.int64),axis=0)
    prefix=np.cumsum(delta,axis=0);recovered=prefix[-1]@(1<<np.arange(PL))
    assert np.array_equal(recovered,expected[f]),'Independent replay must equal frozen OR oracle'
    for j in range(m):
     q=metrics[f*m+j]
     assert recovered[j]==q['OR4']
     records.append({'M':m,'seed':seed,'frame':f,'output':j,'name':q['name'],
      'delta':delta[:,j,:],'prefix':prefix[:,j,:],'positive':cp[:,j,:],'negative':cn[:,j,:],
      'weight_density':planes[j].mean(0),'OR':int(recovered[j]),'event_exact':q['event_exact'],'target':q['SC_expected']})
 return records,inputs
def array(records,k):return np.stack([r[k] for r in records])
def rms(x):return float(np.sqrt(np.mean(np.asarray(x,dtype=np.float64)**2)))
def replay(records,widths,wrap=False,final_only=False):
 d=array(records,'delta');state=np.zeros((len(records),PL),dtype=np.int64);touched=np.zeros_like(state,dtype=bool);steps=0
 widths=np.array(widths);lo=-(1<<np.maximum(widths-1,0));hi=(1<<np.maximum(widths-1,0))-1
 if final_only:
  raw=d.sum(1);state=np.maximum(lo,np.minimum(hi,raw));touched=(state!=raw);steps=int(touched.sum())
 else:
  for t in range(T):
   raw=state+d[:,t,:];hit=((raw<lo)|(raw>hi))&(widths>0);touched|=hit;steps+=int(hit.sum())
   state=((raw-lo)%(1<<widths)+lo) if wrap else np.maximum(lo,np.minimum(hi,raw))
   state[:,widths==0]=0
 state[:,widths==0]=0
 y=state@(1<<np.arange(PL));ref=np.array([r['OR'] for r in records]);exact=np.array([r['event_exact'] for r in records]);target=np.array([r['target'] for r in records]);err=y-ref
 return {'counter_bits':sum(int(v) for v in widths),'widths_low_to_high':[int(v) for v in widths],
  'outputs':len(records),'extra_RMSE_raw':rms(err),'extra_NRMSE_vs_OR_RMS':rms(err)/max(rms(ref),1e-30),
  'extra_NRMSE_vs_exact_event_RMS':rms(err)/max(rms(exact),1e-30),'extra_bias_raw':float(err.mean()),
  'max_abs_extra_error':int(np.abs(err).max()),'changed_output_fraction':float(np.mean(err!=0)),
  'saturation_steps_all_planes':steps,'outputs_touching_limit_fraction':float(touched.any(1).mean()),
  'total_NRMSE_vs_exact_event_RMS':rms(y-exact)/max(rms(exact),1e-30),
  'total_NRMSE_vs_quantized_target_RMS':rms(y-target)/max(rms(target),1e-30)}
def statistics(records):
 c=array(records,'prefix');final=c[:,-1,:];p=array(records,'positive');n=array(records,'negative');out=[]
 den=rms([r['OR'] for r in records]);density=array(records,'weight_density')
 for bit in range(PL):
  a=np.abs(final[:,bit]);peak=np.abs(c[:,:,bit]).max(1)
  out.append({'plane':bit,'bit_weight':1<<bit,'outputs':len(records),'weight_bit_one_fraction':float(density[:,bit].mean()),
   'positive_count_mean':float(p[:,-1,bit].mean()),'negative_count_mean':float(n[:,-1,bit].mean()),
   'signed_count_mean':float(final[:,bit].mean()),'abs_count_mean':float(a.mean()),
   'abs_final_p50':float(np.quantile(a,.5)),'abs_final_p95':float(np.quantile(a,.95)),'abs_final_p99':float(np.quantile(a,.99)),
   'final_min':int(final[:,bit].min()),'final_max':int(final[:,bit].max()),'max_abs_prefix':int(peak.max()),
   'single_plane_drop_extra_NRMSE_vs_OR_RMS':rms(final[:,bit]*(1<<bit))/max(den,1e-30),
   'signed_width_prefix_overflow_fraction':{str(b):float(((c[:,:,bit]<-(1<<(b-1)))|(c[:,:,bit]>(1<<(b-1))-1)).any(1).mean()) for b in (6,7,8,9,10)}})
 return out
def greedy(records,budget):
 d=array(records,'delta');weights=1<<np.arange(PL);ref=np.array([r['OR'] for r in records]);cache={}
 for bit in range(PL):
  for b in range(5,12):
   state=np.zeros(len(records),dtype=np.int64)
   for t in range(T):state=np.clip(state+d[:,t,bit],-(1<<(b-1)),(1<<(b-1))-1)
   cache[bit,b]=state*weights[bit]
 widths=[11]*PL
 def error(v):return rms(sum(cache[i,b] for i,b in enumerate(v))-ref)/max(rms(ref),1e-30)
 while True:
  opts=[]
  for i,b in enumerate(widths):
   if b>5:
    v=widths.copy();v[i]-=1;opts.append((error(v),i,v))
  if not opts:break
  e,i,v=min(opts)
  if e>budget:break
  widths=v
 return widths
def main():
 power,pi=load('power_fixtures');functional,fi=load('fixtures')
 result={'scope':'NUMERICAL_DERIVATION_ONLY; frozen synthetic events, no new model/RTL/PPA; counted samples across implementations are not independent trials',
  'parent_source_commit':'5dcef4fd99200418f804cbd51f3bf325d1cbea60','N':N,'T':T,'OR_group':4,'seeds':SEEDS,
  'baseline':'signed11 per magnitude plane, all 8 planes, positive/negative ORs separately then signed popcount difference',
  'datasets':{},'candidates':{},'calibration':{}}
 profiles={'power_all':power,'power_M8':[r for r in power if r['M']==8],
  'functional_all':functional,'functional_nonstress':[r for r in functional if r['name'] not in ('positive_limit','negative_limit','shared_half','independent_half','cancel')]}
 for key,records in profiles.items():result['datasets'][key]={'outputs':len(records),'planes':statistics(records)}
 candidates={'exact11':[11]*PL,'sat10':[10]*PL,'sat9':[9]*PL,'sat8':[8]*PL,'sat7':[7]*PL,
  'sat9_top7':[9]*7+[7], 'drop_low1_sat9_top7':[0]+[9]*6+[7],
  'mixed_6_7_8_8_9_9_9_7':[6,7,8,8,9,9,9,7], 'mixed_7_7_8_8_9_9_9_7':[7,7,8,8,9,9,9,7]}
 for k in (1,2,3):candidates['drop_low%d_sat9'%k]=[0]*k+[9]*(PL-k)
 for name,widths in candidates.items():result['candidates'][name]={k:replay(v,widths) for k,v in profiles.items()}
 result['candidates']['wrap8']={k:replay(v,[8]*PL,wrap=True) for k,v in profiles.items()}
 result['candidates']['final_clip8_only']={k:replay(v,[8]*PL,final_only=True) for k,v in profiles.items()}
 cal=[r for r in power if r['M']==8 and r['seed']!=1009];holdout=[r for r in power if r['M']==8 and r['seed']==1009]
 for budget in (.01,.02,.05):
  widths=greedy(cal,budget);result['calibration'][str(budget)]={'criterion':'greedy synthetic calibration only, not globally optimal or a model-quality threshold','calibration_seeds':[17,503],
   'holdout_seed':1009,'calibration':replay(cal,widths),'heldout':replay(holdout,widths),'functional':replay(functional,widths)}
 # Two end-to-end arithmetic distinctions that otherwise conceal overflow bugs.
 assert replay(power,[11]*PL)['max_abs_extra_error']==0
 assert replay(functional,[11]*PL)['max_abs_extra_error']==0
 assert replay(functional,[10]*PL)['max_abs_extra_error']<=255
 # Streaming saturation cannot be replaced by final-only clipping when signs cancel.
 v=0
 for d in [16]*16+[-16]*16:v=max(-128,min(127,v+d))
 assert v==-128 and sum([16]*16+[-16]*16)==0
 assert ((128+128)%256)-128==-128  # signed8 wrap changes sign
 assert 32*(1//4)==0 and sum([1]*32)//4==8  # per-cycle LSB removal loses carries
 result['arithmetic_checks']={'oracle_replay':'864 outputs PASS','signed10_global_endpoint_proof':'For t<=31, |C(t)|<=496; at t32 only +512 exceeds signed10 by one. Per-plane count error<=1; reconstructed raw error<=255.',
  'signed8_cancellation_example':{'deltas':'16 times +16, then 16 times -16','exact_final':0,'stream_saturated_final':-128,'final_only_clip':0},
  'wrap_example':{'signed8_exact':128,'saturated':127,'wrapped':-128},'per_cycle_LSB_drop_example':'32 increments of1, each floor-divided by4 gives0; summing before division gives8'}
 save(HERE/'RESULTS.json',result)
 inputs=pi+fi;manifest={'source_script_sha256':sha(Path(__file__)),'inputs':inputs,
  'outputs':{'RESULTS.json':sha(HERE/'RESULTS.json')},'numpy_version':np.__version__,
  'command':'python architecture_tlm/matrix_counter_precision_20261028/analyze.py'}
 save(HERE/'MANIFEST.json',manifest)
 print('VERIFIED_REPLAY',len(power),'power outputs,',len(functional),'functional outputs')
 for x in result['datasets']['power_M8']['planes']:
  print('PLANE',x['plane'],'meanabs',round(x['abs_count_mean'],2),'p99',round(x['abs_final_p99'],2),'range',x['final_min'],x['final_max'],'peak',x['max_abs_prefix'])
 for name,items in result['candidates'].items():
  q=items['power_M8'];print(name,q['counter_bits'],'NRMSE',round(q['extra_NRMSE_vs_OR_RMS'],6),'changed',round(q['changed_output_fraction'],6),'touch',round(q['outputs_touching_limit_fraction'],6))
 for name,q in result['calibration'].items():print('FIT',name,q['calibration']['widths_low_to_high'],'heldout_NRMSE',q['heldout']['extra_NRMSE_vs_OR_RMS'])
if __name__=='__main__':main()
