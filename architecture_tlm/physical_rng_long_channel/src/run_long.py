"""Staged long-record characterization. Python 3.6+, no third-party packages."""
import argparse
from concurrent.futures import as_completed
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time
import traceback
import channel
import common
import engine
from execution import CasePool,check_resources
import long_metrics as m
import lowpower as lp
from pdk_discovery import discover_model
import run_characterization as old
import scan_measurements as scan
import support
import zero_core as z

SOURCE=Path(__file__).resolve().parent


def save(path,data):common.save(Path(path),data)


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def walltime_seconds(value):
    value=str(value);days=0
    if '-' in value:
        d,value=value.split('-',1);days=int(d)
    parts=[int(x) for x in value.split(':')]
    if len(parts)==3:seconds=parts[0]*3600+parts[1]*60+parts[2]
    elif len(parts)==2:seconds=parts[0]*60+parts[1]
    elif len(parts)==1:seconds=parts[0]*60
    else:raise ValueError('Invalid Slurm walltime')
    return days*86400+seconds


def numerical_screen(records,seed_set,tolerances):
    groups={r['setting'].get('matrix_key'):{} for r in records if r['setting'].get('matrix_key')}
    for r in records:
        if r['setting'].get('matrix_key'):groups[r['setting']['matrix_key']][r['setting']['q']['seed']]=r
    comparisons=[]
    for left,right in [('base','fine_step'),('fine_step','wide_band')]:
        per_seed=[]
        for seed in seed_set:
            a=groups[left][seed]['metrics'];b=groups[right][seed]['metrics']
            changes=dict(p1_change=abs(a['p1']-b['p1']),midrail_change=abs(a['midrail_fraction']-b['midrail_fraction']))
            for label in ['core','comparator']:
                da=a[label+'_distribution'];db=b[label+'_distribution']
                changes[label+'_cdf_grid_sup_change']=max(abs(x-y) for x,y in zip(da['cdf'],db['cdf']))
                changes[label+'_std_relative_change']=abs(da['std_V']-db['std_V'])/max(da['std_V'],1e-12)
            acfs=[abs(v['correlation']-b['dense_bit_acf'][k]['correlation']) for k,v in a['dense_bit_acf'].items()
                  if k in b['dense_bit_acf'] and v['correlation'] is not None and b['dense_bit_acf'][k]['correlation'] is not None]
            changes['acf_max_change']=max(acfs) if acfs else 1.
            per_seed.append(dict(seed=seed,**changes))
        means={k:statistics.mean(row[k] for row in per_seed) for k in per_seed[0] if k!='seed'}
        passed=(means['p1_change']<=tolerances['maximum_mean_p1_change'] and
                means['midrail_change']<=tolerances['maximum_mean_midrail_change'] and
                max(means['core_cdf_grid_sup_change'],means['comparator_cdf_grid_sup_change'])<=tolerances['maximum_mean_ks_distance'] and
                max(means['core_std_relative_change'],means['comparator_std_relative_change'])<=tolerances['maximum_mean_std_relative_change'] and
                means['acf_max_change']<=tolerances['maximum_mean_acf_change'])
        comparisons.append(dict(left=left,right=right,per_seed=per_seed,mean_absolute_changes=means,screen_pass=passed))
    return dict(status='SHORT_NUMERICAL_SCREEN_PASS' if all(x['screen_pass'] for x in comparisons) else 'SHORT_NUMERICAL_SCREEN_NEEDS_REVIEW',
                comparisons=comparisons,tolerances=tolerances,
                interpretation='Finite-seed engineering screen, not a proof of numerical convergence; same seeds need not yield identical trajectories across solver settings')


