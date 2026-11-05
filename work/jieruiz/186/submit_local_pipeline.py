"""Freeze new-folder local-bank experiment and submit immutable CPU Slurm."""
import hashlib,json,pathlib,subprocess,sys,tarfile
R=pathlib.Path(__file__).resolve().parents[3];W=R/'work/jieruiz/186';sys.path.insert(0,str(R))
from architecture_tlm.unified_v6.run import source_record

def main():
 record=source_record();commit=record['commit']
 folder=R/'architecture_tlm/ffn_local_pipeline_20261025'
 for p in sorted(folder.iterdir()):
  if p.suffix not in ('.py','.json'):continue
  rel=p.relative_to(R).as_posix();b=p.read_bytes()
  assert subprocess.check_output(['git','show',commit+':'+rel],cwd=R)==b
  record['files'][rel]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
 mf=W/('PIPELINE_SOURCE_'+commit[:8]+'.json');mf.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
 package=W/('pipeline_'+commit[:8]+'.tar.gz')
 with tarfile.open(package,'x:gz') as tar:
  for rel in record['files']:tar.add(R/rel,arcname=rel,recursive=False)
  tar.add(mf,arcname='work/jieruiz/186/SOURCE.json')
 remote='/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/pipeline_'+commit[:8]
 bridge='/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/hbm_43b7b1ff/build/pbit_hbm_bridge'
 ssh=['ssh','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
 def shell(s):return subprocess.check_output(ssh+['bash -l -s'],input=s.encode()).decode().strip()
 print(shell('squeue -u Hongjie_Zeng -h -o "%i %j %T %C"\n'),flush=True)
 shell('test ! -e '+remote+' && mkdir -p '+remote+'/source '+remote+'/logs\n')
 subprocess.run(['scp','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config',str(package),'lab-server-ai:'+remote+'/input.tar.gz'],check=True)
 header='#!/bin/bash\n#SBATCH --partition=gpu5090\n#SBATCH --cpus-per-task=1\n#SBATCH --mem=3G\n#SBATCH --time=01:30:00\n#SBATCH --array=0-12%13\n'
 array=header+'set -euo pipefail\ncd '+remote+'/source\n/usr/bin/python3 -B -u -m architecture_tlm.ffn_local_pipeline_20261025.run_case "$SLURM_ARRAY_TASK_ID" --matrix architecture_tlm/ffn_local_pipeline_20261025/MATRIX.json --manifest work/jieruiz/186/SOURCE.json --bridge '+bridge+' --output '+remote+'/results/case_"$SLURM_ARRAY_TASK_ID"\n'
 payload=dict(remote=remote,sha=hashlib.sha256(package.read_bytes()).hexdigest(),array=array)
 prep="import pathlib,json,hashlib,tarfile\np=json.loads("+repr(json.dumps(payload))+" )\nr=pathlib.Path(p['remote'])\nassert hashlib.sha256((r/'input.tar.gz').read_bytes()).hexdigest()==p['sha']\nwith tarfile.open(r/'input.tar.gz') as t:t.extractall(r/'source',filter='data')\nwith (r/'run.sbatch').open('x') as f:f.write(p['array'])\n"
 subprocess.run(ssh+['/usr/bin/python3 -'],input=prep.encode(),check=True)
 job=shell('sbatch --parsable --output='+remote+'/logs/run_%A_%a.out '+remote+'/run.sbatch\n')
 result=dict(commit=commit,remote=remote,bridge=bridge,cases=13,job=job,package_sha256=payload['sha'],array_sha256=hashlib.sha256(array.encode()).hexdigest(),scope='CPU synthetic timing only; 3 full36-layer rows and 10 one-layer diagnostic rows; no new PPL or physical PPA')
 (W/'PIPELINE_SUBMISSION.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
