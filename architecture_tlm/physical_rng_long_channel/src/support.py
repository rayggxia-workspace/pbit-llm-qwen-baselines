"""Two explicit phases: numerical confirmation, then comparator candidates.

Python >=3.6, standard library. No automatic claim of numerical/statistical
acceptance. Submitted snapshots and raw outputs remain immutable.
"""
import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

import engine as e
import run_characterization as old
from pdk_discovery import discover_model

SOURCE=Path(__file__).resolve().parent
BRANCHES=('vbias:p','vana:p','vbuf1:p','vbuf2:p')


def pack_results(directory):
    """Verify finalized results, stream gzip to a temporary file, publish last.

    Keeps raw results; does not put an entire waveform/archive into memory.
    Hard-link publication refuses to overwrite an existing final archive.
    """
    directory=directory.resolve()
    old.require(directory.is_dir() and directory.parent.name=='results', 'Expected results/JOB directory')
    target=directory.parent.parent/('comparator_confirm_'+directory.name+'.tar.gz')
    old.require(not target.exists(), 'Archive already exists: '+str(target))
    manifest_path=directory/'result_manifest.json'
    old.require(manifest_path.is_file() and not manifest_path.is_symlink(), 'Final manifest required')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    checked=[]
    for name,expected in sorted(manifest.items()):
        relative=PurePosixPath(name)
        old.require(bool(relative.parts) and not relative.is_absolute() and '..' not in relative.parts
                    and '\\' not in name and ':' not in name, 'Unsafe manifest path')
        path=directory.joinpath(*relative.parts)
        old.require(directory in path.resolve().parents and path.is_file() and
                    not any(p.is_symlink() for p in [path]+list(path.parents) if p!=directory),
                    'Unsafe result file: '+name)
        old.require(path.stat().st_size==expected['bytes'] and e.digest(path)==expected['sha256'],
                    'Result checksum mismatch: '+name)
        checked.append((name,path))
    actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    old.require(actual==set(manifest)|{'result_manifest.json'}, 'Result file set differs from manifest')
    fd,temp=tempfile.mkstemp(prefix='.packing-'+directory.name+'-',suffix='.tmp',dir=str(target.parent))
    os.close(fd)
    try:
        with tarfile.open(temp,'w:gz',compresslevel=1) as archive:
            for name,path in checked+[('result_manifest.json',manifest_path)]:
                archive.add(str(path),arcname=directory.name+'/'+name,recursive=False)
        # Same filesystem: publish complete archive without clobbering a name
        # that may have appeared while the compression was running.
        os.link(temp,str(target))
    finally:
        if os.path.exists(temp):os.unlink(temp)
    print('ARCHIVE='+str(target),flush=True)
    print('ARCHIVE_SHA256='+e.digest(target),flush=True)
    return target


def validate(c):
    for k in ('stop_s','discard_s','strobe_s','maxstep_s','noisefmin_Hz','noisefmax_Hz',
              'short_stop_s','short_discard_s','short_strobe_s','comparator_bias_A','output_load_F',
              'case_timeout_s','short_timeout_s','gate_timeout_s'):
        old.require(math.isfinite(c[k]) and c[k]>0,k)
    old.require(c['seeds']==[17,29,43], 'Three specified seeds required')
    old.require(c['vdd_V']==1.2 and c['temperature_C']==25, 'Fixed TT 1.2V 25C protocol')
    old.require(c['maxstep_s']<=.5/c['noisefmax_Hz'], 'Noise bandwidth / timestep')
    for prefix in ('','short_'):
        stop,discard,strobe=[c[prefix+k] for k in ('stop_s','discard_s','strobe_s')]
        old.require(discard<stop and strobe<=c['maxstep_s']*10, 'Invalid trace window')
        for t in (stop,discard):
            old.require(abs(t/strobe-round(t/strobe))<1e-6, 'Nonintegral strobe window')
    old.require(set(c['variants'])=={'baseline','buffer_slim','input_slim'}, 'Unexpected variants')
    for v in c['variants'].values():
        old.require(all(math.isfinite(x) and x>0 for x in v.values()), 'Invalid geometry')
    old.require(.57<c['baseline_reference_V']<.63, 'Historical DC reference')


def header(model,c,gmin):
    return old.header(model,c).replace('gmin=1e-14','gmin={:.16g}'.format(gmin))