def cost_projection(records,c,effective=1):
    measured=[r for r in records if r.get('simulator_elapsed_s') and r['setting'].get('q')]
    if not measured:return dict(status='GENERATED_NOT_TIMED')
    per_sim_second=max(r['simulator_elapsed_s']/r['setting']['q']['stop_s'] for r in measured)
    duration=effective+c['long_warmup_s'];projected=per_sim_second*duration*c['cost_projection_safety_factor']
    calibration_path=(c['calibration_bisections']+2)*(c['calibration_warmup_s']+c['calibration_effective_s'])*per_sim_second*c['cost_projection_safety_factor']
    precision_waves=2*c['lowfreq_check_stop_s']*2*per_sim_second*c['cost_projection_safety_factor']
    return dict(status='EXTRAPOLATION_NOT_MEASUREMENT',long_effective_s=effective,long_total_s=duration,
                minimum_internal_steps_per_record=int(math.ceil(duration/c['maxstep_s'])),
                measured_max_wall_seconds_per_simulated_second=per_sim_second,
                wall_seconds_per_record_with_safety_factor=projected,
                safety_factor=c['cost_projection_safety_factor'],records_1s_both_fmin=6,
                approximate_calibration_plus_10Hz_screen_wall_s_at_8_workers=calibration_path+precision_waves,
                note='Low-frequency generation, nonlinear adaptive steps, host load and output costs can change scaling. 8 CPUs do not accelerate one tiny Spectre process 8x.')


