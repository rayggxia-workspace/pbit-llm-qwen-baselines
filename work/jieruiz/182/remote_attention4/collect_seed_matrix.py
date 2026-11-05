"""Collect four added seeds and verify the paired seed0 records without rerun."""
import argparse,hashlib,json,os,statistics,tarfile,time
from pathlib import Path


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def save(p,v):
    Path(p).write_bytes((json.dumps(v,indent=2,sort_keys=True)+'\n').encode())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True)
    ap.add_argument('--array',required=True);a=ap.parse_args()
    previous=a.job.parent/'execution_7e44b6a4'
    out=a.job/('collection_'+os.environ['SLURM_JOB_ID']);out.mkdir(exist_ok=False)
    m=json.loads((a.job/'source/work/jieruiz/182/SOURCE_MANIFEST.json').read_text())
    old=json.loads((previous/'source/work/jieruiz/182/SOURCE_MANIFEST.json').read_text())
    for rel,e in m['files'].items():assert sha(a.job/'source'/rel)==e['sha256'],rel
    module_paths=[p for p in m['files'] if p.startswith('architecture_tlm/')]
    for p in module_paths:
        assert m['files'][p]['sha256']==old['files'][p]['sha256']==sha(previous/'source'/p),p
    submission=json.loads((a.job/'ARRAY_SUBMISSION.json').read_text())
    plan=[(a.job,a.array,i,p['case'],p['seed'],True) for i,p in enumerate(submission['plan'])]
    plan += [(previous,'2913',9,'balanced_screen_pv',0,False),
             (previous,'2913',10,'balanced_screen_rejection',0,False)]
    rows,errors,raw,small=[],[],[],[]
    for job,array,i,case,seed,download in plan:
        suffix=('_seed'+str(seed)) if download else ''
        d=job/'results'/(array+'_'+str(i)+'_'+case+suffix)
        row=dict(case=case,seed=seed,remote_directory=str(d),array_task=array+'_'+str(i))
        try:
            mf=json.loads((d/'MANIFEST.json').read_text())
            assert mf['status']=='completed' and mf['case']==case
            for name,e in mf['files'].items():
                f=d/name
                assert f.stat().st_size==e['bytes'] and sha(f)==e['sha256'],name
                raw.append(dict(path=str(f),bytes=f.stat().st_size,sha256=e['sha256'],case=case,seed=seed))
            r=json.loads((d/'RESULT.json').read_text());config=r['config'];dram=r['DRAM']['details']
            assert config['seed']==seed and config['random']['backend']=='integrated_service'
            assert r['model']['num_hidden_layers']==36 and r['FFN_activity']['SC_64x64_tiles']==656640
            assert config['digital_weight_chunk_bytes']==65536
            assert dram['configuration_sha256']=='ddbdd1aee7f20d5e3eaf12d73b7e300894ad3ab5cc50ae2a8aa5fd121b2fa419'
            bursts=sum(v for k,v in r['DRAM']['traffic'].items() if k.endswith('_bursts'))
            assert dram['status']=='finished' and bursts==dram['burst_count']==dram['read_bursts']+dram['write_bursts']
            assert r['execution_commit']==(m if download else old)['commit']
            row.update(status='verified',source_commit=r['execution_commit'],result_sha256=sha(d/'RESULT.json'),
                manifest_sha256=sha(d/'MANIFEST.json'),wall_seconds=r['wall_seconds'],metrics=r['metrics'],
                energy_J=r['energy_J'],phase_ns=r['phase_ns'],DRAM_traffic=r['DRAM']['traffic'],
                FFN_activity=r['FFN_activity'],attention_activity=r['attention_activity'])
            if download:small += [d/'RESULT.json',d/'EXECUTION.json',d/'MANIFEST.json']
        except Exception as e:
            row.update(status='incomplete_or_failed',error=type(e).__name__+': '+str(e));errors.append(row)
        rows.append(row)
    aggregate=[]
    for case in ('balanced_screen_pv','balanced_screen_rejection'):
        subset=sorted([r for r in rows if r['case']==case and r['status']=='verified'],key=lambda r:r['seed'])
        if [r['seed'] for r in subset]==[0,1,2]:
            values=[r['metrics']['TPOT_ms'] for r in subset]
            energy=[r['energy_J']['external_DRAMPower_core'] for r in subset]
            aggregate.append(dict(case=case,seeds=[0,1,2],TPOT_ms=values,
                TPOT_mean_ms=statistics.mean(values),TPOT_sample_stdev_ms=statistics.stdev(values),
                DRAM_core_J=energy,DRAM_core_mean_J=statistics.mean(energy),DRAM_core_sample_stdev_J=statistics.stdev(energy),
                scope='three-seed synthetic full-decode timing/traffic; not task quality or measured power'))
    save(out/'SUMMARY.json',rows);save(out/'THREE_SEED_AGGREGATE.json',aggregate);save(out/'RAW_REMOTE_INDEX.json',raw)
    verification=dict(verified=sum(r['status']=='verified' for r in rows),expected=6,new_seed_cases_expected=4,
        errors=errors,architecture_files_identical=len(module_paths),source_commit=m['commit'],seed0_source_commit=old['commit'],
        collector_job=os.environ['SLURM_JOB_ID'],array_job=a.array,
        completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        scope='actual DRAMSys/SystemC synthetic model schedule; unknown full chip PPA/PPL remains null',
        raw_trace_policy='all request traces remain on remote; raw byte SHA in RAW_REMOTE_INDEX.json')
    save(out/'VERIFICATION.json',verification)
    small += [p for p in (a.job/'logs').glob('seeds-'+a.array+'_*.out')]
    small += [p for p in (a.job/'logs').glob('seeds-'+a.array+'_*.err')]
    small += [a.job/n for n in ('ARRAY_SUBMISSION.json','MODULE_IDENTITY.json','RESOURCE_CHECK.json',
        'RUNTIME_PROVENANCE.json','seed_matrix.sbatch','collect_seed_matrix.py','COLLECTOR_SUBMISSION.json')]
    small += [a.job/'source/work/jieruiz/182/SOURCE_MANIFEST.json']
    small += [out/n for n in ('SUMMARY.json','THREE_SEED_AGGREGATE.json','RAW_REMOTE_INDEX.json','VERIFICATION.json')]
    index={str(p.relative_to(a.job)):dict(remote_path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in small}
    save(out/'SMALL_EVIDENCE_INDEX.json',index);small.append(out/'SMALL_EVIDENCE_INDEX.json')
    package=out/'SMALL_EVIDENCE.tar.gz'
    with tarfile.open(package,'w:gz') as tf:
        for p in small:tf.add(p,arcname=str(p.relative_to(a.job)),recursive=False)
    receipt=dict(package=str(package),bytes=package.stat().st_size,sha256=sha(package),verified=verification['verified'],expected=6)
    save(out/'PACKAGE_RECEIPT.json',receipt);print(json.dumps(receipt),flush=True)
    if errors:raise SystemExit(2)


if __name__=='__main__':main()
