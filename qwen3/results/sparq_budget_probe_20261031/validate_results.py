from pathlib import Path
import csv,hashlib,io,json,math,statistics,struct,tarfile
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
archive=args.archive
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='d8bec56cafd920f02e6223b03208974711bc3e52f15b1a6de475a77b10f9ba4e'
with tarfile.open(archive) as t:
    assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in t.getmembers())
    files={m.name:t.extractfile(m).read() for m in t.getmembers()}
read=lambda n:json.loads(files[n])
prefix='results/8c0748c2a130/'
verified=0
for phase,seed in [('preflight',0),('short',0),('short',1),('short',2)]:
    folder=f'{prefix}{phase}/seed{seed}/'; done=read(folder+'complete.json')
    assert done['status']=='completed'
    for name,digest in done['files'].items():
        assert hashlib.sha256(files[folder+name]).hexdigest()==digest
    for name in [folder+'complete.json']+[folder+x for x in done['files']]:
        assert hashlib.sha256(files[name]).hexdigest()==files[name+'.sha256'].decode().strip()
        verified+=1
gate=read(prefix+'preflight/seed0/GATE.json');assert gate['passed'] and gate['native_wrapper_bitwise']
rows=[];plans=set();models=set();quant=[];provenance=[]
for seed in range(3):
    folder=f'{prefix}short/seed{seed}/';prov=read(folder+'provenance.json');provenance.append(prov)
    assert prov['runtime_config_sha256']=='c20dfbe48b64f144f4b5096afbda83fba70a960b009372bdb8cbf9bd724b4df8'
    for name in read(folder+'complete.json')['files']:
        if name in ('provenance.json','RETENTION.json'):continue
        record=read(folder+name);assert record['status']=='completed' and record['seed']==seed and record['scored_tokens']==512 and record['original_ffn']
        assert record['provenance_sha256']==hashlib.sha256(files[folder+'provenance.json']).hexdigest()
        assert abs(math.exp(record['nll_sum']/512)-record['perplexity'])<1e-10
        assert sum(w['scored_tokens'] for w in record['records'])==512
        assert abs(sum(w['nll_sum'] for w in record['records'])-record['nll_sum'])<1e-9
        positions=[i for w in record['records'] for i in range(w['first_target'],w['last_target_exclusive'])]
        psha=hashlib.sha256(struct.pack('<'+'q'*len(positions),*positions)).hexdigest()
        assert psha==record['plan']['target_positions_sha256_le_int64']
        assert len(positions)==len(set(positions))==512
        plans.add(psha);models.add(record['token_ids_sha256'])
        if record['case']!='BF16':assert record['tokens_per_layer']==[512]*36
        layers=record['audit']['layers'];cfg=record['config']
        assert not layers or set(layers)==set(map(str,range(36)))
        assert all(l['zero_fallback']==0 for l in layers.values())
        activity=[sum(l.get('_activity',[0]*6)[i] for l in layers.values()) for i in range(6)] if layers else [0]*6
        if '_WH_' in record['case']:
            head_rows=512*32*36
            assert activity[0]==head_rows*(32+cfg['samples']) and activity[1]==head_rows*cfg['samples']
            assert record['audit']['ideal_sigmoid_source'] is False
        metrics=record['p8_metrics']
        row=dict(case=record['case'],seed=seed,ppl=record['perplexity'],nll_sum=record['nll_sum'],targets=512,
            k=cfg['k'] if cfg else None,samples=cfg['samples'] if cfg and cfg['mode']!='exact' else None,
            proposals=activity[0],addresses=activity[1],
            mean_unique_v_per_kv_group=sum(l['_unique_v'] for l in layers.values())/(512*8*36) if layers and all('_unique_v' in l for l in layers.values()) else None,
            source_result_sha256=hashlib.sha256(files[folder+name]).hexdigest(),source_result=folder+name,
            quant_metrics=metrics)
        rows.append(row)
