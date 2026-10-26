"""Zero added core capacitance: bare baseline, frozen P50, real readout curves.

Python >=3.6, standard library only. One complete channel at a time; no mux,
bank, real DAC, reference generator or digital interface is included.
"""
import argparse
from datetime import datetime
import errno
import hashlib
import gzip
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile
import engine as e
import lowpower as lp
import run_characterization as old
import scan_measurements as scan
import measurements as m
import support
from pdk_discovery import discover_model

SOURCE = Path(__file__).resolve().parent
R = old.require


def validate(c):
    R(c['cextra_F'] == 0, 'This study removes Ccore entirely')
    R(c['vdd_V'] == 1.2 and c['temperature_C'] == 25 and c['vn_V'] == .3, 'Frozen core bias')
    R(c['vp_V'] == .8998115919357365 and c['gmin'] == 1e-15, 'Frozen PDK baseline')
    R(c['output_load_F'] == 5e-15, 'Cbit is retained; it is not Cextra')
    R(c['calibration_seeds'] == [17,29,43] and c['validation_seeds'] == [401,503,607], 'Predeclared seed sets')
    R(c['curve_seeds'] == [809,907,1009], 'Independent probability-curve seeds')
    R(c['calibration_offsets_V'] == [-.008,-.004,0,.004,.008], 'Five fixed calibration points')
    R(c['curve_offsets_V'] == [-.04,-.02,-.01,-.005,0,.005,.01,.02,.04], 'Real Vref curve grid')
    R(c['noisefmin_Hz'] == 500 and c['noisefmax_Hz'] == 100e6 and c['maxstep_s'] == 2.5e-9, 'Frozen noise band/timestep')
    R(c['stop_s'] == .02 and c['discard_s'] == .002 and c['strobe_s'] == 1e-7, 'Held-out comparator protocol')
    R(c['bare_strobe_s'] == 20e-9, 'Bare time resolution')
    R(c['calibration_stop_s'] == .005 and c['calibration_discard_s'] == .0005, 'Calibration window')
    R(c['curve_stop_s'] == .003 and c['curve_discard_s'] == .0005, 'Curve window')
    R(c['window_lengths'] == [32,128] and c['window_intervals_us'] == [.1,.2,.5,1,2,5,10], 'Window diagnostics')
    R([v['name'] for v in c['candidates']] == ['b1_p2_b2_n2','buffers_x2'], 'Existing candidates only')
    expected=[dict(buf1_p_scale=2,buf2_n_scale=2),dict(buf1_n_scale=2,buf1_p_scale=2,buf2_n_scale=2,buf2_p_scale=2)]
    for v,scales in zip(c['candidates'],expected):
        R(v['rail_V'] == .8 and v['bias_A'] == 1e-8 and v['baseline'] is False, 'Comparator bias')
        R({k:x for k,x in v.items() if k.startswith('buf')} == scales, 'Frozen device sizing')
    R([v['initial_reference_V'] for v in c['candidates']] == [.6035741270011059,.6073854664811053], 'Historical calibration centres')
    for k in ['case_timeout_s','gate_timeout_s','calibration_timeout_s']:
        R(math.isfinite(c[k]) and c[k] > 0, k)
    for stage in ['bare','calibration','curve','validation']:
        q=setting(c,stage,c['validation_seeds'][0])
        R(0 <= q['discard_s'] < q['stop_s'] and q['maxstep_s'] <= .5/q['noisefmax_Hz'], 'Window/timestep')
        for key in ['stop_s','discard_s']:
            R(abs(q[key]/q['strobe_s']-round(q[key]/q['strobe_s'])) < 1e-6, 'Integral time grid')


def core(c):
    R(c['cextra_F'] == 0, 'Cextra must be zero')
    text=old.core(c)
    R(sum(line.startswith('Ccore ') for line in text.splitlines()) == 1, 'Known core capacitor')
    return ''.join(line for line in text.splitlines(True) if not line.startswith('Ccore '))


def setting(c,stage,seed):
    q=dict(c,seed=seed,stage=stage)
    if stage == 'bare': q['strobe_s']=c['bare_strobe_s']
    elif stage in ['calibration','curve']:
        q.update(stop_s=c[stage+'_stop_s'],discard_s=c[stage+'_discard_s'])
    R(stage in ['bare','calibration','curve','validation'], 'Unknown trace stage')
    return q


