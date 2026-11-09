"""Submit a small public-source CACTI job in the existing personal EDA project."""
from pathlib import Path
import hashlib,io,json,sys,zipfile

TASK=Path(__file__).resolve().parents[2]
WS=TASK.parents[1]
OUT=TASK/'work/rayggxia/225/process28_rough_20261109'
OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(WS/'tmp/cross-model245-20261106/work/rayggxia/245/mainline_20261108'))
import ops
sys.path.insert(0,str(WS))
from architecture_tlm.cacti_memory import config,parse

def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,x):(OUT/n).write_bytes((json.dumps(x,indent=2)+'\n').encode())
if sys.argv[1]=='submit':
    assert not (OUT/'CACTI_SUBMISSION.json').exists(),'Preserve existing job'
    src=WS/'architecture_tlm/tools/cacti-master'
    template=(src/'cache.cfg').read_text()
    files={p.relative_to(src).as_posix():p.read_bytes() for p in src.rglob('*')
        if p.is_file() and (p.suffix in ('.cc','.h','.dat') or p.name in ('makefile','cacti.mk'))}
    for nm in (28,55):
        cfg=config(template,dict(bytes=4096,width=128)).replace('-technology (u) 0.055','-technology (u) 0.%03d'%nm).replace('-operating temperature (K) 400','-operating temperature (K) 300')
        # Technology in um: 28nm=.028,55nm=.055.
        files['probe%s.cfg'%nm]=cfg.encode()
    files['RUN.sh']=b'''#!/bin/bash
set -eu
export PATH=/public3/soft/gcc/11.2.0/bin:/public3/soft/python/3.9.6/bin:$PATH
export LD_LIBRARY_PATH=/public3/soft/gcc/11.2.0/lib64:/public3/soft/python/3.9.6/lib:${LD_LIBRARY_PATH:-}
make opt -j4 NTHREADS=1 CXXFLAGS="-O2 -DNTHREADS=1" > build.log 2>&1
./cacti -infile probe28.cfg > result28.txt 2>&1
./cacti -infile probe55.cfg > result55.txt 2>&1
sha256sum cacti probe28.cfg probe55.cfg result28.txt result55.txt > SHA256SUMS
'''
    files['SOURCE_MANIFEST.json']=(json.dumps({n:sha(b) for n,b in files.items()},indent=2)+'\n').encode()
    z=io.BytesIO()
    with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as f:
        for n,b in files.items():f.writestr(n,b)
    payload=z.getvalue();digest=sha(payload);remote=ops.BASE+'/tlm28_cacti225_20261109/'+digest[:12]
    (OUT/'CACTI_INPUT_MANIFEST.json').write_bytes(files['SOURCE_MANIFEST.json'])
    with ops.client.connect(ops.client.load_password()) as s:
        code='from pathlib import Path\nimport hashlib\np=Path(%r);p.mkdir(parents=True,exist_ok=True)\nassert not (p/"SUBMISSION.json").exists()\nassert not (p/"source.zip").exists() or hashlib.sha256((p/"source.zip").read_bytes()).hexdigest()==%r\n'%(remote,digest)
        i,o,e=s.exec_command('python3 -B -');i.write(code);i.flush();i.channel.shutdown_write();assert o.channel.recv_exit_status()==0,e.read().decode()
        with s.open_sftp() as f:f.putfo(io.BytesIO(payload),remote+'/source.zip')
    code='''from pathlib import Path
import hashlib,json,subprocess,zipfile
p=Path(%r);b=(p/'source.zip').read_bytes();assert hashlib.sha256(b).hexdigest()==%r
with zipfile.ZipFile(p/'source.zip') as z:
 for n in z.namelist():assert not n.startswith('/') and '..' not in Path(n).parts
 z.extractall(p)
manifest=json.loads((p/'SOURCE_MANIFEST.json').read_bytes())
for n,h in manifest.items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
r=subprocess.run(['sbatch','--parsable','-p','v6_384','-c','4','--mem=4G','--time=00:10:00','--job-name=tlm28-cacti225','--chdir='+str(p),'--output='+str(p/'slurm-%%j.out'),str(p/'RUN.sh')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,check=True)
x=dict(job_id=r.stdout.strip(),remote=str(p),zip_sha256=%r)
(p/'SUBMISSION.json').write_text(json.dumps(x))
print(json.dumps(x))
'''%(remote,digest,digest)
    x=ops.remote(code);save('CACTI_SUBMISSION.json',x);print(json.dumps(x))
elif sys.argv[1]=='collect':
    info=json.loads((OUT/'CACTI_SUBMISSION.json').read_bytes());remote=info['remote']
    code='''from pathlib import Path
import json,subprocess
p=Path(%r)
names=['result28.txt','result55.txt','SHA256SUMS','build.log']
out={n:(p/n).read_text(errors='replace') for n in names if (p/n).exists()}
out['job']=subprocess.run(['sacct','-j',%r,'--noheader','--parsable2','-o','JobID,State,ExitCode,Elapsed'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True).stdout
print(json.dumps(out))
'''%(remote,info['job_id'])
    x=ops.remote(code)
    for n,b in x.items():(OUT/n).write_bytes(b.encode())
    if 'SHA256SUMS' in x:
        for line in x['SHA256SUMS'].splitlines():
            h,n=line.split()
            if n in ('result28.txt','result55.txt'):assert sha((OUT/n).read_bytes())==h
        r={str(n):parse(x['result%s.txt'%n]) for n in (28,55)}
        save('CACTI_PARSED.json',dict(status='ANALYTICAL_CAСTI_NOT_28_FOUNDRY_CALIBRATION',job=info,bank=dict(bytes=4096,width=128,count=240,temperature_K=300,ports='1RW'),results=r))
        print(json.dumps(r))
    else:print(x.get('job','')+x.get('build.log','')[-1200:])
