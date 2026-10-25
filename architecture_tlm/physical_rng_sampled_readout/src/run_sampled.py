"""Bounded real MOS timed readout; independent APS1 cases, no array drawing."""
import argparse,json,os,shutil,subprocess,sys,tarfile,threading,time
from pathlib import Path
from datetime import datetime
import engine as e
import execution
import sampled_circuits as circuits
import sampled_metrics as metrics
from pdk_discovery import discover_model
SOURCE=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,v):e.write_json(p,v)
def snapshot(out):
    e.verify_source();out.mkdir(parents=True,exist_ok=False)
    for name in list(load(SOURCE/'package_manifest.json'))+['package_manifest.json']:
        with (out/name).open('xb') as f:f.write((SOURCE/name).read_bytes())
def pack(out):
    out=out.resolve();e.finalize(out);target=out.parent.parent/('sampled_readout_'+out.name+'.tar.gz')
    if target.exists():raise FileExistsError('Preserve original archive')
    part=target.with_name(target.name+'.part')
    with tarfile.open(str(part),'w:gz',compresslevel=1) as tar:
        for name in list(load(out/'result_manifest.json'))+['result_manifest.json']:tar.add(str(out/name),arcname=out.name+'/'+name,recursive=False)
    part.rename(target)
    with (target.parent/(target.name+'.sha256')).open('w',encoding='ascii') as f:f.write(e.digest(target)+'  '+target.name+'\n')
    print('ARCHIVE='+str(target),flush=True)

class Runner:
    def __init__(self,out,model,c,b,exe,pool,hours):
        self.out,self.model,self.c,self.b,self.exe,self.pool=out,model,c,b,exe,pool
        self.rows=[];self.details={};self.lock=threading.Lock();self.deadline=time.monotonic()+hours*3600
    def persist(self,status):
        save(self.out/'summary.json',dict(status=status,cases=self.rows,details=self.details,
            scope='Single continuous core/comparator plus real25MOS channel and timedQ read; no array/MUX or clock tree',
            physical_entropy_certified=False,power_integration='NOT_RUN'))
    def case(self,name,kind,setting,long=False):
        folder=self.out/name;folder.mkdir(exist_ok=False);save(folder/'case.json',dict(kind=kind,**setting))
        with (folder/'input.scs').open('w',encoding='utf-8',newline='\n') as f:f.write(circuits.deck(self.model,self.b,self.c,kind,setting))
        seconds=self.deadline-time.monotonic()
        if seconds<1:r=dict(status='BLOCKED_BUDGET',simulator_elapsed_s=0)
        else:
            start=time.monotonic()
            r=e.run_case(self.exe,folder,['.tran'],min(seconds,self.c['noise_timeout_s'] if kind=='noise' else self.c['gate_timeout_s']),['+aps','+mt=1'])
            r['simulator_elapsed_s']=time.monotonic()-start
            if r['status']=='COMPLETED_REVIEW_REQUIRED':
                try:
                    if r['aggregate_audit'][1]:raise ValueError('Spectre warning requires review')
                    path=folder/r['result_files']['.tran'][0]
                    result=metrics.trace(path,self.c,setting['q'],folder if long else None) if kind=='noise' else metrics.deterministic(path,self.c,kind,setting)
                    r['metrics']=result
                    if kind!='noise' and result['required_gate'] and (result['wrong_known_stable_inputs'] or result['read_invalid'] or result['hold_invalid_saved_points'] or result['hold_changed_saved_points']):
                        raise ValueError('Known-stable input or hold test failed')
                except (ValueError,KeyError,IndexError,OSError,ZeroDivisionError) as exc:r['status']='FAILED_CHECK';r['check_error']=str(exc)
        save(folder/'status.json',r)
        row=dict(case=name,kind=kind,setting=setting,**r)
        with self.lock:self.rows.append(row);self.persist('IN_PROGRESS')
        print(name+': '+r['status'],flush=True);return row
    def batch(self,jobs):
        fs=[self.pool.submit(j[0],self.case,*j) for j in jobs];return [f.result() for f in fs]
    def require(self,rows):
        if any(r['status']!='COMPLETED_REVIEW_REQUIRED' for r in rows):raise ValueError('Case failed; results preserved, no downstream qualification')
    def study(self):
        c=self.c
        ref=dict(reference_V=c['reference_V'],parent_sha256=c['reference_parent_sha256'],policy='Parent calibration frozen; no new validation-seed tuning')
        save(self.out/'reference_lock.json',ref);frozen=e.digest(self.out/'reference_lock.json')
        gates=self.batch([('functional_{}mV'.format(int(1e3*a)),'functional',dict(overdrive_V=a)) for a in (.001,.01)]+[
            ('aperture_{}_{}'.format('rise' if up else 'fall',i),'aperture',dict(up=up,offset_s=d)) for up in (False,True) for i,d in enumerate(c['stress_offsets_s'])])
        self.require(gates)
        self.details['aperture']=[dict(case=r['case'],offset_s=r['setting']['offset_s'],up=r['setting']['up'],critical=r['metrics']['critical_cycle']) for r in gates if r['kind']=='aperture']
        numeric=self.batch([('precision_{}_seed{}'.format(tag,seed),'noise',dict(tag=tag,q=circuits.parameters(c,seed,step=dt,fmax=bw)))
            for tag,dt,bw in [('base',2.5e-9,1e8),('fine',1.25e-9,1e8),('wide',1.25e-9,2e8)] for seed in c['numeric_seeds']])
        self.require(numeric);screen=metrics.screen(numeric,c);save(self.out/'numerical_screen.json',screen);self.details['numeric_screen']=screen
        if not screen['passed']:raise ValueError('TimedQ short numerical/readout screen failed')
        rate=max(r['simulator_elapsed_s']/r['setting']['q']['stop_s'] for r in numeric if r['setting']['tag']=='base')
        cost=rate*circuits.parameters(c,c['validation_seeds'][0],long=True)['stop_s']*c['remaining_cost_factor']
        save(self.out/'remaining_cost_estimate.json',dict(estimated_long_parallel_seconds=cost,remaining_seconds=self.deadline-time.monotonic(),factor=c['remaining_cost_factor']))
        if cost>self.deadline-time.monotonic():raise ValueError('Full statistics exceeds remaining6h budget; keep pilot results')
        rows=self.batch([('validation_seed'+str(seed),'noise',dict(tag='validation',q=circuits.parameters(c,seed,long=True)),True) for seed in c['validation_seeds']])
        self.require(rows)
        if e.digest(self.out/'reference_lock.json')!=frozen:raise ValueError('Reference changed')
        self.details['validation_summary']=[dict(seed=r['setting']['q']['seed'],**r['metrics']) for r in rows]
        ok=all(r['metrics']['invalid_Q']==0 and r['metrics']['hold_invalid_saved_points']==0 and r['metrics']['hold_changed_saved_points']==0 for r in rows)
        self.persist('TIMED_STATISTICS_COMPLETE_REVIEW_REQUIRED_NOT_ENTROPY_QUALIFIED' if ok else 'TIMED_STATISTICS_COMPLETE_READOUT_FAILURES_PRESERVED')
        return 0 if ok else 2

