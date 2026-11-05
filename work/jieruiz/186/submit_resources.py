"""Freeze and submit hardware x scheduling factorial to CPU Slurm."""
import hashlib,json,pathlib,subprocess,sys,tarfile
R=pathlib.Path(__file__).resolve().parents[3];W=R/'work/jieruiz/186';sys.path.insert(0,str(R))
from architecture_tlm.unified_v6.run import source_record

def main():
 record=source_record();commit=record['commit']
 for rel in ['work/jieruiz/186/run_schedule_case.py','work/jieruiz/186/RESOURCE_MATRIX.json']:
  b=(R/rel).read_bytes();assert subprocess.check_output(['git','show',commit+':'+rel],cwd=R)==b
  record['files'][rel]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
 mf=W/('RESOURCE_SOURCE_'+commit[:8]+'.json');mf.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
 package=W/('resource_'+commit[:8]+'.tar.gz')
 with tarfile.open(package,'x:gz') as tar:
  for rel in record['files']:tar.add(R/rel,arcname=rel,recursive=False)
  tar.add(mf,arcname='work/jieruiz/186/SOURCE.json')
 remote='/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/resource_'+commit[:8]
 bridge='/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/hbm_43b7b1ff/build/pbit_hbm_bridge'
 ssh=['ssh','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
 def shell(s):return subprocess.check_output(ssh+['bash -l -s'],input=s.encode()).decode().strip()
 print(shell('squeue -u Hongjie_Zeng -h -o "%i %j %T %C"\n'),flush=True)
 shell('test ! -e '+remote+' && mkdir -p '+remote+'/source '+remote+'/logs\n')
 subprocess.run(['scp','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config',str(package),'lab-server-ai:'+remote+'/input.tar.gz'],check=True)
 header='#!/bin/bash\n#SBATCH --partition=gpu5090\n#SBATCH --cpus-per-task=1\n#SBATCH --mem=3G\n#SBATCH --time=01:30:00\n'
 gate=header+'set -euo pipefail\ncd '+remote+'/source\n/usr/bin/python3 -B -u architecture_tlm/unified_v6/probes/resource_pipeline_gate.py --bridge '+bridge+' --output '+remote+'/gate\n'
 array=header+'#SBATCH --array=0-15%16\nset -euo pipefail\ncd '+remote+'/source\n/usr/bin/python3 -B -u work/jieruiz/186/run_schedule_case.py "$SLURM_ARRAY_TASK_ID" --matrix work/jieruiz/186/RESOURCE_MATRIX.json --manifest work/jieruiz/186/SOURCE.json --bridge '+bridge+' --output '+remote+'/results/case_"$SLURM_ARRAY_TASK_ID"\n'
 payload=dict(remote=remote,sha=hashlib.sha256(package.read_bytes()).hexdigest(),gate=gate,array=array)
 prep="import pathlib,json,hashlib,tarfile\np=json.loads("+repr(json.dumps(payload))+" )\nr=pathlib.Path(p['remote'])\nassert hashlib.sha256((r/'input.tar.gz').read_bytes()).hexdigest()==p['sha']\nwith tarfile.open(r/'input.tar.gz') as t:t.extractall(r/'source',filter='data')\nfor name,key in [('gate.sbatch','gate'),('run.sbatch','array')]:\n with (r/name).open('x') as f:f.write(p[key])\n"
 subprocess.run(ssh+['/usr/bin/python3 -'],input=prep.encode(),check=True)
 jobs=shell('g=$(sbatch --parsable --output='+remote+'/logs/gate_%j.out '+remote+'/gate.sbatch)\nprintf "%s\\n" "$g"\nsbatch --parsable --dependency=afterok:$g --output='+remote+'/logs/run_%A_%a.out '+remote+'/run.sbatch\n').splitlines()
 result=dict(commit=commit,remote=remote,bridge=bridge,cases=16,jobs=jobs,package_sha256=payload['sha'],gate_sha256=hashlib.sha256(gate.encode()).hexdigest(),array_sha256=hashlib.sha256(array.encode()).hexdigest(),scope='CPU synthetic timing only; digital BF16; no new PPL or physical PPA')
 (W/'RESOURCE_SUBMISSION.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