def build(model,c,variant,kind,reference=None,q=None,sweep=None):
    R(c['cextra_F'] == 0, 'No added core capacitance')
    loaded=variant is not None
    s=old.header(model,c).replace('gmin=1e-14','gmin={:.16g}'.format(c['gmin']))
    s+='VIN (out 0) vsource dc=0.6\n' if kind == 'dc' else core(c)
    if loaded:
        s+=lp.comparator(c,variant,'screen')
        if kind == 'dc': s+='parameters vref={:.16g}\nVREF (ref 0) vsource dc=vref\n'.format(sweep[0])
        elif kind == 'step':
            s+=('VREF (ref 0) vsource type=pulse val0={:.16g} val1={:.16g} '
                'delay=100u rise=100n fall=100n width=100u period=200u\n').format(reference-.01,reference+.01)
        else:
            R(reference is not None and math.isfinite(reference), 'Reference required')
            s+='VREF (ref 0) vsource dc={:.16g}\n'.format(reference)
    if kind == 'dc':
        s+='save out bit\ndcTransfer dc param=vref start={:.16g} stop={:.16g} step={:.16g}\n'.format(*sweep)
    elif kind == 'op_ac_noise':
        s+=lp.save(variant,'screen',bare=not loaded)
        s+=('Itest (0 out) isource dc=0 mag=1\ndcOp dc\n'
            'opInfo info what=oppoint where=file file="oppoint.txt"\n'
            'acCore ac start=1 stop=1G dec=30\n'
            'noiseCore (out 0) noise start=1 stop=1G dec=30 iprobe=Itest\n')
    elif kind == 'step':
        s+=lp.save(variant,'screen')+('tranStep tran stop={step_stop_s:.16g} maxstep={step_maxstep_s:.16g} '
            'strobeperiod={step_strobe_s:.16g} strobeoutput=strobeonly method=trap\n').format(**c)
    else:
        R(q is not None and kind in ['bare','calibration','curve','validation'], 'Trace parameters required')
        s+=('save out bit\n' if kind in ['calibration','curve'] else 'save out VDD:p'+(' bit VDC:p' if loaded else '')+'\n')
        s+=('tranNoise tran stop={stop_s:.16g} maxstep={maxstep_s:.16g} '
            'strobeperiod={strobe_s:.16g} strobeoutput=strobeonly method=trap '
            'noisefmin={noisefmin_Hz:.16g} noisefmax={noisefmax_Hz:.16g} noiseseed={seed} noisescale=1\n').format(**q)
    R('Ccore ' not in s, 'No zero-valued Ccore allowed')
    return s


def expected_count(c=None):
    return 4+2*(5+15+24+3)


def copy_source(source,destination):
    """Copy bytes into fresh writable files, never source modes/timestamps."""
    source=Path(source).resolve();destination=Path(destination).resolve()
    R(not destination.exists(), 'Refusing to overwrite source snapshot')
    manifest=json.loads((source/'package_manifest.json').read_text(encoding='utf-8'))
    destination.mkdir(parents=True)
    for name in list(manifest)+['package_manifest.json']:
        rel=PurePosixPath(name)
        R(rel.parts and not rel.is_absolute() and '..' not in rel.parts and '\\' not in name and ':' not in name, 'Unsafe source name')
        src=source.joinpath(*rel.parts);dst=destination.joinpath(*rel.parts)
        R(src.is_file() and not src.is_symlink() and source in src.resolve().parents, 'Unsafe source file')
        dst.parent.mkdir(parents=True,exist_ok=True)
        with src.open('rb') as fi, dst.open('xb') as fo: shutil.copyfileobj(fi,fo,1024*1024)
        R(e.digest(src)==e.digest(dst), 'Source copy byte mismatch')
        if name in manifest: R(e.digest(dst)==manifest[name], 'Source manifest mismatch')
    return len(manifest)+1