assert len(rows)==25 and len(plans)==len(models)==1
assert all(p['model']==provenance[0]['model'] and p['model_files']==provenance[0]['model_files'] and p['token_sha256']==provenance[0]['token_sha256'] for p in provenance)
bycase={}
for r in rows:bycase.setdefault(r['case'],[]).append(r)
assert {r['ppl'] for r in bycase['BF16']}=={14.116850631757018}
ref=bycase['K128_exact'][0]['ppl'];bf=bycase['BF16'][0]['ppl']
aggregates=[]
for name,group in bycase.items():
    v=[r['ppl'] for r in group]; mean=statistics.mean(v)
    aggregates.append(dict(case=name,seeds=[r['seed'] for r in group],ppl_mean=mean,ppl_sample_sd=statistics.stdev(v) if len(v)>1 else None,
        change_vs_k128_exact_pct=(mean/ref-1)*100,change_vs_bf16_pct=(mean/bf-1)*100,
        mean_unique_v_per_kv_group=statistics.mean([r['mean_unique_v_per_kv_group'] for r in group]) if group[0]['mean_unique_v_per_kv_group'] is not None else None))
ret=read(prefix+'short/seed0/RETENTION.json');assert ret['diagnostic_does_not_change_logits']
for k,summary in ret['by_k'].items():
    for field in ('mass','relative_error'):assert len(ret['raw'][k][field])==9216
    assert abs(statistics.mean(ret['raw'][k]['mass'])-summary['mean_retained_mass'])<1e-12
summary=dict(schema='sparq-p8-budget-probe-summary-v1',status='COMPLETED_SHORT_PILOT_NOT_FULL_WT2',issue=222,
    source_commit='8c0748c2a130b452fdccfb1bfa9a62f8b4f5bec5',dependency_commit=provenance[0]['dependency_commit'],
    archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),archive_bytes=archive.stat().st_size,
    archive_members=len(files),verified_sealed_json=verified,slurm_preflight=3554,slurm_array=3555,slurm_seeds=[0,1,2],
    accounting='sacct unavailable on this host; completion based on sealed completed JSON, not inferred queue exit',
    model=provenance[0]['model'],model_files=provenance[0]['model_files'],prepared_sha256=provenance[0]['prepared_sha256'],
    data_sha256=provenance[0]['data_sha256'],token_ids_sha256=next(iter(models)),target_positions_sha256=next(iter(plans)),
    runtime_config_sha256=provenance[0]['runtime_config_sha256'],environment=provenance[0]['environment'],gpu=provenance[0]['gpu'],
    protocol='8 fixed WT2 suffix windows, context2048..2111, 64 targets/window, 512 targets; all36 decode layers; native BF16 FFN/projections; exact prefill; no chat template',
    gate=gate,retention=ret['by_k'],aggregates=aggregates,individual_results=rows,
    recommendation=dict(k=128,samples=[32,64,128],baseline_samples=128,burn=32,spacing=1,
        note='S64 practical compromise, S32 aggressive training candidate; original ten-case manifest unchanged pending budget handoff decision; no new training'),
    limitations=['not full WT2','test subset observed for budget tuning','not task accuracy','only winner-hold budget measured; CR/Gibbs budgets not inferred',
        'independent Philox R8-equivalent law, not measured shared/physical RNG','unique V logical addresses, not DRAM transactions','no RTL/ASIC PPA or clocks inferred'])
out=args.output;out.mkdir(parents=True,exist_ok=True)
(out/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
with (out/'RESULTS.csv').open('w',encoding='utf-8',newline='') as f:
    fields=list(aggregates[0]);w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(aggregates)
print(json.dumps(dict(status='passed',sealed_json=verified,results=len(rows),aggregates=aggregates,retention=ret['by_k'],p8_mean_diagnostic=bycase['K128_P8_mean'][0]['quant_metrics']),ensure_ascii=False,indent=2))

if __name__=='__main__':pass
