"""Bare MOS core statistics driver. Python >=3.6; standard library only."""
import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pdk_discovery import discover_model

DEFAULT_PDK = '/public3/home/t6s011227/ICsprout_55LLULP1225_1P6M_5Ic_1T4Mc_RDL1_v1p11/ICsprout_55LLULP1225_1P6M_5Ic_1T4Mc_RDL1_v1p11'
SOURCE = Path(__file__).resolve().parent
REAL = re.compile(r'^"([^\"]+)"[ \t]+(?:"[^\"]+"[ \t]+)?([-+0-9.eE]+)[ \t]*$')


def write_json(path, obj):
    with path.open('w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def verify_source():
    manifest = json.loads((SOURCE/'package_manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest.items():
        if digest(SOURCE/name) != expected:
            raise ValueError('Source checksum mismatch: '+name)


def read_values(path):
    """Yield scalar PSF values, supporting sweep and typed single-point DC."""
    active = False
    with path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line == 'VALUE':
                active = True
                continue
            if active and line == 'END':
                break
            if active:
                m = REAL.match(line)
                if m:
                    value = float(m.group(2))
                    if not math.isfinite(value):
                        raise ValueError('Nonfinite PSF value')
                    yield m.group(1).lower(), value
    if not active:
        raise ValueError('Missing PSF VALUE section')


def validate_config(c):
    assert c['seeds'] == [17, 29, 43], 'This protocol requires three specified seeds'
    assert c['noisefmin_Hz'] == [5000, 500], 'This protocol requires both cutoff settings'
    for key in ('stop_s','strobe_s','maxstep_s','noisefmax_Hz','cextra_F','case_timeout_s'):
        assert math.isfinite(c[key]) and c[key] > 0, key
    assert 0 <= c['discard_s'] < c['stop_s']
    assert min(c['noisefmin_Hz']) > 1/c['stop_s']
    assert c['maxstep_s'] <= .5/c['noisefmax_Hz']
    assert abs(c['stop_s']/c['strobe_s']-round(c['stop_s']/c['strobe_s'])) < 1e-6
    assert 0 < c['vn_V'] < c['vdd_V'] and 0 < c['vp_V'] < c['vdd_V']


def circuit(model, c):
    model = model.as_posix()
    if any(x in model for x in ('"','\n','\r')):
        raise ValueError('Unsupported PDK path')
    return '''simulator lang=spectre insensitive=yes
include "{model}" section=tt_mos
simulatorOptions options temp={temperature_C:.16g} reltol=1e-5 vabstol=1e-7 iabstol=1e-16 gmin=1e-14
VDD (vdd 0) vsource dc={vdd_V:.16g}
VGN (gn 0) vsource dc={vn_V:.16g}
VGP (gp 0) vsource dc={vp_V:.16g}
XN (out gn 0 0) nm1p2_svt_lp w=1u l=1u nf=1 mr=1 prelayout=1
XP (out gp vdd vdd) pm1p2_svt_lp w=1u l=1u nf=1 mr=1 prelayout=1
Cload (out 0) capacitor c={cextra_F:.16g}
Itest (0 out) isource dc=0 mag=1
save out VDD:p
'''.format(model=model, **c)


def make_cases(model, c):
    base = circuit(model, c)
    cases = [('00_op_ac_noise', base+'''dcOp dc
opInfo info what=oppoint where=file file="oppoint.txt"
acCore ac start=1 stop=100M dec=30
noiseCore (out 0) noise start=1 stop=100M dec=30 iprobe=Itest
''', ['.dc','.ac','.noise'], None)]
    cases.append(('01_noiseless', base+'tranBase tran stop=2m maxstep=10n strobeperiod=20n strobeoutput=strobeonly\n', ['.tran'], None))
    for floor in c['noisefmin_Hz']:
        for seed in c['seeds']:
            analysis = ('tranStats tran stop={stop_s:.16g} maxstep={maxstep_s:.16g} '
                        'strobeperiod={strobe_s:.16g} strobeoutput=strobeonly '
                        'noisefmin={floor} noisefmax={noisefmax_Hz:.16g} '
                        'noiseseed={seed} noisescale=1\n').format(floor=floor, seed=seed, **c)
            cases.append(('noise_fmin{}_seed{}'.format(floor, seed),base+analysis,['.tran'],
                          dict(seed=seed, noisefmin_Hz=floor)))
    return cases


def basic_trace_check(path, stop, strobe, discard):
    """Check complete uniform output and compute bounded-memory descriptive stats."""
    count = 0
    kept = 0
    mean = m2 = 0.
    low, high = float('inf'), -float('inf')
    time = last = None
    saw_out = True
    expected_points = int(round(stop/strobe))+1
    duplicate_terminal = False
    ignored_terminal_points = 0
    last_out = None
    for key, value in read_values(path):
        if key == 'time':
            if not saw_out:
                raise ValueError('Missing output for a time point')
            time = value
            expected = count*strobe
            duplicate_terminal = (count == expected_points and ignored_terminal_points == 0
                                  and last is not None and abs(last-stop) <= 1e-12
                                  and abs(time-stop) <= 1e-12 and time >= last)
            if duplicate_terminal:
                ignored_terminal_points += 1
            elif abs(time-expected) > 1e-12 or ignored_terminal_points:
                raise ValueError('Missing/nonuniform strobe sample at '+str(time))
            else:
                count += 1
            saw_out = False
        elif key == 'out':
            if time is None or saw_out:
                raise ValueError('Unexpected output point')
            saw_out = True
            if duplicate_terminal:
                if abs(value-last_out) > 1e-6:
                    raise ValueError('Conflicting near-duplicate terminal voltage')
                continue
            last = time
            last_out = value
            # Time tolerance includes the nominal discard-boundary point.
            if time >= discard-1e-12:
                kept += 1
                delta = value-mean
                mean += delta/kept
                m2 += delta*(value-mean)
                low, high = min(low,value), max(high,value)
    if last is None or abs(last-stop)>1e-12 or count != int(round(stop/strobe))+1 or not saw_out or kept<2:
        raise ValueError('Incomplete transient record')
    return dict(points=count, ignored_duplicate_terminal_points=ignored_terminal_points,
                retained_points=kept, mean_V=mean, std_V=math.sqrt(max(m2,0)/(kept-1)),
                min_V=low, max_V=high, last_time_s=last,
                interpretation='DESCRIPTIVE_ONLY_CORRELATION_AND_UNCERTAINTY_REVIEW_PENDING')


def run_case(exe, folder, suffixes, timeout):
    command=[exe,'+spice','-mt','input.scs','-format','psfascii','-raw','raw','+log','spectre.log']
    write_json(folder/'command.json', command)
    timed_out=False
    with (folder/'console.txt').open('w',encoding='utf-8') as stream:
        try:
            rc=subprocess.run(command,cwd=str(folder),stdout=stream,stderr=subprocess.STDOUT,timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            rc,timed_out=124,True
        except OSError as exc:
            stream.write(str(exc)); rc=127
    log=folder/'spectre.log'
    text=log.read_text(errors='replace') if log.exists() else ''
    errors=re.findall(r'^\s*(?:ERROR|FATAL)\b.*$',text,re.M|re.I)
    audit=re.findall(r'spectre completes with (\d+) errors?, (\d+) warnings?, and (\d+) notices?',text,re.I)
    results={s:[p for p in (folder/'raw').glob('*'+s) if p.is_file() and p.stat().st_size] for s in suffixes}
    ok=rc==0 and not timed_out and not errors and bool(audit) and int(audit[-1][0])==0 and all(results.values())
    return dict(status='COMPLETED_REVIEW_REQUIRED' if ok else 'FAILED',returncode=rc,timed_out=timed_out,
                error_lines=errors, aggregate_audit=list(map(int,audit[-1])) if audit else None,
                result_files={s:[p.relative_to(folder).as_posix() for p in paths] for s,paths in results.items()})


def finalize(directory):
    manifest={p.relative_to(directory).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p))
              for p in sorted(directory.rglob('*')) if p.is_file() and p.name!='result_manifest.json'}
    write_json(directory/'result_manifest.json',manifest)


def pack(directory):
    manifest=json.loads((directory/'result_manifest.json').read_text(encoding='utf-8'))
    for name, value in manifest.items():
        path=(directory/name).resolve()
        if directory not in path.parents or digest(path)!=value['sha256']:
            raise ValueError('Result checksum mismatch or invalid path: '+name)
    target=directory.parent.parent/('core_statistics_'+directory.name+'.tar.gz')
    if target.exists():
        raise ValueError('Archive already exists; keep the existing archive: '+str(target))
    # Temporary output on the same filesystem; publish the final name only after closing tar.
    fd,temp=tempfile.mkstemp(prefix='.packing-',suffix='.tmp',dir=str(target.parent))
    os.close(fd)
    try:
        with tarfile.open(temp,'w:gz') as archive:
            for name in list(manifest)+['result_manifest.json']:
                archive.add(str(directory/name),arcname=directory.name+'/'+name,recursive=False)
        os.replace(temp,str(target))
    finally:
        if os.path.exists(temp): os.unlink(temp)
    print('ARCHIVE='+str(target),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--verify',action='store_true')
    p.add_argument('--generate-only',action='store_true')
    p.add_argument('--out',type=Path)
    p.add_argument('--finalize',type=Path)
    p.add_argument('--pack',type=Path)
    p.add_argument('--pdk',default=os.environ.get('PBIT_PDK_ROOT',DEFAULT_PDK))
    args=p.parse_args()
    verify_source()
    if args.finalize:
        finalize(args.finalize.resolve()); return 0
    if args.pack:
        pack(args.pack.resolve()); return 0
    c=json.loads((SOURCE/'config.json').read_text(encoding='utf-8'))
    validate_config(c)
    if args.verify:
        print('Source checksums and configuration: PASS'); return 0
    if args.out is None: p.error('--out is required')
    out=args.out.resolve(); out.mkdir(parents=True,exist_ok=False)
    write_json(out/'config.json',c)
    _,model,discovery=discover_model(args.pdk)
    write_json(out/'pdk_discovery.json',discovery)
    if model is None:
        write_json(out/'summary.json',dict(status='BLOCKED_PDK')); return 2
    expected=json.loads((SOURCE/'local_pdk_hashes.json').read_text(encoding='utf-8'))
    hashes={'model/spectre/'+q.relative_to(model.parent).as_posix():digest(q) for q in model.parent.rglob('*') if q.is_file()}
    matches=all(hashes.get(k)==v for k,v in expected.items())
    write_json(out/'pdk_comparison.json',dict(matches_local=matches,hashes=hashes))
    if not matches:
        write_json(out/'summary.json',dict(status='BLOCKED_PDK_HASH')); return 2
    write_json(out/'metadata.json',dict(utc=datetime.utcnow().isoformat()+'Z',job=os.environ.get('SLURM_JOB_ID'),
        host=os.environ.get('HOSTNAME'),python=sys.version,model=str(model),config_sha256=digest(SOURCE/'config.json'),
        scope='BARE_CORE_STATISTICS_NO_COMPARATOR',baseline_job=c['baseline_job'],
        git_revision='N/A: standalone EDA project; exact code identified by source/package_manifest.json'))
    cases=make_cases(model,c)
    for name,deck,_,_ in cases:
        folder=out/name; folder.mkdir()
        with (folder/'input.scs').open('w',encoding='utf-8',newline='\n') as f: f.write(deck)
    if args.generate_only:
        write_json(out/'summary.json',dict(status='GENERATED_NOT_SIMULATED',cases=[x[0] for x in cases])); return 0
    exe=shutil.which(os.environ.get('SPECTRE_BIN','spectre'))
    if not exe:
        write_json(out/'summary.json',dict(status='BLOCKED_NO_SPECTRE')); return 2
    for label,options in [('version',['-W']),('tran_help',['-h','tran']),('noise_help',['-h','noise'])]:
        with (out/(label+'.txt')).open('w') as stream:
            try: subprocess.run([exe]+options,stdout=stream,stderr=subprocess.STDOUT,timeout=15)
            except (OSError,subprocess.TimeoutExpired) as exc: stream.write(str(exc))
    records=[]
    for name,_,suffixes,setting in cases:
        folder=out/name
        status=run_case(exe,folder,suffixes,c['case_timeout_s'] if setting else 120)
        if status['status']=='COMPLETED_REVIEW_REQUIRED':
            try:
                if name=='00_op_ac_noise':
                    values=dict(read_values(folder/'raw/dcOp.dc'))
                    voltage,current=values['out'],-values['vdd:p']
                    if not .599 <= voltage <= .601 or not 15e-9 <= current <= 18e-9:
                        raise ValueError('Working point drifted from the validated baseline')
                    if not (folder/'oppoint.txt').is_file() or not (folder/'oppoint.txt').stat().st_size:
                        raise ValueError('Missing device operating points')
                    status['working_point']=dict(out_V=voltage,supply_current_A=current)
                else:
                    trace=folder/status['result_files']['.tran'][0]
                    status['trace_check']=basic_trace_check(trace,c['stop_s'] if setting else .002,
                                                            c['strobe_s'],c['discard_s'] if setting else .0002)
            except (ValueError,KeyError,IndexError,OSError) as exc:
                status['status']='FAILED_OUTPUT_CHECK'; status['check_error']=str(exc)
        write_json(folder/'status.json',status)
        records.append(dict(case=name,setting=setting,**status))
        write_json(out/'summary.json',dict(status='IN_PROGRESS',cases=records))
        print(name+': '+status['status'],flush=True)
        if name=='00_op_ac_noise' and status['status']!='COMPLETED_REVIEW_REQUIRED':
            write_json(out/'summary.json',dict(status='BLOCKED_WORKPOINT_OR_SMALL_SIGNAL',cases=records)); return 1
    complete=all(x['status']=='COMPLETED_REVIEW_REQUIRED' for x in records)
    write_json(out/'summary.json',dict(status='COMPLETED_REVIEW_REQUIRED' if complete else 'INCOMPLETE_OR_FAILED',
        cases=records,independent_seeds_per_cutoff=3,statistical_acceptance='PENDING_OFFLINE_REVIEW'))
    return 0 if complete else 1


if __name__=='__main__':
    sys.exit(main())