def finalize(directory):
    directory=Path(directory).resolve()
    R(directory.is_dir(), 'Result directory required')
    snapshot=directory/'source'
    if not snapshot.exists(): copy_source(SOURCE,snapshot)
    # A retry may find a completed copy. Demand the exact submitted source,
    # rather than silently accepting an unrelated or partially copied tree.
    manifest=json.loads((SOURCE/'package_manifest.json').read_text(encoding='utf-8'))
    names=set(manifest)|{'package_manifest.json'}
    R(snapshot.is_dir() and not snapshot.is_symlink(), 'Unsafe source snapshot directory')
    R({p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*') if p.is_file()} == names, 'Existing source snapshot file set differs')
    for name in names:
        path=snapshot/name
        R(path.is_file() and not any(p.is_symlink() for p in [path]+list(path.parents) if p!=snapshot) and e.digest(path)==e.digest(SOURCE/name), 'Existing source snapshot mismatch: '+name)
    e.finalize(directory)


def publish_exclusive(temp,target):
    """Publish without replacing an existing name; portable hard-link fallback."""
    try:
        os.link(str(temp),str(target))
        return
    except OSError as exc:
        permitted={errno.EACCES,errno.EPERM,errno.EXDEV,errno.EINVAL,errno.ENOSYS,
                   getattr(errno,'ENOTSUP',errno.EPERM),getattr(errno,'EOPNOTSUPP',errno.EPERM)}
        if exc.errno not in permitted: raise
    # Some Windows sandboxes/filesystems disallow hard links. Exclusive-create
    # preserves overwrite protection, although the fallback final name is visible
    # during copying. The checksum sidecar appears only after a complete copy.
    created=None
    try:
        with Path(target).open('xb') as out:
            created=os.fstat(out.fileno())
            with Path(temp).open('rb') as source: shutil.copyfileobj(source,out,1024*1024)
        R(e.digest(Path(temp))==e.digest(Path(target)), 'Published archive copy mismatch')
    except Exception:
        if created is not None:
            try:
                current=Path(target).stat()
                if current.st_ino==created.st_ino and current.st_dev==created.st_dev: Path(target).unlink()
            except OSError: pass
        raise


def pack_results(directory):
    directory=Path(directory).resolve()
    R(directory.is_dir() and directory.parent.name == 'results', 'Expected results/JOB')
    target=directory.parent.parent/('zero_cap_readout_'+directory.name+'.tar.gz')
    R(not target.exists() and not Path(str(target)+'.sha256').exists(), 'Archive already exists')
    manifest_path=directory/'result_manifest.json'
    R(manifest_path.is_file() and not manifest_path.is_symlink(), 'Finalized manifest required')
    manifest_bytes=manifest_path.read_bytes()
    manifest=json.loads(manifest_bytes.decode('utf-8'));checked=[]
    manifest_info=dict(bytes=len(manifest_bytes),sha256=hashlib.sha256(manifest_bytes).hexdigest())
    for name,v in sorted(manifest.items()):
        rel=PurePosixPath(name)
        R(rel.parts and not rel.is_absolute() and '..' not in rel.parts and '\\' not in name and ':' not in name, 'Unsafe result name')
        path=directory.joinpath(*rel.parts)
        R(path.is_file() and directory in path.resolve().parents and not any(p.is_symlink() for p in [path]+list(path.parents) if p!=directory), 'Unsafe result file')
        R(path.stat().st_size == v['bytes'] and e.digest(path) == v['sha256'], 'Result checksum mismatch: '+name)
        checked.append((name,path))
    R({p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()} == set(manifest)|{'result_manifest.json'}, 'Result file set changed')
    fd,temp=tempfile.mkstemp(prefix='.packing-',suffix='.tmp',dir=str(target.parent));os.close(fd)
    try:
        archived={}
        with tarfile.open(temp,'w:gz',compresslevel=1) as archive:
            for name,path in checked+[('result_manifest.json',manifest_path)]:
                expected=manifest[name] if name in manifest else manifest_info
                member=tarfile.TarInfo(directory.name+'/'+name);member.size=expected['bytes'];member.mode=0o644
                class CheckedReader:
                    def __init__(self,stream): self.stream=stream;self.h=hashlib.sha256();self.n=0
                    def read(self,size=-1):
                        block=self.stream.read(size);self.h.update(block);self.n+=len(block);return block
                with path.open('rb') as stream:
                    reader=CheckedReader(stream);archive.addfile(member,reader)
                    R(not stream.read(1) and reader.n==expected['bytes'] and reader.h.hexdigest()==expected['sha256'], 'File changed during packing: '+name)
                archived[member.name]=expected
        # Verify the completed gzip bytes before publishing a final name.
        seen=set()
        with gzip.open(temp,'rb') as payload:
            with tarfile.open(fileobj=payload,mode='r|') as archive:
                for member in archive:
                    R(member.isfile() and member.name in archived and member.name not in seen, 'Unexpected archive member')
                    expected=archived[member.name];h=hashlib.sha256();n=0
                    stream=archive.extractfile(member)
                    for block in iter(lambda:stream.read(1024*1024),b''): h.update(block);n+=len(block)
                    R(n==expected['bytes'] and h.hexdigest()==expected['sha256'], 'Archive verification failed')
                    seen.add(member.name)
            # Force gzip CRC/footer verification even after tar end-of-archive.
            for block in iter(lambda:payload.read(1024*1024),b''): pass
        R(seen==set(archived), 'Missing archive member')
        R({p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()} == set(manifest)|{'result_manifest.json'}, 'Result file set changed during packing')
        publish_exclusive(Path(temp),target)
    finally:
        if os.path.exists(temp): os.unlink(temp)
    sha=e.digest(target)
    with Path(str(target)+'.sha256').open('x',encoding='ascii',newline='\n') as f: f.write(sha+'  '+target.name+'\n')
    print('ARCHIVE='+str(target)+'\nARCHIVE_SHA256='+sha,flush=True)
    return target


class Study:
    def __init__(self,out,model,c,exe,preview):
        self.out,self.model,self.c,self.exe,self.preview=out,model,c,exe,preview
        self.records=[];self.rejected=[];self.calibrations={};self.eligible=[];self.phase='bare'

    def persist(self,status):
        e.write_json(self.out/'summary.json',dict(status=status,phase=self.phase,cases=self.records,
            expected_cases=expected_count(self.c),calibrations=self.calibrations,rejected_candidates=self.rejected,
            noise_eligible=self.eligible,scope=self.c['scope'],physical_entropy_validated=False,
            numerical_acceptance='PENDING_OFFLINE_REVIEW',statistical_acceptance='PENDING_OFFLINE_REVIEW',
            packing_success_does_not_mean_simulation_success=True))

    @staticmethod
    def ok(r):
        return r['status'] in ['COMPLETED_REVIEW_REQUIRED','GENERATED_NOT_SIMULATED'] and not r.get('diagnostics',{}).get('trapezoidal_ringing',False)

    def run(self,name,v,kind,reference=None,q=None,sweep=None,freeze_sha=None):
        folder=self.out/name;folder.mkdir()
        with (folder/'input.scs').open('w',encoding='utf-8',newline='\n') as f:
            f.write(build(self.model,self.c,v,kind,reference,q,sweep))
        setting_record=dict(path=v['name'] if v else 'bare',kind=kind,reference_V=reference,
            sweep=list(sweep) if sweep else None,cextra_F=0,output_load_F=self.c['output_load_F'] if v else None,
            frozen_reference_sha256=freeze_sha,stage=self.phase,
            trace={k:q[k] for k in ['seed','stop_s','discard_s','strobe_s','maxstep_s','noisefmin_Hz','noisefmax_Hz']} if q else None)
        if self.preview: result=dict(status='GENERATED_NOT_SIMULATED')
        else:
            suffixes=['.dc','.ac','.noise'] if kind=='op_ac_noise' else ['.dc'] if kind=='dc' else ['.tran']
            timeout=self.c['calibration_timeout_s'] if kind in ['calibration','curve'] else self.c['case_timeout_s'] if q else self.c['gate_timeout_s']
            result=e.run_case(self.exe,folder,suffixes,timeout)
            result['diagnostics']=support.log_diagnostics(folder/'spectre.log')
            if self.ok(result):
                try:
                    for suffix in suffixes:
                        R(len(result['result_files'][suffix])==1, 'Ambiguous result file')
                        scan.complete_psf(folder/result['result_files'][suffix][0])
                    if kind=='dc': measurement=old.transfer(folder/'raw/dcTransfer.dc',*sweep,.8,abs(sweep[2])>1e-5)
                    elif kind=='op_ac_noise': measurement=scan.small_signal(folder,v is not None,self.c,v)
                    elif kind=='step': measurement=lp.check_step(folder/result['result_files']['.tran'][0],self.c,v,'screen')
                    elif kind in ['calibration','curve']: measurement=m.probability(folder/result['result_files']['.tran'][0],q)
                    elif kind=='bare': measurement=scan.stats(folder/result['result_files']['.tran'][0],q,False)
                    else: measurement=m.long_trace(folder/result['result_files']['.tran'][0],q)
                    result['measurements']=measurement
                except (ValueError,KeyError,IndexError,OSError,ZeroDivisionError) as exc:
                    result.update(status='FAILED_OUTPUT_CHECK',check_error=str(exc))
        e.write_json(folder/'status.json',result)
        self.records.append(dict(case=name,setting=setting_record,**result));self.persist('IN_PROGRESS')
        print(name+': '+result['status'],flush=True);return result

    def gates(self,v):
        name=v['name'];trips=[]
        for tag,sweep in [('forward',(.54,.67,.0001)),('reverse',(.67,.54,-.0001))]:
            r=self.run(name+'_dc_'+tag,v,'dc',sweep=sweep)
            if not self.ok(r): return None
            trips.append(v['previous_dc_V'] if self.preview else r['measurements']['reference_trip_V'])
        if abs(trips[0]-trips[1]) >= 20e-6: return None
        center=sum(trips)/2
        r=self.run(name+'_dc_fine',v,'dc',sweep=(center-.0005,center+.0005,5e-6))
        if not self.ok(r): return None
        if not self.preview: center=r['measurements']['reference_trip_V']
        if not self.ok(self.run(name+'_op_ac_noise',v,'op_ac_noise',center)): return None
        # This gate is deterministic at the measured DC trip. It is not the
        # stochastic P50 or an independence measurement.
        if not self.ok(self.run(name+'_step',v,'step',center)): return None
        return center

    def run_all(self):
        c=self.c
        bare_good=True
        if self.ok(self.run('bare_op_ac_noise',None,'op_ac_noise')):
            for seed in c['validation_seeds']:
                bare_good=self.ok(self.run('bare_long_seed'+str(seed),None,'bare',q=setting(c,'bare',seed))) and bare_good
        else: bare_good=False
        if not bare_good:
            self.rejected.append(dict(name='bare',reason='BARE_PREREQUISITE_FAILED; comparator stages not executed'))
            self.phase='prerequisite_failed';self.persist('INCOMPLETE_REVIEW_REQUIRED');return 1
        for v in c['candidates']:
            name=v['name'];self.phase=name+'_physical_gate';dc=self.gates(v)
            if dc is None:
                self.rejected.append(dict(name=name,reason='DC_HEADROOM_SMALL_SIGNAL_OR_STEP_GATE'));continue
            self.phase=name+'_calibration';points=[];complete=True
            for i,offset in enumerate(c['calibration_offsets_V']):
                ref=v['initial_reference_V']+offset;pp=[]
                for seed in c['calibration_seeds']:
                    r=self.run(name+'_cal{}_seed{}'.format(i,seed),v,'calibration',ref,setting(c,'calibration',seed))
                    if not self.ok(r): complete=False
                    elif not self.preview: pp.append(r['measurements']['p1'])
                points.append(dict(reference_V=ref,offset_V=offset,seed_p1=pp,mean_p1=sum(pp)/len(pp) if pp else None))
            selected=dict(status='PREVIEW_PLACEHOLDER_NOT_CALIBRATED',reference_V=v['initial_reference_V']) if self.preview else m.interpolate(points)
            self.calibrations[name]=dict(dc_trip_V=dc,points=points,selected=selected,calibration_seeds=c['calibration_seeds'])
            if not complete or 'reference_V' not in selected:
                self.rejected.append(dict(name=name,reason='P50_CALIBRATION_FAILED_NO_EXTRAPOLATION'));continue
            ref=selected['reference_V'];freeze_path=self.out/(name+'_frozen_reference.json')
            R(not freeze_path.exists(), 'Frozen selection already exists')
            e.write_json(freeze_path,dict(candidate=name,reference_V=ref,selection=selected,calibration=self.calibrations[name],
                heldout_seeds=c['validation_seeds'],curve_seeds=c['curve_seeds'],generated_only=self.preview,
                config_sha256=e.digest(SOURCE/'config.json'),policy='Calibration seeds only; never retune from held-out or curve records'))
            freeze_sha=e.digest(freeze_path);self.calibrations[name]['frozen_reference_sha256']=freeze_sha;self.eligible.append(name)
            self.phase=name+'_heldout'
            for seed in c['validation_seeds']:
                self.run(name+'_long_seed'+str(seed),v,'validation',ref,setting(c,'validation',seed),freeze_sha=freeze_sha)
            self.phase=name+'_real_reference_curve'
            for i,offset in enumerate(c['curve_offsets_V']):
                if offset == 0: continue  # central point uses the fresh long records above
                for seed in c['curve_seeds']:
                    self.run(name+'_curve{}_seed{}'.format(i,seed),v,'curve',ref+offset,setting(c,'curve',seed),freeze_sha=freeze_sha)
            R(e.digest(freeze_path)==freeze_sha, 'Frozen reference was changed')
        self.phase='finished'
        good=len(self.records)==expected_count(c) and not self.rejected and len(self.eligible)==2 and all(self.ok(r) for r in self.records)
        self.persist('GENERATED_NOT_SIMULATED' if self.preview and good else 'COMPLETED_REVIEW_REQUIRED' if good else 'INCOMPLETE_REVIEW_REQUIRED')
        return 0 if good else 1


def main():
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');p.add_argument('--generate-only',action='store_true')
    p.add_argument('--out',type=Path);p.add_argument('--finalize',type=Path);p.add_argument('--pack',type=Path)
    p.add_argument('--snapshot-source',type=Path)
    p.add_argument('--pdk',default=os.environ.get('PBIT_PDK_ROOT',e.DEFAULT_PDK));a=p.parse_args();e.verify_source()
    if a.snapshot_source: copy_source(SOURCE,a.snapshot_source);return 0
    if a.finalize: finalize(a.finalize);return 0
    if a.pack: pack_results(a.pack);return 0
    c=json.loads((SOURCE/'config.json').read_text(encoding='utf-8'));validate(c)
    if a.verify: print('Source checksums and zero-cap protocol: PASS; expected cases='+str(expected_count(c)));return 0
    if a.out is None: p.error('--out required')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);e.write_json(out/'config.json',c)
    e.write_json(out/'execution_plan.json',dict(expected_cases=expected_count(c),stages=['bare_4_cases','each_candidate_5_gate_cases','each_candidate_15_calibration_cases','freeze_P50','each_candidate_3_heldout_cases','each_candidate_24_real_Vref_curve_cases'],
        adaptive_reference_policy='Only DC fine sweep centre and P50 reference depend on prior measured calibration; no validation retuning',
        curve_zero_offset_source='Three 20ms held-out records; curve endpoints use separate curve seeds',
        failures='Failed physical gate/calibration prevents dependent cases; manifest and archive can still be produced',
        runtime_limits_are_upper_bounds_not_ETA=True))
    _,model,discovery=discover_model(a.pdk);e.write_json(out/'pdk_discovery.json',discovery)
    if model is None: e.write_json(out/'summary.json',dict(status='BLOCKED_PDK'));return 2
    expected=json.loads((SOURCE/'local_pdk_hashes.json').read_text(encoding='utf-8'))
    hashes={'model/spectre/'+q.relative_to(model.parent).as_posix():e.digest(q) for q in model.parent.rglob('*') if q.is_file()}
    matches=all(hashes.get(k)==v for k,v in expected.items());e.write_json(out/'pdk_comparison.json',dict(matches_local=matches,hashes=hashes))
    if not matches: e.write_json(out/'summary.json',dict(status='BLOCKED_PDK_HASH'));return 2
    e.write_json(out/'metadata.json',dict(utc=datetime.utcnow().isoformat()+'Z',job=os.environ.get('SLURM_JOB_ID'),host=os.environ.get('HOSTNAME'),python=sys.version,model=str(model),scope=c['scope'],
        source_manifest_sha256=e.digest(SOURCE/'package_manifest.json'),config_sha256=e.digest(SOURCE/'config.json'),generated_only=a.generate_only,
        baseline_job=c['baseline_job'],baseline_archive_sha256=c['baseline_archive_sha256'],git_revision='N/A standalone EDA; exact source manifest',
        cost_boundary='Two MOS core and one 15 MOS comparator, ideal bias draw counted; real DAC/reference/regulator/1.2V interface/mux/bank excluded',
        power_policy='Long uniform strobe mean is PROVISIONAL; no new all-solver-point power audit'))
    exe=None if a.generate_only else shutil.which(os.environ.get('SPECTRE_BIN','spectre'))
    if not a.generate_only and not exe: e.write_json(out/'summary.json',dict(status='BLOCKED_NO_SPECTRE'));return 2
    if exe:
        with (out/'version.txt').open('w',encoding='utf-8') as f: subprocess.run([exe,'-W'],stdout=f,stderr=subprocess.STDOUT,timeout=30)
    study=Study(out,model,c,exe,a.generate_only)
    try: return study.run_all()
    except Exception: study.persist('DRIVER_EXCEPTION_REVIEW_REQUIRED');raise


if __name__=='__main__': sys.exit(main())
