"""Transfer immutable CPU simulation snapshot; build and run through Slurm."""
import hashlib,json,pathlib,subprocess,sys
R=pathlib.Path(__file__).resolve().parents[3];W=R/'work/jieruiz/186'
pipeline='--pipeline' in sys.argv
matrix='HBM_PIPELINE_MATRIX.json' if pipeline else 'HBM_MATRIX.json'
n=len(json.loads((W/matrix).read_text())['cases'])
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R).decode().strip()
package=W/('hbm_'+commit[:8]+'.tar.gz')
remote='/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/hbm_'+commit[:8]
ssh=['ssh','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
def shell(s):return subprocess.check_output(ssh+['bash -l -s'],input=s.encode()).decode().strip()
shell('mkdir -p '+remote+'/source '+remote+'/logs\n')
subprocess.run(['scp','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config',str(package),'lab-server-ai:'+remote+'/input.tar.gz'],check=True)
old='/home/Hongjie_Zeng/projects/pbit-pv-stream-v6-20261016/build'
build=r'''import hashlib,json,pathlib,shlex,subprocess
root=pathlib.Path(REMOTE);old=pathlib.Path(OLD);out=root/'build';out.mkdir(exist_ok=False)
source=root/'source/architecture_tlm/unified_v6/probes/dramsys_bridge/bridge_sg_v6_audit.cpp'
flags={}
for l in (old/'CMakeFiles/pbit_dram_bridge_sg_v6_audit.dir/flags.make').read_text().splitlines():
 if ' = ' in l:
  k,v=l.split(' = ',1);flags[k]=shlex.split(v)
obj=out/'bridge.o';exe=out/'pbit_hbm_bridge'
cc=['/usr/bin/c++']+flags['CXX_DEFINES']+flags['CXX_INCLUDES']+flags['CXX_FLAGS']+['-c',str(source),'-o',str(obj)]
subprocess.run(cc,check=True)
link=shlex.split((old/'CMakeFiles/pbit_dram_bridge_sg_v6_audit.dir/link.txt').read_text())
link=[str(obj) if x.endswith('bridge_sg_v6_audit.cpp.o') else x for x in link]
link[link.index('-o')+1]=str(exe)
subprocess.run(link,cwd=old,check=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
libs=[old/'upstream/src/libdramsys.so',old/'_deps/systemclanguage-build/src/libsystemc.so.3.0.2',old/'_deps/drampower-build/src/DRAMPower/libDRAMPower.so']
(out/'MANIFEST.json').write_text(json.dumps(dict(status='completed',compile=cc,link=link,cwd=str(old),source_sha256=sha(source),executable_sha256=sha(exe),dependencies={str(p):sha(p) for p in libs}),indent=2)+'\n')
subprocess.run(['/usr/bin/python3','-B','work/jieruiz/186/probe_hbm.py','--bridge',str(exe),'--old-bridge',str(old/'pbit_dram_bridge_sg_v6_audit'),'--output',str(root/'probe')],cwd=root/'source',check=True)
'''.replace('REMOTE',repr(remote)).replace('OLD',repr(old))
script='''#!/bin/bash
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:20:00
set -euo pipefail
/usr/bin/python3 REMOTE/build.py
'''.replace('REMOTE',remote)
array='''#!/bin/bash
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=01:30:00
#SBATCH --array=0-LAST%17
set -euo pipefail
cd REMOTE/source
exec /usr/bin/python3 -B -u work/jieruiz/186/run_schedule_case.py "$SLURM_ARRAY_TASK_ID" --matrix work/jieruiz/186/MATRIX --manifest work/jieruiz/186/SOURCE.json --bridge REMOTE/build/pbit_hbm_bridge --output REMOTE/results/case_"$SLURM_ARRAY_TASK_ID"
'''.replace('REMOTE',remote).replace('LAST',str(n-1)).replace('MATRIX',matrix)
payload=json.dumps(dict(build=build,script=script,array=array,remote=remote,sha=hashlib.sha256(package.read_bytes()).hexdigest()))
prepare=r'''import pathlib,json,hashlib,tarfile
p=json.loads(PAYLOAD);r=pathlib.Path(p['remote'])
assert hashlib.sha256((r/'input.tar.gz').read_bytes()).hexdigest()==p['sha']
with tarfile.open(r/'input.tar.gz') as tar:tar.extractall(r/'source',filter='data')
for name,key in [('build.py','build'),('build.sbatch','script'),('run.sbatch','array')]:
 with (r/name).open('x') as f:f.write(p[key])
'''.replace('PAYLOAD',repr(payload))
subprocess.run(ssh+['/usr/bin/python3 -'],input=prepare.encode(),check=True)
jobs=shell('b=$(sbatch --parsable --output='+remote+'/logs/build_%j.out '+remote+'/build.sbatch)\nprintf "%s\\n" "$b"\nsbatch --parsable --dependency=afterok:$b --output='+remote+'/logs/run_%A_%a.out '+remote+'/run.sbatch\n').splitlines()
record=dict(matrix=matrix,cases=n,commit=commit,remote=remote,package_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),jobs=jobs,scope='CPU-only actual DRAMSys full synthetic TLM; no GPU or PPL',build_script_sha256=hashlib.sha256(build.encode()).hexdigest(),array_script_sha256=hashlib.sha256(array.encode()).hexdigest())
(W/('HBM_PIPELINE_SUBMISSION.json' if pipeline else 'HBM_SUBMISSION.json')).write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
