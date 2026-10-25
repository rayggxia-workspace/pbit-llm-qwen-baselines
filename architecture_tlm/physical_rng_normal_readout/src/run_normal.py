"""Bounded conventional-comparator study; Python3.6, real Spectre only in Slurm."""
import argparse,json,math,os,shutil,subprocess,sys,tarfile,threading,time
from pathlib import Path
from datetime import datetime
import engine as e
import execution
import normal_circuits as circuits
import normal_metrics as metrics
import run_characterization as parser
from pdk_discovery import discover_model

SOURCE=Path(__file__).resolve().parent
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,data):e.write_json(path,data)

def snapshot(target):
    e.verify_source();target.mkdir(parents=True,exist_ok=False)
    for name in list(load(SOURCE/'package_manifest.json'))+['package_manifest.json']:
        with (target/name).open('xb') as f:f.write((SOURCE/name).read_bytes())

def pack(out):
    out=out.resolve();e.finalize(out)
    target=out.parent.parent/('normal_readout_'+out.name+'.tar.gz')
    if target.exists():raise FileExistsError('Keep existing archive: '+str(target))
    part=target.with_name(target.name+'.part')
    with tarfile.open(str(part),'w:gz') as tar:
        for name in list(load(out/'result_manifest.json'))+['result_manifest.json']:
            tar.add(str(out/name),arcname=out.name+'/'+name,recursive=False)
    part.rename(target)
    (target.parent/(target.name+'.sha256')).write_text(e.digest(target)+'  '+target.name+'\n',encoding='ascii')
    print('ARCHIVE='+str(target),flush=True)