def main():
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');p.add_argument('--snapshot',type=Path);p.add_argument('--pack',type=Path)
    p.add_argument('--out',type=Path);p.add_argument('--workers',type=int,default=8);p.add_argument('--max-hours',type=float,default=6);a=p.parse_args()
    e.verify_source();c=load(SOURCE/'config.json');b=load(SOURCE/'base_config.json');circuits.validate(c)
    assert e.digest(SOURCE/'parent_reference.json')==c['reference_parent_sha256']
    assert abs(load(SOURCE/'parent_reference.json')['reference_V']-c['reference_V'])<1e-12
    if a.verify:print('SOURCE/CONFIG/PARENT_REFERENCE=PASS');return 0
    if a.snapshot:snapshot(a.snapshot);return 0
    if a.pack:pack(a.pack);return 0
    if not a.out:p.error('--out required')
    execution.check_resources(a.workers,threads=1,cpus=8)
    if not 0<a.max_hours<=6:raise ValueError('Compute budget must be positive and<=6h')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);snapshot(out/'source')
    for name in ['config.json','base_config.json','parent_reference.json']:shutil.copyfile(str(SOURCE/name),str(out/name))
    _,model,discovery=discover_model(c['pdk_root']);save(out/'pdk_discovery.json',discovery)
    if model is None:raise ValueError('PDK not found')
    hashes={'model/spectre/'+q.relative_to(model.parent).as_posix():e.digest(q) for q in model.parent.rglob('*') if q.is_file()}
    matched=all(hashes.get(k)==v for k,v in load(SOURCE/'local_pdk_hashes.json').items());save(out/'pdk_comparison.json',dict(matches=matched,hashes=hashes))
    if not matched:raise ValueError('PDK hashes differ')
    exe=shutil.which(os.environ.get('SPECTRE_BIN','spectre'))
    if not exe:raise ValueError('Spectre not found')
    with (out/'spectre_version.txt').open('w') as f:subprocess.run([exe,'-W'],stdout=f,stderr=subprocess.STDOUT,timeout=20)
    save(out/'metadata.json',dict(utc=datetime.utcnow().isoformat()+'Z',job=os.environ.get('SLURM_JOB_ID'),python=sys.version,
        source_git_commit=os.environ.get('SAMPLED_SOURCE_COMMIT','MANIFEST_ONLY'),source_manifest_sha256=e.digest(SOURCE/'package_manifest.json'),
        config_sha256=e.digest(SOURCE/'config.json'),solver='APS',threads_per_case=1,workers=a.workers,allocated_CPUs=8,compute_budget_hours=a.max_hours))
    with execution.CasePool(a.workers,out/'parallel_events.jsonl') as pool:
        runner=Runner(out,model,c,b,exe,pool,a.max_hours)
        try:return runner.study()
        except Exception as exc:
            runner.details['failure']=type(exc).__name__+': '+str(exc);runner.persist('BLOCKED_OR_FAILED_RESULTS_PRESERVED');raise
        finally:save(out/'parallel_summary.json',pool.stats())
if __name__=='__main__':sys.exit(main())