class Runner:
    def __init__(self,out,model,c,b,exe,pool,preview,stage,effective):
        self.out=out;self.model=model;self.c=c;self.b=b;self.v=channel.candidate(c,b)
        self.exe=exe;self.pool=pool;self.preview=preview;self.stage=stage;self.effective=effective
        self.records=[];self.details={}

    def persist(self,status,**extra):
        save(self.out/'summary.json',dict(status=status,stage=self.stage,generated_only=self.preview,
            circuit=self.v,operating_mode=self.c['operating_mode'],cases=self.records,
            source_manifest_sha256=common.digest(SOURCE/'package_manifest.json'),
            config_sha256=common.digest(SOURCE/'config.json'),physical_entropy_certified=False,
            details=self.details,**extra))

    def execute(self,name,deck,suffixes,setting,check,timeout):
        folder=self.out/name;folder.mkdir(exist_ok=False)
        with (folder/'input.scs').open('w',encoding='utf-8',newline='\n') as f:f.write(deck)
        save(folder/'case.json',dict(setting=setting,config_sha256=common.digest(SOURCE/'config.json')))
        if self.preview:r=dict(status='GENERATED_NOT_SIMULATED')
        else:
            start=time.monotonic();r=engine.run_case(self.exe,folder,suffixes,timeout)
            r['simulator_elapsed_s']=time.monotonic()-start
            r['diagnostics']=support.log_diagnostics(folder/'spectre.log')
            text=(folder/'spectre.log').read_text(errors='replace') if (folder/'spectre.log').exists() else ''
            bad=[line for line in text.splitlines() if re.search(r'(noiseoff|noisefmin|noisefmax|noisescale|strobe)',line,re.I) and re.search(r'ignor|not supported|unknown|unrecogn',line,re.I)]
            if bad:r.update(status='FAILED_NOISE_PARAMETER_REVIEW',noise_parameter_lines=bad)
            if r['status']=='COMPLETED_REVIEW_REQUIRED':
                try:
                    if r['diagnostics']['trapezoidal_ringing']:raise ValueError('Trapezoidal ringing diagnostic')
                    for suffix in suffixes:
                        if len(r['result_files'][suffix])!=1:raise ValueError('Ambiguous/missing PSF')
                        scan.complete_psf(folder/r['result_files'][suffix][0])
                    r['metrics']=check(folder,r)
                except Exception as exc:r.update(status='FAILED_OUTPUT_CHECK',error=str(exc),traceback=traceback.format_exc())
        save(folder/'status.json',r)
        return dict(case=name,setting=setting,**r)

    def batch(self,jobs):
        names=[j[0] for j in jobs]
        if len(set(names))!=len(names) or any((self.out/name).exists() for name in names):raise ValueError('Duplicate/preexisting case')
        pending={self.pool.submit(self.stage+'/'+j[0],self.execute,*j):i for i,j in enumerate(jobs)}
        ordered=[None]*len(jobs)
        for future in as_completed(pending):
            i=pending[future]
            try:r=future.result()
            except Exception as exc:
                r=dict(case=jobs[i][0],setting=jobs[i][3],status='FAILED_INTERNAL',error=str(exc),traceback=traceback.format_exc())
                folder=self.out/jobs[i][0];folder.mkdir(exist_ok=True);save(folder/'status.json',r)
            ordered[i]=r;self.records.append(r);self.persist('IN_PROGRESS')
            print(self.stage+'/'+r['case']+': '+r['status'],flush=True)
        return ordered

    def one(self,*job):return self.batch([job])[0]

    def require_cases(self,records):
        if any(r['status'] not in ['GENERATED_NOT_SIMULATED','COMPLETED_REVIEW_REQUIRED'] for r in records):
            raise ValueError('Case failure; successful siblings preserved. Reanalyze completed PSF instead of rerunning long simulation when possible.')

    def noise_job(self,name,q,reference,audit='all',long=False,extra=None):
        setting=dict(kind='long' if long else 'noise_diagnostic',q=q,reference_V=reference,
                     audit=audit,circuit=self.c['circuit'],rail_V=self.v['rail_V'])
        if extra:setting.update(extra)
        if long:
            provenance='Spectre simulation only; '+json.dumps(setting,sort_keys=True)+'; source manifest '+common.digest(SOURCE/'package_manifest.json')
            check=lambda folder,r:m.long_record(folder/r['result_files']['.tran'][0],folder,q,self.v['rail_V'],self.c,provenance)
        else:check=lambda folder,r:m.wave(folder/r['result_files']['.tran'][0],q,self.v['rail_V'],self.c,audit!='all')
        timeout=self.c['timeout_s']['long' if long else 'probe' if audit!='all' or name.startswith('probe_') else 'calibrate' if self.stage=='calibrate' else 'pilot']
        if long:timeout=int(os.environ.get('LONG_CASE_TIMEOUT_S',str(timeout)))
        return (name,channel.noise_deck(self.model,self.b,self.v,reference,q,audit),['.tran'],setting,check,timeout)

    def matrix(self,fmin,seeds,stop,discard,strobe,reference,prefix):
        jobs=[]
        for tag,dt,fmax in [('base',2.5e-9,1e8),('fine_step',1.25e-9,1e8),('wide_band',1.25e-9,2e8)]:
            for seed in seeds:
                q=channel.transient_parameters(stop,discard,strobe,fmin,fmax,dt,seed)
                jobs.append(self.noise_job(prefix+'_'+tag+'_seed'+str(seed),q,reference,extra=dict(matrix_key=tag)))
        results=self.batch(jobs);self.require_cases(results)
        if self.preview:return dict(status='GENERATED_NOT_SIMULATED')
        return numerical_screen(results,seeds,self.c['numerical_screen'])

    def pilot(self):
        trips=[]
        for tag,sweep in [('forward',(.54,.67,.0001)),('reverse',(.67,.54,-.0001))]:
            r=self.one('dc_'+tag,z.build(self.model,self.b,self.v,'dc',sweep=sweep),['.dc'],dict(kind='dc'),
                lambda f,r,sweep=sweep:old.transfer(f/'raw/dcTransfer.dc',*sweep,self.v['rail_V']),self.c['timeout_s']['gate'])
            self.require_cases([r]);trips.append(self.v['previous_dc_V'] if self.preview else r['metrics']['reference_trip_V'])
        if abs(trips[0]-trips[1])>=20e-6:raise ValueError('DC hysteresis gate failed')
        center=sum(trips)/2;sweep=(center-.0005,center+.0005,5e-6)
        r=self.one('dc_fine',z.build(self.model,self.b,self.v,'dc',sweep=sweep),['.dc'],dict(kind='dc'),
            lambda f,r:old.transfer(f/'raw/dcTransfer.dc',*sweep,self.v['rail_V'],False),self.c['timeout_s']['gate']);self.require_cases([r])
        if not self.preview:center=r['metrics']['reference_trip_V']
        ref=self.c['diagnostic_reference_V']
        jobs=[('op_ac_noise',z.build(self.model,self.b,self.v,'op_ac_noise',center),['.dc','.ac','.noise'],dict(kind='op_ac_noise',reference_V=center),
               lambda f,r:scan.small_signal(f,True,self.b,self.v),self.c['timeout_s']['gate']),
              ('startup_step',z.build(self.model,self.b,self.v,'step',center),['.tran'],dict(kind='step',reference_V=center),
               lambda f,r:lp.check_step(f/r['result_files']['.tran'][0],self.b,self.v,'screen'),self.c['timeout_s']['gate'])]
        self.require_cases(self.batch(jobs))
        audits=[]
        for tag in ['all','core_only','comparator_only','none']:
            q=channel.transient_parameters(self.c['probe_stop_s'],self.c['probe_discard_s'],self.c['probe_strobe_s'],seed=self.c['probe_seed'])
            audits.append(self.noise_job('probe_'+tag,q,ref,tag))
        r=self.batch(audits);self.require_cases(r)
        if self.preview:audit=dict(status='GENERATED_NOT_SIMULATED')
        else:
            by={x['setting']['audit']:x['metrics'] for x in r}
            core_ok=by['core_only']['core_distribution']['std_V']>max(1e-8,5*by['none']['core_distribution']['std_V'])
            cmp_ok=by['comparator_only']['sense_distribution']['std_V']>max(1e-9,5*by['none']['sense_distribution']['std_V'])
            audit=dict(status='DEVICE_NOISE_EFFECTS_OBSERVED' if core_ok and cmp_ok else 'DEVICE_NOISE_REVIEW_REQUIRED',
                core_noise_effect=core_ok,comparator_noise_effect=cmp_ok,
                evidence='Same device models, noiseoff masks on actual transistor instances; effect test not an additive noise-contribution decomposition',
                encrypted_PDK_noise_coefficients='Not exposed or edited; exact 27 PDK hashes and simulator help retained')
        self.details['noise_audit']=audit;save(self.out/'noise_audit.json',audit)
        self.details['cost']=cost_projection(r,self.c,self.effective);save(self.out/'cost_projection.json',self.details['cost'])
        screen=self.matrix(500,self.c['pilot_seeds'],self.c['pilot_stop_s'],self.c['pilot_discard_s'],self.c['pilot_strobe_s'],ref,'precision500')
        self.details['numerical_screen_500Hz']=screen;save(self.out/'numerical_screen_500Hz.json',screen)
        eligible=self.preview or (audit['status']=='DEVICE_NOISE_EFFECTS_OBSERVED' and screen['status']=='SHORT_NUMERICAL_SCREEN_PASS')
        self.persist('GENERATED_NOT_SIMULATED' if self.preview else 'PILOT_PASS' if eligible else 'PILOT_NEEDS_REVIEW',eligible_for_next_stage=eligible and not self.preview)
        return 0 if eligible else 1

    def calibrate(self):
        c=self.c;center=c['diagnostic_reference_V'];half=c['calibration_half_width_V'];evaluations=[]
        def evaluate(ref):
            index=len(evaluations);jobs=[]
            for seed in c['calibration_seeds']:
                q=channel.transient_parameters(c['calibration_warmup_s']+c['calibration_effective_s'],c['calibration_warmup_s'],c['calibration_strobe_s'],10,seed=seed)
                jobs.append(self.noise_job('cal{}_seed{}'.format(index,seed),q,ref))
            r=self.batch(jobs);self.require_cases(r)
            probabilities=[max(.01,min(.99,.5+(center-ref)/.012))]*3 if self.preview else [x['metrics']['p1'] for x in r]
            evaluations.append(dict(reference_V=ref,seeds=c['calibration_seeds'],p1=probabilities))
            return sum(probabilities)/len(probabilities)
        low,high=center-half,center+half;pl,ph=evaluate(low),evaluate(high)
        if not pl>=.5>=ph or pl<=ph:raise ValueError('P50 not bracketed; no expansion/extrapolation permitted')
        for _ in range(c['calibration_bisections']):
            mid=(low+high)/2;pm=evaluate(mid)
            if not pl>=pm>=ph:raise ValueError('Nonmonotonic calibration; retain records, do not tune validation')
            if pm>=.5:low,pl=mid,pm
            else:high,ph=mid,pm
        estimate=low+(.5-pl)*(high-low)/(ph-pl);grid=c['reference_resolution_V']
        integer=max(math.ceil(low/grid-1e-8),min(math.floor(high/grid+1e-8),round(estimate/grid)))
        reference=integer*grid
        if not low-1e-12<=reference<=high+1e-12:raise ValueError('Calibration grid outside bracket')
        frozen=dict(status='PREVIEW_ONLY' if self.preview else 'FROZEN_BEFORE_NUMERICAL_CHECK_AND_LONG_VALIDATION',
            reference_V=reference,circuit=c['circuit'],mode=c['operating_mode'],calibration_seeds=c['calibration_seeds'],
            noisefmin_Hz=10,evaluations=evaluations,final_bracket_V=[low,high],source_manifest_sha256=common.digest(SOURCE/'package_manifest.json'),
            config_sha256=common.digest(SOURCE/'config.json'),generated_only=self.preview,reference_policy='Never alter from lowfreq screen or heldout data')
        path=self.out/'frozen_reference.json';save(path,frozen);before=common.digest(path)
        self.details['frozen_reference_sha256']=before;self.details['reference_V']=reference
        screen=self.matrix(10,c['lowfreq_check_seeds'],c['lowfreq_check_stop_s'],c['lowfreq_check_discard_s'],c['lowfreq_check_strobe_s'],reference,'precision10')
        self.details['numerical_screen_10Hz']=screen;save(self.out/'numerical_screen_10Hz.json',screen)
        if common.digest(path)!=before:raise ValueError('Frozen reference modified')
        self.details['cost']=cost_projection(self.records,c,self.effective);save(self.out/'cost_projection.json',self.details['cost'])
        eligible=self.preview or screen['status']=='SHORT_NUMERICAL_SCREEN_PASS'
        self.persist('GENERATED_NOT_SIMULATED' if self.preview else 'CALIBRATION_AND_10HZ_SCREEN_PASS' if eligible else 'FROZEN_REFERENCE_PRESERVED_NUMERICAL_REVIEW_REQUIRED',eligible_for_next_stage=eligible and not self.preview)
        return 0 if eligible else 1

    def long(self,parent):
        frozen=load(parent/'frozen_reference.json');before=common.digest(parent/'frozen_reference.json')
        if not self.preview and (frozen['generated_only'] or frozen['calibration_seeds']!=self.c['calibration_seeds']):raise ValueError('Invalid calibration freeze')
        if frozen['config_sha256']!=common.digest(SOURCE/'config.json'):raise ValueError('Freeze config mismatch')
        shutil.copyfile(str(parent/'frozen_reference.json'),str(self.out/'frozen_reference.json'))
        reference=frozen['reference_V'];self.details['reference_V']=reference;self.details['frozen_reference_sha256']=before
        estimate=cost_projection(load(parent/'summary.json')['cases'],self.c,self.effective)
        self.details['cost']=estimate;save(self.out/'cost_projection.json',estimate)
        if not self.preview:
            case_limit=int(os.environ.get('LONG_CASE_TIMEOUT_S',self.c['timeout_s']['long']))
            wall_limit=walltime_seconds(os.environ.get('STUDY_WALLTIME','3-00:00:00'))-600
            if case_limit>wall_limit:raise ValueError('LONG_CASE_TIMEOUT_S must fit Slurm walltime with >=600s packing margin')
            limit=min(case_limit,wall_limit)
            if estimate.get('wall_seconds_per_record_with_safety_factor',float('inf'))>limit:
                self.persist('BLOCKED_BUDGET_ESTIMATE',eligible_for_next_stage=False)
                raise ValueError('Projected long case exceeds LONG_CASE_TIMEOUT_S; review measured cost and resource budget, do not relax noise physics')
        seeds=self.c['validation_seeds'] if self.effective==1 else self.c['extension_seeds']
        jobs=[]
        for fmin in self.c['noise_minima_Hz']:
            for seed in seeds:
                q=channel.transient_parameters(self.c['long_warmup_s']+self.effective,self.c['long_warmup_s'],self.c['long_strobe_s'],fmin,seed=seed)
                jobs.append(self.noise_job('long_fmin{}_seed{}'.format(fmin,seed),q,reference,long=True,
                                          extra=dict(frozen_reference_sha256=before)))
        results=self.batch(jobs);self.require_cases(results)
        if common.digest(parent/'frozen_reference.json')!=before or common.digest(self.out/'frozen_reference.json')!=before:raise ValueError('Frozen reference changed')
        self.persist('GENERATED_NOT_SIMULATED' if self.preview else 'LONG_RECORDS_COMPLETED_QUALITY_REVIEW_REQUIRED',
            eligible_for_next_stage=False,records_analyzed_separately=True,expected_raw_bits_per_record=int(round(self.effective/self.c['sample_interval_s'])))
        return 0