class Runner:
    def __init__(self,out,model,c,b,exe,pool,hours):
        self.out,self.model,self.c,self.b,self.exe,self.pool=out,model,c,b,exe,pool
        self.records=[];self.details={};self.lock=threading.Lock();self.deadline=time.monotonic()+hours*3600
    def persist(self,status):
        save(self.out/'summary.json',dict(status=status,cases=self.records,details=self.details,
            physical_entropy_certified=False,power_integration='NOT_RUN',
            scope='TT25C,500Hz,continuous12MOS channel,noMUX/latch/1s drift'))
    def case(self,name,v,kind,ref=None,sweep=None,overdrive=.01,loaded=True,q=None,tag=None,long=False):
        folder=self.out/name;folder.mkdir(exist_ok=False)
        setting=dict(candidate=v,kind=kind,reference_V=ref,sweep=sweep,overdrive_V=overdrive,loaded=loaded,q=q,tag=tag)
        save(folder/'case.json',setting)
        with (folder/'input.scs').open('w',encoding='utf-8',newline='\n') as stream:
            stream.write(circuits.deck(self.model,self.b,self.c,v,kind,ref,sweep,overdrive,loaded,q))
        seconds=self.deadline-time.monotonic()
        if seconds<=1:r=dict(status='BLOCKED_BUDGET',returncode=125,timed_out=False)
        else:
            start=time.monotonic()
            suffixes=['.dc'] if kind in ['dc','op'] else ['.tran']
            r=e.run_case(self.exe,folder,suffixes,min(seconds,self.c['noise_timeout_s'] if kind=='noise' else self.c['gate_timeout_s']),['+aps','+mt=1'])
            r['simulator_elapsed_s']=time.monotonic()-start
            if r['status']=='COMPLETED_REVIEW_REQUIRED':
                try:
                    if r['aggregate_audit'][1]:raise ValueError('Unexpected Spectre warnings require review')
                    if kind=='dc':result=parser.transfer(folder/'raw/dcTransfer.dc',*sweep,1.2)
                    elif kind=='op':result=metrics.op(folder,self.c)
                    elif kind=='step':result=metrics.step(folder/r['result_files']['.tran'][0],self.c,ref)
                    else:result=metrics.wave(folder/r['result_files']['.tran'][0],q,self.c,folder if long else None)
                    r['metrics']=result
                except (ValueError,KeyError,IndexError,OSError,ZeroDivisionError) as exc:
                    r['status']='FAILED_CHECK';r['check_error']=str(exc)
        save(folder/'status.json',r)
        record=dict(case=name,setting=setting,**r)
        with self.lock:
            self.records.append(record);self.persist('IN_PROGRESS')
        print(name+': '+r['status'],flush=True)
        return record
    def batch(self,jobs):
        futures=[self.pool.submit(job[0],self.case,*job) for job in jobs]
        rows=[];failures=[]
        for f in futures:
            try:rows.append(f.result())
            except Exception as exc:failures.append(type(exc).__name__+': '+str(exc))
        if failures:raise RuntimeError('Worker failures; completed siblings retained: '+'; '.join(failures))
        return rows
    @staticmethod
    def require(rows):
        if any(r['status']!='COMPLETED_REVIEW_REQUIRED' for r in rows):raise ValueError('Case check failed; preserve diagnostics, no downstream records')
    def study(self):
        c=self.c
        broad=self.batch([(v['name']+'_dc',v,'dc',None,(.50,.70,.00025)) for v in c['candidates']])
        eligible=[r for r in broad if r['status']=='COMPLETED_REVIEW_REQUIRED']
        fine=self.batch([(r['setting']['candidate']['name']+'_fine',r['setting']['candidate'],'dc',None,
            (r['metrics']['reference_trip_V']-.0005,r['metrics']['reference_trip_V']+.0005,5e-6)) for r in eligible])
        eligible=[r for r in fine if r['status']=='COMPLETED_REVIEW_REQUIRED']
        jobs=[]
        for row in eligible:
            v=row['setting']['candidate'];ref=row['metrics']['reference_trip_V']
            jobs.append((v['name']+'_op',v,'op',ref))
            for overdrive in [.01,.001]:
                for loaded in [False,True]:
                    name='{}_step_{}m_{}'.format(v['name'],int(overdrive*1000),'loaded' if loaded else 'fixed_input')
                    jobs.append((name,v,'step',ref,None,overdrive,loaded))
        physical=self.batch(jobs);choices=[]
        for row in eligible:
            v=row['setting']['candidate'];siblings=[r for r in physical if r['setting']['candidate']['name']==v['name']]
            if len(siblings)!=5 or any(r['status']!='COMPLETED_REVIEW_REQUIRED' for r in siblings):continue
            worst=max(r['metrics']['maximum_delay_s'] for r in siblings if r['setting']['kind']=='step')
            choices.append(dict(candidate=v,DC_reference_V=row['metrics']['reference_trip_V'],worst_step_delay_s=worst,
                speed_target_met=worst<=c['maximum_step_delay_s']))
        self.details['candidate_choices']=choices
        save(self.out/'candidate_selection.json',dict(choices=choices,policy='Minimum worst deterministic step delay among physically valid normal-bias candidates, then bias/name; no noisy validation used'))
        if not choices:raise ValueError('No physical normal-inversion comparator candidate passed')
        selected=min(choices,key=lambda r:(r['worst_step_delay_s'],r['candidate']['bias_A'],r['candidate']['name']))
        self.details['selected']=selected;v=selected['candidate'];center=selected['DC_reference_V']
        # New disjoint numerical seeds; original physical bandwidth is preserved.
        jobs=[]
        for tag,dt,fmax in [('base',2.5e-9,1e8),('fine',1.25e-9,1e8),('wide',1.25e-9,2e8)]:
            for seed in c['numeric_seeds']:
                q=circuits.q(c,seed,step=dt,fmax=fmax)
                jobs.append(('precision_{}_seed{}'.format(tag,seed),v,'noise',center,None,.01,True,q,tag))
        numeric=self.batch(jobs);self.require(numeric)
        screen=metrics.numerical_screen(numeric,c);save(self.out/'numerical_screen.json',screen);self.details['numerical_screen']=screen
        if screen['status']!='SHORT_SCREEN_PASS':raise ValueError('New comparator precision screen did not pass')
        rate=max(r['simulator_elapsed_s']/r['setting']['q']['stop_s'] for r in numeric if r['setting']['tag']=='base')
        estimate=rate*((c['calibration_bisections']+2)*c['short_stop_s']+c['validation_stop_s'])*1.5
        save(self.out/'remaining_cost_estimate.json',dict(status='EXTRAPOLATION_ONLY',seconds=estimate,remaining_seconds=self.deadline-time.monotonic(),factor=1.5))
        if estimate>self.deadline-time.monotonic():raise ValueError('Remaining calibrated/statistical stage exceeds budget')
        evaluations=[]
        def evaluate(ref):
            i=len(evaluations)
            rows=self.batch([('cal{}_seed{}'.format(i,seed),v,'noise',ref,None,.01,True,circuits.q(c,seed),'calibration') for seed in c['calibration_seeds']])
            self.require(rows);ps=[r['metrics']['p1'] for r in rows]
            evaluations.append(dict(reference_V=ref,seeds=c['calibration_seeds'],p1=ps))
            save(self.out/'calibration.json',evaluations)
            return sum(ps)/len(ps)
        lo,hi=center-c['calibration_half_width_V'],center+c['calibration_half_width_V']
        pl,ph=evaluate(lo),evaluate(hi)
        if not pl>=.5>=ph or pl<=ph:raise ValueError('Calibration did not bracketP50; no extrapolation or validation tuning')
        for _ in range(c['calibration_bisections']):
            mid=(lo+hi)/2;pm=evaluate(mid)
            if not pl>=pm>=ph:raise ValueError('Nonmonotonic calibration; frozen protocol retained')
            if pm>=.5:lo,pl=mid,pm
            else:hi,ph=mid,pm
        ref=lo+(.5-pl)*(hi-lo)/(ph-pl);grid=c['reference_resolution_V'];ref=round(ref/grid)*grid
        if not lo-1e-12<=ref<=hi+1e-12:raise ValueError('Frozen reference grid outside final bracket')
        frozen=dict(status='FROZEN_500HZ_BEFORE_HELDOUT_VALIDATION_NOT10HZ',reference_V=ref,selected=selected,
            calibration=evaluations,calibration_seeds=c['calibration_seeds'],validation_seeds=c['validation_seeds'],
            source_manifest_sha256=e.digest(SOURCE/'package_manifest.json'),config_sha256=e.digest(SOURCE/'config.json'))
        save(self.out/'frozen_reference.json',frozen);before=e.digest(self.out/'frozen_reference.json')
        validation=self.batch([('validation_seed'+str(seed),v,'noise',ref,None,.01,True,circuits.q(c,seed,long=True),'validation',True) for seed in c['validation_seeds']])
        self.require(validation)
        if e.digest(self.out/'frozen_reference.json')!=before:raise ValueError('Reference changed during validation')
        self.details['frozen_reference_sha256']=before
        self.details['validation_summary']=[dict(seed=r['setting']['q']['seed'],samples=r['metrics']['actual_sample_bits'],
            P1=r['metrics']['actual_P1'],MID=r['metrics']['actual_MID'],ACF=r['metrics']['actual_acf']) for r in validation]
        self.persist('STATISTICS_COMPLETE_REVIEW_REQUIRED_NOT_ENTROPY_QUALIFIED')
        return 0

