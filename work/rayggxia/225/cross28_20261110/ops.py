"""User-authorized CPU TLM submission using the existing EDA login helper."""
from pathlib import Path
import hashlib,json,sys
H=Path(__file__).resolve().parent;ROOT=H.parents[3];WS=ROOT.parents[1]
sys.path.insert(0,str(WS/'local_tools/paracloud_client'));import client
BASE='/public3/home/t6s011227/pbit_chimera_pipeline_20260920'

def save(name,x):(H/name).write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def remote(code,timeout=60):
    with client.connect(client.load_password()) as s:
        i,o,e=s.exec_command('python3 -B -',timeout=timeout);i.write(code);i.flush();i.channel.shutdown_write()
        raw=o.read().decode();err=e.read().decode();rc=o.channel.recv_exit_status()
        if rc:raise RuntimeError('remote rc='+str(rc)+' '+raw[-1500:]+' '+err[-1800:])
        return json.loads(raw)

def preflight():
    code='BASE='+repr(BASE)+'\n'+r'''
from pathlib import Path
import json,subprocess,sys,os,hashlib
q=subprocess.run(['squeue','-u',os.environ['USER'],'-h','-o','%i|%j|%T|%M|%C'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
roots={'runtime':BASE+'/tlm236_joint_20261105/retry_time_audit_ed028cc70e06',
       'dependencies':BASE+'/attention_resources198_20261107/ee741a72b48e/dependencies',
       'snapshot':BASE+'/tlm245_current_3a7dd5e0679e'}
files={'runtime_manifest':roots['runtime']+'/EXECUTION_MANIFEST.json',
       'dependencies_manifest':roots['dependencies']+'/MANIFEST.json',
       'snapshot_manifest':roots['snapshot']+'/SNAPSHOT_MANIFEST.json'}
print(json.dumps(dict(python=list(sys.version_info[:3]),queue_rc=q.returncode,queue=q.stdout.strip().splitlines(),
    roots={k:dict(path=v,exists=Path(v).exists()) for k,v in roots.items()},user=os.environ['USER'],
    python39_exists=Path('/public3/soft/python/3.9.6/bin/python3').exists(),
    manifests={k:hashlib.sha256(Path(v).read_bytes()).hexdigest() for k,v in files.items()})))
'''
    x=remote(code);save('REMOTE_PREFLIGHT.json',x);print(json.dumps(x,ensure_ascii=False))

def submit():
    assert not (H/'SUBMISSION.json').exists(),'existing receipt;status only'
    p=json.loads((H/'UPLOAD_PLAN.json').read_bytes())
    assert hashlib.sha256(Path(p['local']).read_bytes()).hexdigest()==p['sha256']
    with client.connect(client.load_password()) as session:
        with session.open_sftp() as sftp:
            try:
                with sftp.open(p['remote'],'rb') as f:old=f.read()
                assert hashlib.sha256(old).hexdigest()==p['sha256']
            except IOError:
                with sftp.open(p['remote'],'wx') as f:f.write(Path(p['local']).read_bytes())
    x=remote('P='+repr(p)+'\n'+(H/'remote_submit.py').read_text(),120)
    save('SUBMISSION.json',x);print(json.dumps(x,ensure_ascii=False))

def status():
    p=json.loads((H/'UPLOAD_PLAN.json').read_bytes())
    x=remote('ROOT='+repr(p['root'])+'\n'+(H/'remote_status.py').read_text())
    save('STATUS.json',x)
    print(json.dumps(dict(observed_UTC=x['observed_UTC'],queue=x['queue'],accounting=x['accounting'],
        cases={k:dict(exit_code=v.get('EXIT.json',{}).get('exit_code'),
            job_id=v.get('INVOCATION.json',{}).get('job_id'),seal_present='seal' in v,
            last_progress=v.get('tail',[])[-1:]) for k,v in x['cases'].items()}),ensure_ascii=False))

if __name__=='__main__':
    {'preflight':preflight,'submit':submit,'status':status}[sys.argv[1]]()
