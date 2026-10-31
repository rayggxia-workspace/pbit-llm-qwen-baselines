"""Slurm-only frozen-native Qwen score gate; no training or fallback."""
import argparse,hashlib,importlib.util,json,os,sys,time
from pathlib import Path
import numpy as np
from numeric_gate import expected,event_law,capped_mc,unit,literal_check

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def seal(p,v):
 p=Path(p);assert not p.exists(),p
 p.parent.mkdir(parents=True,exist_ok=True)
 data=(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode();p.write_bytes(data)
 p.with_suffix(p.suffix+'.sha256').write_text(hashlib.sha256(data).hexdigest()+'\n')
def load(p):
 p=Path(p);assert sha(p)==p.with_suffix(p.suffix+'.sha256').read_text().strip()
 return json.loads(p.read_bytes())
def summary(x):
 x=np.asarray(x,dtype=np.float64)
 return dict(n=int(x.size),mean=float(x.mean()),median=float(np.median(x)),p05=float(np.quantile(x,.05)),p95=float(np.quantile(x,.95)),max=float(x.max()))

def extract(root,cfg,source,lut,m_table):
 import torch
 from transformers import AutoTokenizer,AutoModelForCausalLM
 from transformers.integrations import sdpa_attention as sdpa
 dep=Path(cfg['dependency_source']);sys.path.insert(0,str(dep))
 from experiments.sparq_ising_20261028.vendor.support import verify_files,check_config
 from experiments.sparq_ising_20261028.vendor.plans import ids_sha256
 from experiments.sparq_ising_20261028.scoring import score
 from experiments.sparq_ising_20261028.core import select,Config
 assert torch.cuda.device_count()==1
 torch.set_num_threads(4);torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 prep=json.loads(Path(cfg['prepared']).read_bytes());verify_files(prep);assert prep['model']==cfg['model']
 for name,digest in cfg['data_sha256'].items():assert sha(Path(cfg['data_root'])/name)==digest
 old_manifest=json.loads((dep/'execution.json').read_bytes());assert old_manifest['commit']=='a7108f8cba2c72ad319114af34557f4cec2b793d'
 for rel,digest in old_manifest['files_sha256'].items():assert sha(dep/rel)==digest,rel
 tokenizer=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True,trust_remote_code=False)
 model=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,trust_remote_code=False,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval()
 check_config(model.config,cfg['model']);unchanged=[(p,p._version,p.data_ptr()) for p in model.parameters()]
 out=root/'results'/source['source_id'];out.mkdir(parents=True,exist_ok=True)
 tables=torch.tensor(lut,device='cuda',dtype=torch.int64)
 seal(out/'provenance.json',dict(status='prepared',source=source,dependency_commit=old_manifest['commit'],dependency_manifest_sha256=sha(dep/'execution.json'),
   prepared_sha256=sha(cfg['prepared']),model=cfg['model'],model_files=prep['files'],data_sha256=cfg['data_sha256'],
   runtime_config_sha256=sha(root/'runtime.json'),gpu=torch.cuda.get_device_name(),slurm_job=os.environ['SLURM_JOB_ID'],
   numpy=np.__version__,torch=torch.__version__,sampling_contract='PR221@33c7e688 finite S12F4/U8F4/P8; independent candidates',
   scope='native BF16 Qwen frozen; native Attention/FFN; diagnostic only; not model PPL/full WT2/training/PPA'))
 for corpus,name in [('train','wiki.train.raw'),('test','wiki.test.raw')]:
  ids=tokenizer((Path(cfg['data_root'])/name).read_bytes().decode(),return_tensors='pt',add_special_tokens=False).input_ids[0]
  token_sha=ids_sha256(ids.tolist())
  if corpus=='test':assert token_sha==prep['test_token_ids_sha256_le_int64']
  global_arrays={k:[] for k in ['full','K256']};details={k:[] for k in global_arrays};zs={k:[] for k in global_arrays};hs={k:[] for k in global_arrays};laws={k:[] for k in global_arrays}
  layers=[];old=sdpa.sdpa_attention_forward
  def hook(module,q,k,v,*args,**kwargs):
   result=old(module,q,k,v,*args,**kwargs)
   if q.shape[2]!=1:return result
   layer=module.layer_idx;assert layer==len(layers);layers.append(layer)
   b,hq,_,d=q.shape;h,n=k.shape[1:3];g=hq//h
   assert (b,hq,h,n,d)==(8,32,8,2048,128)
   Q=q.float().reshape(b,h,g,d);K=k.float();V=v.float();Z=(Q/(d**.5))@K.transpose(-1,-2)
   chosen,zero=select(Q,K,Config(k=256,mode='exact'));assert not bool(zero.any())
   selected_z=Z.gather(-1,chosen[:,:,None,:].expand(b,h,g,256));selected_v=V.gather(2,chosen[:,:,:,None].expand(b,h,256,d))
   full_prob=Z.softmax(-1)
   for label,z,value in [('full',Z,V),('K256',selected_z,selected_v)]:
    raw=torch.round(z*16);code=raw.clamp(-2048,2047).long();gap=code.amax(-1,keepdim=True)-code
    threshold=tables[gap.clamp_max(255)];p=threshold.float()/256.;odds=p/(1-p);pi=odds/odds.sum(-1,keepdim=True)
    target=z.softmax(-1);exact=target@value;approx=pi@value
    mass=target.masked_fill(threshold!=0,0).sum(-1)
    retained=torch.ones_like(mass) if label=='full' else full_prob.gather(-1,chosen[:,:,None,:].expand(b,h,g,256)).sum(-1)
    metrics=torch.stack([mass,.5*(pi-target).abs().sum(-1),((approx-exact).square().sum(-1)/exact.square().sum(-1).clamp_min(1e-30)).sqrt(),
       -(target*target.clamp_min(1e-30).log()).sum(-1),target.amax(-1),(threshold>0).sum(-1).float(),retained,
       (raw!=code).float().mean(-1),(gap>255).float().mean(-1)],-1)
    global_arrays[label].append(metrics.reshape(-1,9).double().cpu().numpy())
    # Fixed one Q head per KV group, one query per layer; not selected by score.
    example=layer%8;offset=layer%4
    zrow=z[example,:,offset].double().cpu().numpy();vrow=value[example].double().cpu().numpy()
    for kv in range(8):
     stat,law,hist,target64=expected(zrow[kv],lut,m_table,128,vrow[kv])
     stat.update(corpus=corpus,mode=label,layer=layer,query_example=example,q_head=4*kv+offset,kv_head=kv,
       score_sha256=hashlib.sha256(zrow[kv].tobytes()).hexdigest(),value_sha256=hashlib.sha256(vrow[kv].tobytes()).hexdigest())
     details[label].append(stat);zs[label].append(zrow[kv]);hs[label].append(hist)
     laws[label].append(np.stack([law[x] for x in ['p0','p1','reference']],-1))
   print('CAPTURE',corpus,layer,flush=True)
   return result
  options=dict(context=2048,decode=1,examples=8,batch=8,native=True,capture=True)
  before=score(model,ids,None,**options)
  # The pinned matched wrapper resolves the module attribute at dispatch time;
  # native Qwen caches a registry function and bypasses that attribute hook.
  # Compare the instrumented wrapper against the original native output below.
  options['native']=False
  sdpa.sdpa_attention_forward=hook
  try:after=score(model,ids,None,**options)
  finally:sdpa.sdpa_attention_forward=old
  assert layers==list(range(36)),('capture_coverage',layers)
  assert before['logits_sha256']==after['logits_sha256'] and before['nll_sum']==after['nll_sum'],('native_wrapper_mismatch',before['nll_sum'],after['nll_sum'])
  assert all(p._version==ver and p.data_ptr()==ptr for p,ver,ptr in unchanged)
  assert before['tokens_per_layer']==after['tokens_per_layer']==[8]*36
  for label in ['full','K256']:
   path=out/f'{corpus}_{label}.npz';assert not path.exists()
   np.savez_compressed(path,global_metrics=np.concatenate(global_arrays[label]),scores=np.stack(zs[label]),expected_histogram=np.stack(hs[label]),event_classes=np.stack(laws[label]))
   seal(out/f'{corpus}_{label}.json',dict(status='completed',corpus=corpus,mode=label,npz_sha256=sha(path),
      global_metric_names=['zeroed_softmax_mass','P8_odds_tv','P8_expected_V_relative_L2','entropy','pmax','nonzero_thresholds','retained_full_mass','score_saturated_fraction','gap_saturated_fraction'],
      all_head_rows=8*36*32,selected_audit_rows=len(details[label]),rows=details[label]))
  seal(out/f'{corpus}_GATE.json',dict(status='completed',native_logits_unchanged=True,matched_native_wrapper=True,model_parameters_unchanged=True,
      all_36_layers=True,rows_per_mode=9216,audit_rows_per_mode=288,token_ids_sha256=token_sha,
      data_sha256=cfg['data_sha256'][name],reference=before,diagnostic=after,warning='8 target query diagnostic, not model PPL; test already observed in earlier budget work'))
 seal(out/'EXTRACT_COMPLETED.json',dict(status='completed',files={p.name:sha(p) for p in out.iterdir() if p.suffix in ['.json','.npz'] and p.name!='EXTRACT_COMPLETED.json'}))

