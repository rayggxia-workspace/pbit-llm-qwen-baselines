"""Stage a separate benchmark snapshot; no job submission."""
from prepare_cpu_gate import ROOT,TREE,project,guard,m
from pathlib import Path
import hashlib,json,subprocess,sys,tarfile

assert not (ROOT/'MEASUREMENT_PLAN.json').exists(),'inspect existing plan; never replay staging blindly'
assert not subprocess.check_output(['git','-C',str(TREE),'status','--porcelain'],text=True).strip()
head=subprocess.check_output(['git','-C',str(TREE),'rev-parse','HEAD'],text=True).strip()
bundle=ROOT/('measurement_source_'+head[:12])
subprocess.run([sys.executable,'-X','utf8','-B','-m','qwen3.sparq.bench_only','freeze','--out',str(bundle)],cwd=TREE,check=True)
execution=json.loads((bundle/'EXECUTION.json').read_text(encoding='utf-8'))
assert execution['commit']==head
archive=ROOT/('measurement_'+head[:12]+'.tar.gz')
with tarfile.open(archive,'w:gz') as tar:
    for path in sorted(bundle.rglob('*')):
        if path.is_file():tar.add(path,arcname=path.relative_to(bundle).as_posix(),recursive=False)
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
target=project+'/measurement-source-'+head[:12]
parent=project+'/results/8d60abe4e7c5'
parent_identity=hashlib.sha256((ROOT/'formal_results/8d60abe4e7c5/IDENTITY.json').read_bytes()).hexdigest()
parent_value=json.loads((ROOT/'formal_results/8d60abe4e7c5/IDENTITY.json').read_text(encoding='utf-8'))
assert parent_value['execution']['commit']=='8d60abe4e7c5c245c8f5f87b7f66e49e23ae0eea'
parent_fingerprint=hashlib.sha256(json.dumps(parent_value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
script='''#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:30:00
'''+guard+f'''
test "$(realpath -e {target})" = {target}
test "$(stat -c %U {target})" = Weican_Chen
test -x /opt/slurm/21.08.8/bin/srun
export OMP_NUM_THREADS=4 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
export TMPDIR={project}/tmp
export HF_HOME={project}/cache/hf HF_DATASETS_CACHE={project}/cache/datasets
export HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1
cd {target}
/opt/slurm/21.08.8/bin/srun env CUDA_VISIBLE_DEVICES="" {project}/env-v2/bin/python -B -m unittest qwen3.sparq.test_bench_only
/opt/slurm/21.08.8/bin/srun env CUDA_VISIBLE_DEVICES="" {project}/env-v2/bin/python -B -m qwen3.sparq.benchmark --self-test
/opt/slurm/21.08.8/bin/srun {project}/env-v2/bin/python -B -m qwen3.sparq.bench_only run --root {project} --parent-results {parent} --parent-identity-sha256 {parent_identity}
'''
script_path=ROOT/'measurement.sbatch'
script_path.write_text(script,encoding='utf-8',newline='\n')
plan=dict(commit=head,source=target,bundle=str(bundle),archive_sha256=digest,
          parent_results=parent,parent_identity_sha256=parent_identity,
          parent_fingerprint=parent_fingerprint,
          script=target+'/measurement.sbatch',script_sha256=hashlib.sha256(script_path.read_bytes()).hexdigest(),
          execution=execution,project=project,dependency_job_must_be_terminal='2878',gpu_job_submitted=False)
m.save('MEASUREMENT_STAGING_INTENT.json',plan)
m.ssh(guard+'test ! -e '+target+'\nmkdir '+target)
m.transfer(archive,target+'/source.tar.gz')
assert m.ssh(guard+'sha256sum '+target+'/source.tar.gz').split()[0]==digest
m.ssh(guard+'tar -xzf '+target+'/source.tar.gz -C '+target)
m.transfer(script_path,target+'/measurement.sbatch')
assert m.ssh(guard+'sha256sum '+target+'/measurement.sbatch').split()[0]==plan['script_sha256']
m.ssh(guard+'bash -n '+target+'/measurement.sbatch')
m.save('MEASUREMENT_PLAN.json',plan)
print(json.dumps(dict(status='staged_not_submitted',commit=head,source=target)))