def comparator(c,variant):
    v=c['variants'][variant]
    lines=['// Zero-volt supply probes preserve rail voltage and expose branch currents.',
           'VDC (vdc 0) vsource dc={:.16g}'.format(c['vdd_V']),
           'VBIAS (vdc vrbias) vsource dc=0',
           'VANA (vdc vana) vsource dc=0',
           'VBUF1 (vdc vbuf1) vsource dc=0',
           'VBUF2 (vdc vbuf2) vsource dc=0',
           'IBIAS (vrbias nbias) isource dc={:.16g}'.format(c['comparator_bias_A'])]
    def mos(name,nodes,pmos,w,l):
        lines.append('{} ({}) {}m1p2_svt_lp w={:.16g}u l={:.16g}u nf=1 mr=1 prelayout=1'.format(
            name,nodes,'p' if pmos else 'n',w,l))
    mos('XBIAS','nbias nbias 0 0',False,2,1)
    mos('XTAIL','tail nbias 0 0',False,2,1)
    mos('XIP','mirror out tail 0',False,v['input_w_um'],v['input_l_um'])
    mos('XIN','sense ref tail 0',False,v['input_w_um'],v['input_l_um'])
    mos('XLP','mirror mirror vana vana',True,2,1)
    mos('XLM','sense mirror vana vana',True,2,1)
    for num,output,control in [(1,'inv','sense'),(2,'bit','inv')]:
        mos('XB{}N'.format(num),'{} {} 0 0'.format(output,control),False,v['buffer_n_w_um'],v['buffer_l_um'])
        mos('XB{}P'.format(num),'{} {} vbuf{} vbuf{}'.format(output,control,num,num),True,v['buffer_p_w_um'],v['buffer_l_um'])
    lines.append('Cbit (bit 0) capacitor c={:.16g}'.format(c['output_load_F']))
    return '\n'.join(lines)+'\n'


def save(loaded=True,detail=False):
    s='save out VDD:p\n'
    if loaded:
        s+='save bit VDC:p VBIAS:p VANA:p VBUF1:p VBUF2:p\n'
    if detail:s+='save ref sense inv tail nbias\n'
    return s


def dc_deck(model,c,variant,gmin,start,stop,step):
    # No core/VDD here: the comparator is driven by an ideal fixed input.
    return header(model,c,gmin)+comparator(c,variant)+'''parameters vref={start:.16g}
VIN (out 0) vsource dc=0.6
VREF (ref 0) vsource dc=vref
save out ref bit sense inv tail nbias VDC:p VBIAS:p VANA:p VBUF1:p VBUF2:p
dcTransfer dc param=vref start={start:.16g} stop={stop:.16g} step={step:.16g}
'''.format(start=start,stop=stop,step=step)


def op_deck(model,c,variant,reference,gmin=1e-14,bare=False):
    deck=header(model,c,gmin)+old.core(c)
    if not bare:
        deck+=comparator(c,variant)+'VREF (ref 0) vsource dc={:.16g}\n'.format(reference)
    return deck+save(not bare,not bare)+'dcOp dc\nopInfo info what=oppoint where=file file="oppoint.txt"\n'


def step_deck(model,c,variant,reference):
    return header(model,c,1e-14)+old.core(c)+comparator(c,variant)+(
        'VREF (ref 0) vsource type=pulse val0={:.16g} val1={:.16g} delay=10u rise=10n fall=10n width=10u period=20u\n'
        .format(reference-.01,reference+.01))+save(True,True)+(
        'tranStep tran stop=100u maxstep=5n strobeperiod=20n strobeoutput=strobeonly method=trap\n')


def noise_deck(model,c,setting):
    q=trace_config(c,setting)
    deck=header(model,c,setting['gmin'])+old.core(c)+comparator(c,setting['variant'])
    deck+='VREF (ref 0) vsource dc={:.16g}\n'.format(setting['reference_V'])
    deck+=save(True,setting['short'])
    return deck+('tranNoise tran stop={stop_s:.16g} maxstep={maxstep_s:.16g} '
                 'strobeperiod={strobe_s:.16g} strobeoutput=strobeonly '
                 'method={method} noisefmin={noisefmin_Hz:.16g} noisefmax={noisefmax_Hz:.16g} '
                 'noiseseed={seed} noisescale=1\n').format(**q)


def trace_config(c,s):
    q=dict(c);q.update(s)
    if s['short']:
        for key in ('stop_s','discard_s','strobe_s'):q[key]=c['short_'+key]
    return q