def analyze(root,source,lut,m_table):
 out=root/'results'/source['source_id'];done=load(out/'EXTRACT_COMPLETED.json')
 for rel,digest in done['files'].items():assert sha(out/rel)==digest,rel
 laws=[];entries=[];global_summary={};literal=[]
 for corpus in ['train','test']:
  assert load(out/f'{corpus}_GATE.json')['native_logits_unchanged']
  for mode in ['full','K256']:
   raw=np.load(out/f'{corpus}_{mode}.npz',allow_pickle=False);info=load(out/f'{corpus}_{mode}.json')
   assert sha(out/f'{corpus}_{mode}.npz')==info['npz_sha256']
   assert raw['global_metrics'].shape==(9216,9) and len(info['rows'])==288
   global_summary[corpus+'_'+mode]={name:summary(raw['global_metrics'][:,i]) for i,name in enumerate(info['global_metric_names'])}
   for row,stat in enumerate(info['rows']):
    check,law,hist,target=expected(raw['scores'][row],lut,m_table)
    assert np.max(abs(hist-raw['expected_histogram'][row]))<1e-10
    assert abs(check['expected_trials_uncapped']-stat['expected_trials_uncapped'])<1e-7
    assert np.max(abs(np.stack([law[x] for x in ['p0','p1','reference']],-1)-raw['event_classes'][row]))<1e-12
    laws.append(law);entries.append(stat)
    if row in (0,144,287):literal.append(dict(corpus=corpus,mode=mode,row=row,checks=literal_check(raw['scores'][row],lut,m_table,22031+len(literal))))
   print('VERIFIED',corpus,mode,flush=True)
 mc,byseed=capped_mc(laws,S=128,replicas=32,seeds=(101,102,103))
 for row,m in zip(entries,mc):row['capped_MC']=m
 groups={}
 for corpus in ['train','test']:
  for mode in ['full','K256']:
   selected=[r for r in entries if r['corpus']==corpus and r['mode']==mode]
   metrics=['expected_trials_uncapped','expected_reference_fraction_uncapped','target_reference_probability','mean_histogram_tv_vs_softmax','mean_histogram_tv_vs_P8_odds','zeroed_softmax_mass','P8_expected_V_relative_L2','CR_uncapped_expected_V_relative_L2']
   groups[corpus+'_'+mode]=dict(rows=len(selected),statistics={key:summary([r[key] for r in selected]) for key in metrics},
      completion_fraction=float(np.mean([r['capped_MC']['completion_fraction'] for r in selected])),
      rows_with_any_failure=sum(r['capped_MC']['failed']>0 for r in selected),
      rows_with_no_completion=sum(r['capped_MC']['completed']==0 for r in selected),
      rows_expected_trials_above_cap=sum(r['expected_trials_uncapped']>8192 for r in selected))
 seal(out/'AUDIT.json',dict(status='completed',S=128,cap=8192,seed_replicas=byseed,rows=entries,groups=groups,all_head_summary=global_summary,literal_R8_checks=literal,
   scope='same-native-QKV row-level analytic/MC gate, not PPL/training/PPA; uncapped expected histograms are not completed-within-cap results; no failures discarded'))
 seal(out/'complete.json',dict(status='completed',files={p.name:sha(p) for p in out.iterdir() if p.suffix in ['.json','.npz'] and p.name!='complete.json'}))
 print('SUMMARY',json.dumps(groups),flush=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--stage',choices=['unit','extract','analyze'],required=True);a=ap.parse_args()
 assert os.environ.get('SLURM_JOB_ID')
 root=Path(a.root).resolve(strict=True);assert root.parent==Path.home()/'projects' and root.stat().st_uid==os.getuid()
 source_path=Path(__file__).resolve().parents[2];source=json.loads((source_path/'execution.json').read_bytes())
 for rel,digest in source['files_sha256'].items():assert sha(source_path/rel)==digest,rel
 cfg=json.loads((root/'runtime.json').read_bytes());out=root/'results'/source['source_id'];out.mkdir(parents=True,exist_ok=True)
 table=json.loads((Path(__file__).parent/'NUMERIC_TABLES.json').read_bytes());lut=table['sigmoid_lut'];m_table=table['rejection_m_ln2_F4']
 if a.stage=='unit':
  result=unit(lut,m_table)
  spec=importlib.util.spec_from_file_location('old_audit',Path(__file__).parent/'p8_rejection_audit.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
  for n in [128,256,2048]:
   ours,_,_,_=expected(np.zeros(n),lut,m_table);prior=old.uniform_rejection(n)
   for key in ['expected_trials_uncapped','expected_reference_fraction_uncapped']:assert abs(ours[key]-prior[key])<1e-7,(n,key)
  result.update(old_uniform_three_N_crosscheck=True,source_commit=source['source_commit'])
  seal(out/'UNIT.json',result);print('UNIT_PASS',flush=True)
 else:
  assert load(out/'UNIT.json')['status']=='passed'
  if a.stage=='extract':extract(root,cfg,source,lut,m_table)
  else:analyze(root,source,lut,m_table)

if __name__=='__main__':main()