def main():
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');p.add_argument('--snapshot',type=Path)
    p.add_argument('--pack',type=Path);p.add_argument('--out',type=Path);p.add_argument('--workers',type=int,default=8)
    p.add_argument('--max-hours',type=float,default=6);a=p.parse_args()
    e.verify_source();c=load(SOURCE/'config.json');b=load(SOURCE/'base_config.json');circuits.validate(c)
    if a.verify:print('SOURCE/CONFIG=PASS');return 0
    if a.snapshot:snapshot(a.snapshot);return 0
    if a.pack:pack(a.pack);return 0
    if not a.out:p.error('--out required')
    execution.check_resources(a.workers,threads=1,cpus=8)
    if not 0<a.max_hours<=6:raise ValueError('Compute budget must be positive and<=6h')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    for name in ['config.json','base_config.json']:shutil.copyfile(str(SOURCE/name),str(out/name))
    snapshot(out/'source')
    _,model,discovery=discover_model(c['pdk_root']);save(out/'pdk_discovery.json',discovery)
    if model is None:raise ValueError('PDK model not found')
    expected=load(SOURCE/'local_pdk_hashes.json')
    hashes={'model/spectre/'+q.relative_to(model.parent).as_posix():e.digest(q) for q in model.parent.rglob('*') if q.is_file()}
    matched=all(hashes.get(k)==v for k,v in expected.items());save(out/'pdk_comparison.json',dict(matches=matched,hashes=hashes))
    if not matched:raise ValueError('PDK byte mismatch')
    exe=shutil.which(os.environ.get('SPECTRE_BIN','spectre'))
    if not exe:raise ValueError('No Spectre executable')
    with (out/'spectre_version.txt').open('w') as f:subprocess.run([exe,'-W'],stdout=f,stderr=subprocess.STDOUT,timeout=20)
    save(out/'metadata.json',dict(utc=datetime.utcnow().isoformat()+'Z',job=os.environ.get('SLURM_JOB_ID'),host=os.environ.get('HOSTNAME'),
        python=sys.version,source_git_commit=os.environ.get('NORMAL_SOURCE_COMMIT','MANIFEST_ONLY'),
        source_manifest_sha256=e.digest(SOURCE/'package_manifest.json'),config_sha256=e.digest(SOURCE/'config.json'),
        solver='APS',threads_per_case=1,workers=a.workers,allocated_CPUs=8,compute_budget_hours=a.max_hours))
    with execution.CasePool(a.workers,out/'parallel_events.jsonl') as pool:
        r=Runner(out,model,c,b,exe,pool,a.max_hours)
        try:code=r.study()
        except Exception as exc:
            r.details['failure']=type(exc).__name__+': '+str(exc);r.persist('BLOCKED_OR_FAILED_RESULTS_PRESERVED');raise
        finally:save(out/'parallel_summary.json',pool.stats())
    return code

if __name__=='__main__':sys.exit(main())
