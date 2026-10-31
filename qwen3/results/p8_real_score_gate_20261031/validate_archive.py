from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import csv,hashlib,importlib.util,io,json,statistics,tarfile
import numpy as np
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--source-dir',type=Path,required=True);args=ap.parse_args()
archive=args.archive;digest='278aaed9d321dae6c57b427091fc52bfc4a45c3a8ae441cc9674fb89ef8726a0'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==digest
with tarfile.open(archive) as t:
 assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in t.getmembers())
 raw={m.name:t.extractfile(m).read() for m in t.getmembers()}
prefix='results/de13b021a375/';read=lambda p:json.loads(raw[p]);complete=read(prefix+'complete.json');assert complete['status']=='completed'
for n,h in complete['files'].items():assert hashlib.sha256(raw[prefix+n]).hexdigest()==h,n
sealed=0
for path,data in raw.items():
 if path.startswith(prefix) and path.endswith('.json'):
  assert hashlib.sha256(data).hexdigest()==raw[path+'.sha256'].decode().strip();sealed+=1
audit=read(prefix+'AUDIT.json');assert audit['status']=='completed' and len(audit['rows'])==1152 and len(audit['literal_R8_checks'])==12
prov=read(prefix+'provenance.json');assert prov['source']['source_commit']=='de13b021a375d5492e54190c54c28b70d8cc9005'
spec=importlib.util.spec_from_file_location('p8gate',args.source_dir/'numeric_gate.py');numeric=importlib.util.module_from_spec(spec);spec.loader.exec_module(numeric)
assert hashlib.sha256((args.source_dir/'numeric_gate.py').read_bytes()).hexdigest()==prov['source']['files_sha256']['experiments/p8_real_score_gate_20261031/numeric_gate.py']
table=json.loads((args.source_dir/'NUMERIC_TABLES.json').read_bytes());groups=[]
for corpus in ['train','test']:
 gate=read(prefix+corpus+'_GATE.json');assert gate['native_logits_unchanged'] and gate['model_parameters_unchanged'] and gate['all_36_layers']
 assert gate['reference']['tokens_per_layer']==gate['diagnostic']['tokens_per_layer']==[8]*36
 assert gate['reference']['logits_sha256']==gate['diagnostic']['logits_sha256']
 assert gate['reference']['nll_sum']==gate['diagnostic']['nll_sum']
 for mode in ['full','K256']:
  name=corpus+'_'+mode;source=read(prefix+name+'.json');npz=np.load(io.BytesIO(raw[prefix+name+'.npz']),allow_pickle=False)
  assert source['npz_sha256']==hashlib.sha256(raw[prefix+name+'.npz']).hexdigest()
  rows=[r for r in audit['rows'] if r['corpus']==corpus and r['mode']==mode]
  assert len(rows)==288 and {r['layer'] for r in rows}==set(range(36))
  assert {(r['layer'],r['kv_head']) for r in rows}=={(layer,kv) for layer in range(36) for kv in range(8)}
  for i,r in enumerate(rows):
   assert r['candidates']==(2048 if mode=='full' else 256)
   v,_,hist,_=numeric.expected(npz['scores'][i],table['sigmoid_lut'],table['rejection_m_ln2_F4'])
   assert np.max(abs(hist-npz['expected_histogram'][i]))<1e-10
   assert abs(v['expected_trials_uncapped']-r['expected_trials_uncapped'])<1e-7
  for i,metric in enumerate(source['global_metric_names']):
   assert abs(npz['global_metrics'][:,i].mean()-audit['all_head_summary'][name][metric]['mean'])<1e-12
  ntrials=sum(r['capped_MC']['replicas'] for r in rows);failed=sum(r['capped_MC']['failed'] for r in rows)
  assert ntrials==27648 and failed==0
  g=audit['groups'][name];global_summary=audit['all_head_summary'][name]
  group=dict(corpus=corpus,mode=mode,all_head_rows=9216,CR_audit_rows=288,MC_runs=ntrials,MC_failed=failed,
   mean_trials_uncapped=statistics.mean(r['expected_trials_uncapped'] for r in rows),
   max_mean_trials_uncapped=max(r['expected_trials_uncapped'] for r in rows),
   global_zeroed_mass_mean=global_summary['zeroed_softmax_mass']['mean'],global_zeroed_mass_p95=global_summary['zeroed_softmax_mass']['p95'],
   global_P8_odds_TV_mean=global_summary['P8_odds_tv']['mean'],global_P8_expected_V_relative_L2_mean=global_summary['P8_expected_V_relative_L2']['mean'],
   CR_mean_hist_TV_softmax=statistics.mean(r['mean_histogram_tv_vs_softmax'] for r in rows),
   CR_mean_hist_TV_P8odds=statistics.mean(r['mean_histogram_tv_vs_P8_odds'] for r in rows),
   CR_uncapped_expected_V_relative_L2=statistics.mean(r['CR_uncapped_expected_V_relative_L2'] for r in rows),
   target_reference_mean=statistics.mean(r['target_reference_probability'] for r in rows),
   CR_expected_reference_mean=statistics.mean(r['expected_reference_fraction_uncapped'] for r in rows),
   MC_reference_mean=statistics.mean(r['capped_MC']['reference_fraction_completed'] for r in rows))
  groups.append(group)
print(json.dumps(dict(status='passed',sealed_json=sealed,rows_recomputed=1152,MC_runs=110592,failed_MC_runs=0)))