def numerical_noise(c):
    cases=[]
    def add(name,method,seed=17,gmin=1e-14,short=False):
        cases.append(dict(name=name,variant='baseline',method=method,seed=seed,gmin=gmin,
                          short=short,reference_V=c['baseline_reference_V'],offset_V=0.))
    add('10_baseline_traponly_seed17','traponly')
    for seed in c['seeds']:add('11_baseline_trap_seed'+str(seed),'trap',seed)
    add('12_baseline_trap_gmin1e15_seed17','trap',gmin=1e-15)
    add('13_short_traponly_seed17','traponly',short=True)
    add('14_short_trap_seed17','trap',short=True)
    return cases


def candidate_noise(c,variant,reference):
    cases=[]
    for offset,seeds in [(0.,c['seeds']),(-.006,[17]),(.006,[17])]:
        for seed in seeds:
            tag='m6' if offset<0 else 'p6' if offset>0 else 'p0'
            cases.append(dict(name=variant+'_noise_'+tag+'_seed'+str(seed),variant=variant,
                              method='trap',seed=seed,gmin=1e-14,short=False,
                              reference_V=reference+offset,offset_V=offset))
    return cases


def log_diagnostics(path):
    text=path.read_text(errors='replace') if path.exists() else ''
    ringing=bool(re.search(r'(?:Found trapezoidal ringing|Trapezoidal ringing is detected)',text,re.I))
    return dict(trapezoidal_ringing=ringing,gmin_notice='GminDC' in text,
                notices_suppressed=bool(re.search(r'notices? (?:will be )?suppressed',text,re.I)),
                evidence=[x.strip() for x in text.splitlines() if
                          any(w in x.lower() for w in ('trapezoidal ringing','gmindc =','dv(','use method='))],
                status='NUMERICAL_RINGING_REVIEW_REQUIRED' if ringing else 'NO_RINGING_REPORTED_NOT_CONVERGENCE_PROOF')


def branch_stats(path,c):
    sums={k:0. for k in BRANCHES};n=0;max_balance=0.;total_sum=0.
    conditional={k:dict(samples=0,buffer1_W=0.,buffer2_W=0.) for k in ('low','mid','high')}
    signals=['out','bit','vdd:p','vdc:p']+list(BRANCHES)
    for row in old.checked_trace(path,c['stop_s'],c['strobe_s'],signals):
        if row['time']<c['discard_s']-1e-12 or row['time']>=c['stop_s']-1e-12:continue
        n+=1;total_sum+=-row['vdc:p']
        for key in BRANCHES:sums[key]+=row[key]
        max_balance=max(max_balance,abs(-row['vdc:p']-sum(row[k] for k in BRANCHES)))
        state='low' if row['bit']<=.2*c['vdd_V'] else 'high' if row['bit']>=.8*c['vdd_V'] else 'mid'
        conditional[state]['samples']+=1
        conditional[state]['buffer1_W']+=c['vdd_V']*row['vbuf1:p']
        conditional[state]['buffer2_W']+=c['vdd_V']*row['vbuf2:p']
    old.require(n>0,'Empty retained trace')
    mean_balance=abs(total_sum-sum(sums.values()))/n
    old.require(mean_balance<=max(1e-12,abs(total_sum/n)*1e-6),'Comparator branch accounting does not close')
    for stats in conditional.values():
        for key in ('buffer1_W','buffer2_W'):
            stats[key]=stats[key]/stats['samples'] if stats['samples'] else None
    return dict(average_power_W={key:c['vdd_V']*value/n for key,value in sums.items()},
                mean_balance_error_A=mean_balance,max_instantaneous_balance_error_A=max_balance,
                conditional_buffer_power=conditional,
                interpretation='Supply-branch power; reference generator overhead and voltage-bias implementation excluded')


def op_check(folder,result,bare=False):
    d=dict(e.read_values(folder/'raw/dcOp.dc'))
    old.require(.599<=d['out']<=.601 and 15e-9<=-d['vdd:p']<=18e-9,'Core baseline workpoint drift')
    old.require((folder/'oppoint.txt').is_file(),'Missing transistor operating point')
    result=dict(out_V=d['out'],core_current_A=-d['vdd:p'])
    if not bare:
        old.require(-d['vdc:p']>0,'Comparator supply sign')
        residual=-d['vdc:p']-sum(d[k] for k in BRANCHES)
        old.require(abs(residual)<max(1e-12,abs(d['vdc:p'])*1e-6),'DC supply branch accounting')
        result.update(comparator_current_A=-d['vdc:p'],branch_currents_A={k:d[k] for k in BRANCHES},balance_error_A=residual)
    return result


