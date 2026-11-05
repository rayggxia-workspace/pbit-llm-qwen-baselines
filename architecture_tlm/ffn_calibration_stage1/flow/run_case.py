"""One immutable functional -> DC -> optional PT-STA run. Python >=3.8."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import uuid

from parse_results import EvidenceError, parse_stage

IDENTIFIER = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
REPORT_NAMES = {'setup.rpt', 'hold.rpt', 'area.rpt', 'constraints.rpt',
                'check_design.rpt', 'check_timing.rpt', 'mapping_audit.txt',
                'setup_slack_ns.txt', 'hold_slack_ns.txt', 'pvt.txt',
                'STAGE_COMPLETE', 'FLOW_FAILED.txt'}


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write('\n')


def load_cases(package):
    data = json.loads((Path(package)/'cases.json').read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('cases'), list):
        raise EvidenceError('Expected cases.json schema_version=1 and cases list')
    cases = data['cases']
    seen = set()
    for item in cases:
        if not all(IDENTIFIER.fullmatch(item.get(k, '')) for k in ('id', 'top')):
            raise EvidenceError('Unsafe/invalid case id or top')
        if item['id'] in seen or not isinstance(item.get('smoke'), bool):
            raise EvidenceError('Duplicate case or missing boolean smoke field')
        seen.add(item['id'])
    if not cases:
        raise EvidenceError('Empty case set')
    return cases


def source_inventory(package):
    package = Path(package).resolve()
    files = [package/'cases.json']
    for folder in ('rtl', 'tests', 'flow'):
        root = package/folder
        if not root.is_dir():
            raise EvidenceError('Missing source folder ' + folder)
        for path in root.rglob('*'):
            if any(part in ('__pycache__', '.git') for part in path.relative_to(package).parts):
                continue
            if path.is_symlink():
                raise EvidenceError('Source symlink not allowed: ' + str(path))
            if not path.is_file():
                continue
            if path.name in ('env.sh', 'setup.sh') or path.suffix.lower() in ('.db','.lib','.lef','.vcd','.ddc','.pem','.key','.pyc'):
                raise EvidenceError('Private/generated file in portable source tree: '+str(path))
            files.append(path)
    if not list((package/'rtl').glob('*.sv')):
        raise EvidenceError('Missing rtl/*.sv')
    if len(files) > 10000 or sum(p.stat().st_size for p in files) > 50*1024**2:
        raise EvidenceError('Source tree unexpectedly large; refuse implicit large copy')
    return {str(p.relative_to(package)).replace('\\','/'):digest(p) for p in sorted(files)}


def snapshot(source, target):
    source, target = Path(source), Path(target)
    inventory = source_inventory(source)
    target.mkdir(exist_ok=False)
    for name in inventory:
        dst = target/name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source/name, dst)
    if source_inventory(target) != inventory or source_inventory(source) != inventory:
        raise EvidenceError('Source changed during snapshot')
    return inventory


def run_process(command, cwd, env, timeout, log, receipt):
    result = dict(command=command, cwd=str(cwd), start_utc=utc(), timeout_seconds=timeout)
    start = time.monotonic()
    try:
        with Path(log).open('wb') as output:
            proc = subprocess.Popen(command, cwd=str(cwd), env=env, stdout=output,
                                    stderr=subprocess.STDOUT, start_new_session=(os.name=='posix'))
            try:
                result['returncode'] = proc.wait(timeout=timeout)
                result['status'] = 'completed' if proc.returncode == 0 else 'failed'
            except subprocess.TimeoutExpired:
                result['status'] = 'timeout'
                if os.name == 'posix':
                    os.killpg(proc.pid, signal.SIGTERM)
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if os.name == 'posix': os.killpg(proc.pid, signal.SIGKILL)
                    else: proc.kill()
                    proc.wait()
                result['returncode'] = proc.returncode
    except OSError as exc:
        result.update(status='failed_to_start', error=str(exc), returncode=None)
    result.update(end_utc=utc(), wall_seconds=time.monotonic()-start)
    if Path(log).is_file(): result['log_sha256']=digest(log)
    save(receipt, result)
    if result['status'] != 'completed':
        raise EvidenceError('Stage '+result['status']+': '+str(receipt))
    return result


def verify_functional(summary, case_id, inventory):
    data = json.loads(Path(summary).read_text(encoding='utf-8'))
    if data.get('status') != 'passed' or data.get('case_id') != case_id:
        raise EvidenceError('Functional summary absent, unsuccessful or wrong case')
    reported = data.get('source_sha256', {})
    required = {k:v for k,v in inventory.items() if k.startswith(('rtl/','tests/'))}
    for name, sha in required.items():
        if reported.get(name) != sha:
            raise EvidenceError('Functional source SHA missing/mismatch: '+name)
    return data


def archive_reports(run):
    run = Path(run)
    names = ['RESULT.json','CONFIGURATION.json','SOURCE_MANIFEST.json']
    names += [str(p.relative_to(run)) for p in (run/'receipts').glob('*.json')]
    for stage in ('dc','pt'):
        folder = run/'work'/stage
        if folder.is_dir():
            names += [str(p.relative_to(run)) for p in folder.iterdir() if p.name in REPORT_NAMES and p.is_file()]
    if (run/'work/functional/summary.json').is_file():
        names.append('work/functional/summary.json')
    # Explicit allowlist: no .db, .lib, mapped netlist, tool work libraries,
    # library_private.rpt, licensed model, waveforms or complete tool logs.
    names = sorted(set(n for n in names if (run/n).is_file()))
    save(run/'RETURN_MANIFEST.json', {'files':{n:digest(run/n) for n in names},
            'excluded':'netlists, libraries, library reports, waveforms and full tool logs stay local'})
    names.append('RETURN_MANIFEST.json')
    with tarfile.open(run/'reports.tar.gz', 'w:gz') as archive:
        for name in names:
            archive.add(run/name, arcname=name, recursive=False)
    save(run/'ARCHIVE.json',dict(file='reports.tar.gz',sha256=digest(run/'reports.tar.gz'),bytes=(run/'reports.tar.gz').stat().st_size))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case-id',required=True)
    p.add_argument('--corner',choices=['ss','tt'],required=True)
    p.add_argument('--output-root',required=True)
    p.add_argument('--timeout',type=int,default=3600,help='seconds per functional/DC/PT stage')
    p.add_argument('--with-pt-sta',action='store_true')
    p.add_argument('--functional-simulator',choices=['vcs','iverilog'],default='vcs')
    args=p.parse_args(argv)
    if not IDENTIFIER.fullmatch(args.case_id) or args.timeout<1:
        p.error('Invalid case ID/timeout')
    package=Path(__file__).resolve().parents[1]
    root=Path(args.output_root).expanduser().resolve()
    if root==package or package in root.parents:
        p.error('Output root must be outside immutable source package')
    root.mkdir(parents=True,exist_ok=True)
    run=root/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+args.case_id+'_'+args.corner+'_'+uuid.uuid4().hex[:8])
    run.mkdir(exist_ok=False);(run/'receipts').mkdir();(run/'work').mkdir()
    result=dict(schema_version=1,status='failed',case_id=args.case_id,corner=args.corner,
                start_utc=utc(),run_directory=str(run),power_W=None,energy_J=None,
                stage='preflight',stages={},limits=['prelayout only','no activity-based power analysis'])
    lock=None;token=uuid.uuid4().hex
    try:
        locks=root/'.locks';locks.mkdir(exist_ok=True)
        candidate=locks/(args.case_id+'_'+args.corner+'.lock')
        fd=os.open(str(candidate),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as stream: json.dump(dict(token=token,pid=os.getpid(),run=str(run),started=utc()),stream)
        lock=candidate
        cases={x['id']:x for x in load_cases(package)}
        if args.case_id not in cases:raise EvidenceError('Unknown case ID')
        case=cases[args.case_id]
        library=Path(os.environ.get('STD_DB','')).expanduser().resolve()
        if not library.is_file() or library.suffix.lower()!='.db':raise EvidenceError('STD_DB must be one existing .db file')
        ref=os.environ.get('STD_REF_CELL','INVX1_9TSVT')
        if not IDENTIFIER.fullmatch(ref):raise EvidenceError('Invalid reference-cell name')
        dc=shutil.which(os.environ.get('DC_SHELL','dc_shell'))
        pt=shutil.which(os.environ.get('PT_SHELL','pt_shell')) if args.with_pt_sta else None
        if not dc or (args.with_pt_sta and not pt):raise EvidenceError('Required DC/PT executable not found; source tool setup first')
        inventory=snapshot(package,run/'source')
        env_file=os.environ.get('FLOW_ENV_FILE')
        config=dict(schema_version=1,case=case,corner=args.corner,node_nm=55,
                    voltage_V=1.08 if args.corner=='ss' else 1.2,temperature_C=125 if args.corner=='ss' else 25,
                    clock_MHz=100,period_ns=10,setup_uncertainty_ns=2,hold_uncertainty_ns=.1,
                    input_delay_max_ns=1,input_delay_min_ns=.2,output_delay_max_ns=1,output_delay_min_ns=.2,
                    transition_ns=.1,load_pF=.02,reset='synchronous rst_n; timed; no false path',
                    STD_DB=str(library),STD_DB_sha256=digest(library),STD_REF_CELL=ref,
                    environment_setup_path=env_file,environment_setup_sha256=digest(env_file) if env_file else None,
                    source_package=str(package),dc_executable=dc,pt_executable=pt,
                    python=sys.version,timeout_seconds_per_stage=args.timeout,
                    slurm_job_id=os.environ.get('SLURM_JOB_ID'),slurm_array_task_id=os.environ.get('SLURM_ARRAY_TASK_ID'))
        save(run/'SOURCE_MANIFEST.json',dict(schema_version=1,source_sha256=inventory))
        save(run/'CONFIGURATION.json',config)
        result['configuration_sha256']=digest(run/'CONFIGURATION.json')
        result['source_manifest_sha256']=digest(run/'SOURCE_MANIFEST.json')
        env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',FLOW_PACKAGE=str(run/'source'),
            FLOW_CORNER=args.corner,FLOW_TOP=case['top'],STD_DB=str(library),STD_REF_CELL=ref)
        result['stage']='functional'
        command=[sys.executable,str(run/'source/tests/run_all.py'),'--output',str(run/'work/functional'),
                 '--case-id',args.case_id,'--simulator',args.functional_simulator]
        run_process(command,run/'source',env,args.timeout,run/'functional.log',run/'receipts/functional.json')
        functional=verify_functional(run/'work/functional/summary.json',args.case_id,inventory)
        result['stages']['functional']=dict(status='passed',summary_sha256=digest(run/'work/functional/summary.json'))
        if source_inventory(run/'source')!=inventory:raise EvidenceError('Execution source changed during functional stage')
        for stage, executable, script in [('dc',dc,'dc.tcl')]+([('pt',pt,'pt_sta.tcl')] if args.with_pt_sta else []):
            result['stage']=stage
            folder=run/'work'/stage;folder.mkdir(exist_ok=False)
            env.update(FLOW_TOOL=stage,FLOW_DC_DIR=str(run/'work/dc'))
            run_process([executable,'-f',str(run/'source/flow'/script)],folder,env,args.timeout,
                        run/(stage+'.log'),run/'receipts'/(stage+'.json'))
            parsed=parse_stage(folder,run/(stage+'.log'),args.corner,stage)
            result['stages'][stage]=parsed
            if source_inventory(run/'source')!=inventory:raise EvidenceError('Execution source changed during '+stage)
        if digest(library)!=config['STD_DB_sha256']:raise EvidenceError('Library file changed during execution')
        result['status']='not_met' if any(x.get('status')=='not_met' for x in result['stages'].values()) else 'met'
        result['stage']='completed'
    except Exception as exc:
        result.update(status='failed',error=type(exc).__name__+': '+str(exc))
    finally:
        result['end_utc']=utc();save(run/'RESULT.json',result)
        archive_reports(run)
        if lock is not None and lock.is_file():
            # Release only the lock created by this process. A killed job may
            # leave a lock; inspect its receipt instead of auto-breaking it.
            if json.loads(lock.read_text()).get('token')==token:lock.unlink()
    print(json.dumps(dict(status=result['status'],run_directory=str(run),archive=str(run/'reports.tar.gz')),ensure_ascii=False))
    return {'met':0,'not_met':3,'failed':2}[result['status']]


if __name__=='__main__':
    raise SystemExit(main())
