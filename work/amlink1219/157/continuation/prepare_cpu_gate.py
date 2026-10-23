from pathlib import Path
import importlib.util,json,hashlib,subprocess,tarfile,re,io
ROOT=Path(__file__).resolve().parent
TREE=ROOT.parents[1]/'workspace_projects/sq157'
spec=importlib.util.spec_from_file_location('sparq_remote_cpu',ROOT.parent/'pdnn_accuracy_20261023/remote_control.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.OUT=ROOT
project='/home/Weican_Chen/projects/sparq-qwen3-issue157'
guard='''set -euo pipefail
test "$(id -un)" = Weican_Chen
test "$(getent passwd Weican_Chen | cut -d: -f6)" = /home/Weican_Chen
test "$(realpath -e /home/Weican_Chen)" = /home/Weican_Chen
test "$(stat -c %U /home/Weican_Chen)" = Weican_Chen
test "$(realpath -e /home/Weican_Chen/projects/sparq-qwen3-issue157)" = /home/Weican_Chen/projects/sparq-qwen3-issue157
test "$(stat -c %U /home/Weican_Chen/projects/sparq-qwen3-issue157)" = Weican_Chen
'''
if __name__=='__main__':
    assert not (ROOT/'CPU_GATE_JOB.json').exists()
    head=subprocess.check_output(['git','-C',str(TREE),'rev-parse','HEAD'],text=True).strip()
    tracked=subprocess.check_output(['git','-C',str(TREE),'ls-files','qwen3','architecture_tlm/sparq_baseline'],text=True).splitlines()
    paths=[p for p in tracked if p.endswith('.py') or p=='qwen3/sparq/SOURCES.json']
    files={p:hashlib.sha256((TREE/p).read_bytes()).hexdigest() for p in paths}
    manifest={'commit':head,'files':files,'purpose':'CPU gates only; quality execution frozen separately'}
    m.save('CPU_GATE_EXECUTION.json',manifest)
    archive=ROOT/'cpu_gate_source.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for p in paths:tar.add(TREE/p,arcname=p,recursive=False)
        payload=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('EXECUTION.json');info.size=len(payload);tar.addfile(info,io.BytesIO(payload))
    checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
    target=project+'/cpu-gates-v1'
    script='''#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=00:30:00
'''+guard+f'''
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=4 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
export TMPDIR={project}/tmp
cd {target}
/opt/slurm/21.08.8/bin/srun {project}/env-v2/bin/python -B -m qwen3.sparq.cpu_gate --output {target}/CPU_GATE.json
'''
    (ROOT/'cpu_gate.sbatch').write_text(script,encoding='utf-8',newline='\n')
    print(m.ssh(guard+'find '+project+'/model -maxdepth 5 -type f -printf "%P %s bytes\\n" | head -n 25\n/opt/slurm/21.08.8/bin/scontrol show partition gpu5090'))
    m.ssh(guard+'test ! -e '+target+'\nmkdir '+target)
    m.transfer(archive,target+'/source.tar.gz');m.transfer(ROOT/'cpu_gate.sbatch',target+'/cpu_gate.sbatch')
    assert m.ssh(guard+'sha256sum '+target+'/source.tar.gz').split()[0]==checksum
    m.ssh(guard+'tar -xzf '+target+'/source.tar.gz -C '+target+'\nbash -n '+target+'/cpu_gate.sbatch')
    m.save('CPU_GATE_INTENT.json',dict(root=target,commit=head,archive_sha256=checksum))
    result=m.ssh(guard+f'/opt/slurm/21.08.8/bin/sbatch --parsable --output={project}/logs/cpu-gate-%j.out --error={project}/logs/cpu-gate-%j.err {target}/cpu_gate.sbatch')
    job=result.strip().split(';')[0];assert re.fullmatch(r'\d+',job)
    m.save('CPU_GATE_JOB.json',dict(job=job,project=project,source=target,commit=head,gpu=False))
    print(json.dumps(dict(job=job,commit=head,files=len(paths))))