def parent_gate(path,stage,preview):
    if path is None:raise ValueError('Provide previous stage result directory')
    path=Path(path).resolve();s=load(path/'summary.json')
    if s['stage']!=stage:raise ValueError('Wrong dependency stage')
    if s['source_manifest_sha256']!=common.digest(SOURCE/'package_manifest.json') or s['config_sha256']!=common.digest(SOURCE/'config.json'):
        raise ValueError('Dependency source/config does not match this immutable package')
    if not preview:
        if s['generated_only'] or not s.get('eligible_for_next_stage'):raise ValueError('Previous stage did not pass; previews cannot unlock execution')
        if not (path/'job_exit_status.txt').is_file() or (path/'job_exit_status.txt').read_text().strip()!='0':raise ValueError('Wait for a successful completed Slurm parent job')
    return path


def run_stage(a,c,b,out,parent):
    out.mkdir(parents=True,exist_ok=False);common.copy_source(out/'source');save(out/'config.json',c);save(out/'base_config.json',b)
    save(out/'metadata.json',dict(stage=a.stage,utc=datetime.utcnow().isoformat()+'Z',job=os.environ.get('SLURM_JOB_ID'),host=os.environ.get('HOSTNAME'),
        python=sys.version,command=sys.argv,workers=a.workers,parent=str(parent) if parent else None,
        effective_seconds=a.effective_seconds,source_manifest_sha256=common.digest(SOURCE/'package_manifest.json'),config_sha256=common.digest(SOURCE/'config.json'),
        generated_only=a.generate_only,mode=c['operating_mode'],git='Exact package byte manifest; formal source tracked under Issue152',
        LONG_CASE_TIMEOUT_S=os.environ.get('LONG_CASE_TIMEOUT_S'),STUDY_WALLTIME=os.environ.get('STUDY_WALLTIME')))
    if parent:
        dep=parent_gate(parent,'pilot' if a.stage=='calibrate' else 'calibrate',a.generate_only)
        save(out/'dependency.json',dict(parent=str(dep),summary_sha256=common.digest(dep/'summary.json')))
    _,model,report=discover_model(a.pdk_root or os.environ.get('PBIT_PDK_ROOT',c['pdk_root']));save(out/'pdk_discovery.json',report)
    if model is None:save(out/'summary.json',dict(status='BLOCKED_PDK'));return 2
    expected=load(SOURCE/'local_pdk_hashes.json')
    actual={'model/spectre/'+p.relative_to(model.parent).as_posix():common.digest(p) for p in model.parent.rglob('*') if p.is_file()}
    matches=all(actual.get(k)==v for k,v in expected.items());save(out/'pdk_comparison.json',dict(matches=matches,hashes=actual))
    if not matches:save(out/'summary.json',dict(status='BLOCKED_PDK_HASH'));return 2
    exe=None if a.generate_only else shutil.which(os.environ.get('SPECTRE_BIN','spectre'))
    if not a.generate_only and not exe:save(out/'summary.json',dict(status='BLOCKED_NO_SPECTRE'));return 2
    if exe:
        for name,args in [('version',['-W']),('tran_help',['-h','tran']),('noise_help',['-h','noise'])]:
            with (out/(name+'.txt')).open('w',encoding='utf-8') as f:subprocess.run([exe]+args,stdout=f,stderr=subprocess.STDOUT,timeout=30)
        helptext=(out/'tran_help.txt').read_text(errors='replace')
        if any(re.search(r'\b'+name+r'\b',helptext,re.I) is None for name in ['noisefmin','noisefmax','noisescale','noiseoff','strobeperiod','strobeoutput']):
            save(out/'summary.json',dict(status='BLOCKED_REQUIRED_SPECTRE_TRAN_FEATURE'));return 2
    with CasePool(a.workers,out/'parallel_events.jsonl') as pool:
        runner=Runner(out,model,c,b,exe,pool,a.generate_only,a.stage,a.effective_seconds)
        runner.persist('STARTING')
        try:code=runner.pilot() if a.stage=='pilot' else runner.calibrate() if a.stage=='calibrate' else runner.long(parent)
        except Exception as exc:
            runner.details['exception']=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
            runner.persist('INCOMPLETE_OR_BLOCKED');code=1
    save(out/'parallel_summary.json',pool.stats())
    return code


