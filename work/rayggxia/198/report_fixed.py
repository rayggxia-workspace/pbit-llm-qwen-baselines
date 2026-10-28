"""Verify original result bytes, summarize equal-sized native observations."""
from pathlib import Path
import hashlib,json,statistics,math,shutil
R=Path(__file__).resolve().parents[3];W=Path(__file__).resolve().parent
WS=Path('C:/Users/86134/Documents/a_P_BIT')
A=WS/'project_archives/attention_compare_issue198_20261027/fixedpoint_20261028_v3'
D=R/'experiments/attention_fixedpoint_20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
def avg(rs,k):return statistics.mean(r[k] for r in rs if r[k] is not None)
def aggregate(rs):
    return dict(tensors=len(rs),head_rows=len(rs)*32,invalid_heads=sum(r['invalid_heads'] for r in rs),
        tv_mean=sum(r['tv_mean']*r['valid_heads'] for r in rs if r['tv_mean'] is not None)/sum(r['valid_heads'] for r in rs),tv_max=max(r['tv_max'] for r in rs if r['tv_max'] is not None),
        output_relative_rms_mean=avg(rs,'output_relative_rms'),output_relative_rms_max=max(r['output_relative_rms'] for r in rs if r['output_relative_rms'] is not None),
        output_relative_rms_pooled=math.sqrt(sum(r['error_ss'] for r in rs)/sum(r['ref_ss'] for r in rs)),
        argmax_changes=sum(r['argmax_changes'] for r in rs),clip_fraction=avg(rs,'clip_fraction'),clipped_ref_mass=avg(rs,'clipped_ref_mass'),
        zero_ref_mass=avg(rs,'zero_ref_mass'),endpoint_one_count=sum(r['endpoint_one_count'] for r in rs))