class Study:
    def __init__(self,out,model,c,exe,preview,phase):
        self.out,self.model,self.c,self.exe=out,model,c,exe
        self.preview,self.phase=preview,phase
        self.records=[];self.calibrations={};self.skipped=[]

    def persist(self,status):
        e.write_json(self.out/'summary.json',dict(status=status,phase=self.phase,cases=self.records,
            calibrations=self.calibrations,skipped=self.skipped,
            numerical_acceptance='PENDING_OFFLINE_REVIEW',statistical_acceptance='PENDING_OFFLINE_REVIEW',
            physical_entropy_validated=False,
            ringing_cases=[r['case'] for r in self.records if r.get('diagnostics',{}).get('trapezoidal_ringing')]))

    def run(self,name,deck,suffixes,check=None,setting=None,timeout=None):
        folder=self.out/name;folder.mkdir()
        with (folder/'input.scs').open('w',encoding='utf-8',newline='\n') as f:f.write(deck)
        if self.preview:result=dict(status='GENERATED_NOT_SIMULATED')
        else:
            result=e.run_case(self.exe,folder,suffixes,timeout or self.c['gate_timeout_s'])
            result['diagnostics']=log_diagnostics(folder/'spectre.log')
            if result['status']=='COMPLETED_REVIEW_REQUIRED' and check:
                try:result['measurements']=check(folder,result)
                except (ValueError,KeyError,IndexError,OSError) as exc:
                    result.update(status='FAILED_OUTPUT_CHECK',check_error=str(exc))
        e.write_json(folder/'status.json',result)
        self.records.append(dict(case=name,setting=setting,**result));self.persist('IN_PROGRESS')
        print(name+': '+result['status']+(' [RINGING]' if result.get('diagnostics',{}).get('trapezoidal_ringing') else ''),flush=True)
        return result

    def dc(self,name,variant,start,stop,step,gmin=1e-14,rails=False):
        return self.run(name,dc_deck(self.model,self.c,variant,gmin,start,stop,step),['.dc'],
            lambda f,r:old.transfer(f/'raw/dcTransfer.dc',start,stop,step,self.c['vdd_V'],rails),
            dict(variant=variant,gmin=gmin,start_V=start,stop_V=stop,step_V=step))

    @staticmethod
    def ok(r):return r['status'] in ('GENERATED_NOT_SIMULATED','COMPLETED_REVIEW_REQUIRED')

    def noise(self,setting):
        c=trace_config(self.c,setting)
        def check(folder,result):
            path=folder/result['result_files']['.tran'][0]
            value=old.summarize_trace(path,c,True)
            value['branch_power']=branch_stats(path,c)
            return value
        return self.run(setting['name'],noise_deck(self.model,self.c,setting),['.tran'],check,setting,
                        self.c['short_timeout_s'] if setting['short'] else self.c['case_timeout_s'])

    def numerical_phase(self):
        c=self.c;model=self.model;center=c['baseline_reference_V']
        r=self.run('00_bare_op',op_deck(model,c,'baseline',center,bare=True),['.dc'],lambda f,r:op_check(f,r,True))
        if not self.ok(r):return False
        for name,gmin in [('01_dc_gmin1e14',1e-14),('02_dc_gmin1e15',1e-15)]:
            r=self.dc(name,'baseline',center-.0005,center+.0005,.00001,gmin)
            if not self.ok(r):return False
            self.calibrations[name]=r.get('measurements',{'preview_reference_V':center})
        r=self.run('03_loaded_op',op_deck(model,c,'baseline',center),['.dc'],op_check)
        if not self.ok(r):return False
        r=self.run('04_loaded_reference_step',step_deck(model,c,'baseline',center),['.tran'],
                   lambda f,r:old.check_step(f/r['result_files']['.tran'][0],c,True))
        if not self.ok(r):return False
        # Keep the historical control voltage fixed: isolate solver/gmin effects.
        for s in numerical_noise(c):self.noise(s)
        return True

    def candidate_phase(self):
        c=self.c
        for variant in ('baseline','buffer_slim','input_slim'):
            trips=[];good=True
            for tag,start,stop,step in [('forward',.57,.63,.0001),('reverse',.63,.57,-.0001)]:
                r=self.dc(variant+'_dc_'+tag,variant,start,stop,step,rails=True)
                if not self.ok(r):good=False;break
                trips.append(c['baseline_reference_V'] if self.preview else r['measurements']['reference_trip_V'])
            if good and abs(trips[0]-trips[1])>.0002:
                good=False
            if not good:
                self.skipped.append(dict(variant=variant,reason='DC_TRANSFER_OR_DIRECTION_CHECK_FAILED'));continue
            coarse=sum(trips)/2
            r=self.dc(variant+'_dc_fine',variant,coarse-.0005,coarse+.0005,.00001)
            if not self.ok(r):
                self.skipped.append(dict(variant=variant,reason='DC_FINE_FAILED'));continue
            center=coarse if self.preview else r['measurements']['reference_trip_V']
            self.calibrations[variant]=dict(reference_V=center,preview_placeholder=self.preview,
                interpretation='DC calibration only; not calibrated to stochastic p=0.5')
            r=self.run(variant+'_loaded_op',op_deck(self.model,c,variant,center),['.dc'],op_check)
            if not self.ok(r):
                self.skipped.append(dict(variant=variant,reason='LOADED_OP_FAILED'));continue
            r=self.run(variant+'_reference_step',step_deck(self.model,c,variant,center),['.tran'],
                       lambda f,r:old.check_step(f/r['result_files']['.tran'][0],c,True))
            if not self.ok(r) or r.get('diagnostics',{}).get('trapezoidal_ringing'):
                self.skipped.append(dict(variant=variant,reason='STEP_OR_NUMERICAL_CHECK_FAILED'));continue
            for s in candidate_noise(c,variant,center):self.noise(s)
        return True

    def finish(self,prerequisites):
        if self.preview:self.persist('GENERATED_NOT_SIMULATED');return 0
        complete=prerequisites and not self.skipped and all(self.ok(r) for r in self.records)
        self.persist('COMPLETED_REVIEW_REQUIRED' if complete else 'INCOMPLETE_OR_PREREQUISITE_FAILED')
        return 0 if complete else 1


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--phase',choices=['numerics','candidates'],default='numerics')
    p.add_argument('--verify',action='store_true')
    p.add_argument('--generate-only',action='store_true')
    p.add_argument('--out',type=Path)
    p.add_argument('--finalize',type=Path)
    p.add_argument('--pack',type=Path)
    p.add_argument('--pdk',default=os.environ.get('PBIT_PDK_ROOT',e.DEFAULT_PDK))
    a=p.parse_args();e.verify_source()
    if a.finalize:e.finalize(a.finalize.resolve());return 0
    if a.pack:pack_results(a.pack);return 0
    c=json.loads((SOURCE/'config.json').read_text(encoding='utf-8'));validate(c)
    if a.verify:print('Source checksums and config: PASS');return 0
    if a.out is None:p.error('--out required')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    e.write_json(out/'config.json',c)
    _,model,discovery=discover_model(a.pdk);e.write_json(out/'pdk_discovery.json',discovery)
    if model is None:e.write_json(out/'summary.json',dict(status='BLOCKED_PDK'));return 2
    expected=json.loads((SOURCE/'local_pdk_hashes.json').read_text(encoding='utf-8'))
    hashes={'model/spectre/'+q.relative_to(model.parent).as_posix():e.digest(q)
            for q in model.parent.rglob('*') if q.is_file()}
    matches=all(hashes.get(k)==v for k,v in expected.items())
    e.write_json(out/'pdk_comparison.json',dict(matches_local=matches,hashes=hashes))
    if not matches:e.write_json(out/'summary.json',dict(status='BLOCKED_PDK_HASH'));return 2
    e.write_json(out/'metadata.json',dict(utc=datetime.utcnow().isoformat()+'Z',phase=a.phase,
        python=sys.version,host=os.environ.get('HOSTNAME'),job=os.environ.get('SLURM_JOB_ID'),
        model=str(model),scope=c['scope'],baseline_job=c['baseline_job'],
        baseline_archive_sha256=c['baseline_archive_sha256'],config_sha256=e.digest(SOURCE/'config.json'),
        git_revision='N/A standalone EDA; exact source identified by source/package_manifest.json',
        cost_boundary='core + comparator + ideal reference current consumption; no reference generator or DAC implementation'))
    exe=None if a.generate_only else shutil.which(os.environ.get('SPECTRE_BIN','spectre'))
    if not a.generate_only and not exe:e.write_json(out/'summary.json',dict(status='BLOCKED_NO_SPECTRE'));return 2
    if exe:
        for label,opts in [('version',['-W']),('tran_help',['-h','tran'])]:
            with (out/(label+'.txt')).open('w') as f:
                subprocess.run([exe]+opts,stdout=f,stderr=subprocess.STDOUT,timeout=30)
    study=Study(out,model,c,exe,a.generate_only,a.phase)
    try:
        prerequisites=study.numerical_phase() if a.phase=='numerics' else study.candidate_phase()
    except Exception:
        study.persist('DRIVER_EXCEPTION; inspect job log and retained cases')
        raise
    return study.finish(prerequisites)


if __name__=='__main__':sys.exit(main())