def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group()
    g.add_argument('--verify',action='store_true');g.add_argument('--snapshot-source');g.add_argument('--pack');g.add_argument('--reanalyze',type=Path);g.add_argument('--validate-parent',action='store_true')
    p.add_argument('--stage',choices=['pilot','calibrate','long','all'],default='pilot');p.add_argument('--parent',type=Path)
    p.add_argument('--workers',type=int,default=8);p.add_argument('--generate-only',action='store_true');p.add_argument('--pdk-root');p.add_argument('--out',type=Path)
    p.add_argument('--effective-seconds',type=float,choices=[1.,4.],default=1.)
    a=p.parse_args();common.verify();c=load(SOURCE/'config.json');b=load(SOURCE/'base_config.json');channel.validate(c,b)
    if a.verify:print('SOURCE/CONFIG=PASS');return 0
    if a.snapshot_source:common.copy_source(a.snapshot_source);return 0
    if a.pack:print('ARCHIVE='+str(common.pack(a.pack)));return 0
    if a.validate_parent:
        if a.stage not in ['calibrate','long']:p.error('Only calibrate/long have a parent')
        print('PARENT_PASS='+str(parent_gate(a.parent,'pilot' if a.stage=='calibrate' else 'calibrate',False)));return 0
    if a.out is None:p.error('--out required')
    if a.reanalyze:
        original=a.reanalyze.resolve();case=load(original/'case.json');q=case['setting']['q']
        if case['setting']['kind']!='long' or case['config_sha256']!=common.digest(SOURCE/'config.json'):raise ValueError('Reanalysis requires exact long-case config')
        paths=list((original/'raw').glob('*.tran'))
        if len(paths)!=1:raise ValueError('Ambiguous raw PSF')
        a.out.mkdir(parents=True,exist_ok=False)
        m.long_record(paths[0],a.out,q,case['setting']['rail_V'],c,'Reanalysis of '+str(original)+'; Spectre simulation only')
        save(a.out/'reanalysis.json',dict(original=str(original),psf_sha256=common.digest(paths[0]),input_sha256=common.digest(original/'input.scs'),config_sha256=case['config_sha256'],simulation_rerun=False))
        return 0
    check_resources(a.workers,a.generate_only)
    if a.stage=='all':
        if not a.generate_only:p.error('Run expensive stages separately after inspecting measured cost; all is preview-only')
        a.out.mkdir(parents=True,exist_ok=False);parent=None
        for stage in ['pilot','calibrate','long']:
            a.stage=stage;out=a.out/stage;code=run_stage(a,c,b,out,parent)
            if code:return code
            parent=out
        return 0
    return run_stage(a,c,b,a.out.resolve(),a.parent.resolve() if a.parent else None)

if __name__=='__main__':sys.exit(main())