def main():
    coll=json.loads((W/'FIXED3_COLLECTION.json').read_bytes())
    for name,m in coll['files'].items():assert sha(A/name)==m['sha256'] and (A/name).stat().st_size==m['bytes']
    x=json.loads((A/'results/RESULTS.json').read_bytes());prov=json.loads((A/'results/provenance.json').read_bytes())
    for name,h in prov['source']['files_sha256'].items():assert sha(R/name)==h,name
    assert len(x['inputs'])==288 and len(x['native_baseline'])==12 and all(r['equal'] for r in x['native_baseline'])
    names=sorted({r['name'] for r in x['rows']});assert len(names)==62 and len(x['rows'])==62*288
    result={n:aggregate([r for r in x['rows'] if r['name']==n]) for n in names}
    snames=sorted({r['name'] for r in x['samples']});assert len(snames)==10 and len(x['samples'])==10*3*288
    finite={}
    for n in snames:
        vals=[]
        for seed in (0,1,2):
            rs=[r for r in x['samples'] if r['name']==n and r['seed']==seed];assert len(rs)==288
            vals.append(dict(seed=seed,dead_heads=sum(r['dead_heads'] for r in rs),tv_mean=avg(rs,'tv_mean'),output_relative_rms_mean=avg(rs,'output_relative_rms'),
                output_relative_rms_pooled=math.sqrt(sum(r['error_ss'] for r in rs)/sum(r['ref_ss'] for r in rs))))
        finite[n]=dict(seeds=vals,mean={k:statistics.mean(v[k] for v in vals) for k in vals[0] if k!='seed'},
            sample_sd={k:statistics.stdev(v[k] for v in vals) for k in vals[0] if k!='seed'})
    chosen=['bf16','i8_f2','i10_f4','i12_f6','i16_f10','i8_train_pot','gap_u8_f4','i10_f4_gap_u8',
        'bf16_i10_f4','i10_f4_gap_u8_p8','i10_f4_gap_u8_p12','i10_f4_gap_u8_p16','i10_f4_trainref_p16',
        'i8_f1','i10_f3','i11_f4','i12_f5','i12_f4','i14_f7','fp32_i11_f4_gap_u8','bf16_gap_u8_f4',
        'fp32_i11_f4_gap_u8_p8','fp32_i11_f4_gap_u8_p12','fp32_i11_f4_gap_u8_p16','bf16_i11_f4_gap_u8_p16']
    layernames=['bf16','i8_f1','i8_f2','gap_u8_f4','i11_f4','fp32_i11_f4_gap_u8_p12','fp32_i11_f4_gap_u8_p16','i10_f4_trainref_p16']
    bylayer={n:{str(li):aggregate([r for r in x['rows'] if r['name']==n and r['layer']==li]) for li in range(36)} for n in layernames}
    summary=dict(job=prov['job'],source=prov['source'],counts=dict(train_windows=4,test_windows=8,layers=36,heads=32,test_head_rows=9216,
        configurations=62,finite_configurations=10,finite_seeds=3),score_min=min(r['score_min'] for r in x['inputs']),score_max=max(r['score_max'] for r in x['inputs']),
        results=result,finite=finite,bylayer=bylayer,limits=x['limits'],original_results=dict(path=str(A/'results/RESULTS.json'),sha256=sha(A/'results/RESULTS.json'),bytes=(A/'results/RESULTS.json').stat().st_size))
    save(D/'SUMMARY.json',summary)
    for name in ('CALIBRATION.json','provenance.json','COMPLETE.json'):shutil.copyfile(A/'results'/name,D/name)
    save(D/'RAW_INDEX.json',dict(server=json.loads((W/'FIXED3_SOURCE.json').read_bytes())['root'],local=str(A),files=coll['files'],raw_results_in_git=False))
    old=WS/'project_archives/attention_compare_issue198_20261027/fixedpoint_20261028_v2/results/RESULTS.json'
    older=json.loads(old.read_bytes());assert older['inputs']==x['inputs'] and older['native_baseline']==x['native_baseline']
    # Every shared configuration must reproduce exactly; follow-up only widens ranges.
    current={(r['case'],r['layer'],r['name']):r for r in x['rows']}
    assert all(current[(r['case'],r['layer'],r['name'])]==r for r in older['rows'])
    save(D/'REPEAT_CHECK.json',dict(v2_results_sha256=sha(old),same_native_inputs=True,all_13248_shared_rows_identical=True))
    pc=json.loads((A/'results/PPL_COMPLETE.json').read_bytes());assert pc['cases']==14 and pc['targets_per_case']==256
    gate=json.loads((A/'results/PPL_GATE.json').read_bytes());assert gate['native_wrapper_byte_equal'] and gate['lut_entries_verified']==512
    cases=[]
    for p in sorted((A/'results').glob('PPL_*_seed*.json')):
        r=json.loads(p.read_bytes());assert r['tokens_per_layer']==[256]*36
        assert sum(v['scored_tokens'] for v in r['records'])==256
        nll=sum(v['nll_sum'] for v in r['records'])
        assert abs(nll-r['nll_sum'])<1e-9 and abs(math.exp(nll/256)-r['perplexity'])<1e-12
        positions=[i for v in r['records'] for i in range(v['first_target'],v['last_target_exclusive'])]
        assert len(positions)==len(set(positions))==256
        if r['case'] not in ('bf16','sparq_exact'):
            assert all(v['sampled_head_rows']==256*32 for v in r['audit']['layers'].values())
            assert r['audit']['config']['samples']==128 and r['audit']['config']['burn']==32
        cases.append({k:r[k] for k in ('case','seed','perplexity','nll_sum','plan','records','tokens_per_layer','score_quantization','quantized_calls','saturated_score_entries','score_entries')})
    assert len(cases)==14 and all(c['plan']==cases[0]['plan'] for c in cases)
    ps=dict(completion=pc,gate=dict(native_wrapper_byte_equal=True,lut_entries_verified=512),cases=cases,
        aggregate={n:dict(mean=statistics.mean(v),sample_sd=statistics.stdev(v) if len(v)>1 else None,seeds=len(v)) for n,v in pc['variants'].items()})
    save(D/'PPL_SUMMARY.json',ps)
    print(json.dumps({n:result[n] for n in chosen},ensure_ascii=False,indent=2));print('FINITE',json.dumps(finite));print('SCORE_RANGE',summary['score_min'],summary['score_max'])
if __name__=='__main__':main()
