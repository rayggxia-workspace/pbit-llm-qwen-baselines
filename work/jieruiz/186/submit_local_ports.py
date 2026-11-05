import hashlib,json,pathlib,subprocess,sys,tarfile
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/ffn-local-pipeline-issue186-20261025');W=R/'work/jieruiz/186';sys.path.insert(0,str(R))
from architecture_tlm.unified_v6.run import source_record
sys.stdout.reconfigure(encoding='utf-8')
suffix='_BURST' if '--burst' in sys.argv else ('_EXPOSED' if '--exposed' in sys.argv else '')
indices=[10,11,12,13] if suffix=='_BURST' else ([8,9] if suffix else list(range(6)))
record=source_record();head=record['commit']
for name in ('local_ports_20261027','sliced_sram_20261027','scheduling_v2_20261027','clock500_resource_20261026','ffn_local_pipeline_20261025'):
 for p in (R/'architecture_tlm'/name).glob('*.py'):
  rel=p.relative_to(R).as_posix();b=p.read_bytes()
  assert subprocess.check_output(['git','show',head+':'+rel],cwd=R)==b
  record['files'][rel]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
mf=W/('LOCAL_PORTS'+suffix+'_SOURCE_'+head[:8]+'.json');mf.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
package=W/('local_ports_'+head[:8]+'.tar.gz')
with tarfile.open(package,'x:gz') as tar:
 for rel in record['files']:tar.add(R/rel,arcname=rel,recursive=False)
 tar.add(mf,arcname='work/jieruiz/186/SOURCE.json')
remote='/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/local_ports_'+head[:8]
bridge='/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/hbm_43b7b1ff/build/pbit_hbm_bridge'
ssh=['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
def shell(s):return subprocess.check_output(ssh+['bash -l -s'],input=s.encode(),timeout=45).decode().strip()
print(shell('squeue -u Hongjie_Zeng -h -o "%i %j %T %C"\n'),flush=True)
shell('test ! -e '+remote+' && mkdir -p '+remote+'/source '+remote+'/logs\n')
subprocess.run(['C:/Windows/System32/OpenSSH/scp.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config',str(package),'lab-server-ai:'+remote+'/input.tar.gz'],check=True,timeout=90)
array='#!/bin/bash\n#SBATCH --partition=gpu5090\n#SBATCH --cpus-per-task=1\n#SBATCH --mem=4G\n#SBATCH --time=01:00:00\n#SBATCH --array='+','.join(map(str,indices))+'%'+str(len(indices))+'\n'
array+='set -euo pipefail\ncd '+remote+'/source\n/usr/bin/python3 -B -m unittest architecture_tlm.local_ports_20261027.test_ports >/dev/null\n/usr/bin/python3 -B -u -m architecture_tlm.local_ports_20261027.run_case "$SLURM_ARRAY_TASK_ID" --manifest work/jieruiz/186/SOURCE.json --bridge '+bridge+' --output '+remote+'/results/case_"$SLURM_ARRAY_TASK_ID"\n'
payload=dict(remote=remote,sha=hashlib.sha256(package.read_bytes()).hexdigest(),array=array)
prep="import pathlib,json,hashlib,tarfile\np=json.loads("+repr(json.dumps(payload))+")\nr=pathlib.Path(p['remote'])\nassert hashlib.sha256((r/'input.tar.gz').read_bytes()).hexdigest()==p['sha']\nwith tarfile.open(r/'input.tar.gz') as t:t.extractall(r/'source',filter='data')\nwith (r/'run.sbatch').open('x') as f:f.write(p['array'])\n"
subprocess.run(ssh+['/usr/bin/python3 -'],input=prep.encode(),check=True,timeout=45)
job=shell('sbatch --parsable --output='+remote+'/logs/run_%A_%a.out '+remote+'/run.sbatch\n')
result=dict(commit=head,remote=remote,bridge=bridge,cases=len(indices),indices=indices,job=job,package_sha256=payload['sha'],array_sha256=hashlib.sha256(array.encode()).hexdigest(),scope='CPU one Qwen3-4B layer+full vocabulary; SC/BF16 local-port controls; actual DRAMSys; no new PPL/PPA')
(W/('LOCAL_PORTS'+suffix+'_SUBMISSION.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(result),flush=True)
