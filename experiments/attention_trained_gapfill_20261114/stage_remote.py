"""Run through the configured GPU host's login shell; only stage this new run."""
from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess

assert Path.home() == Path('/home/Hongjie_Zeng')
root = Path.home() / 'projects/attention-fig5-kwh128-gapfill-20261114'
root.mkdir(exist_ok=True)
assert root.resolve().parent == Path.home() / 'projects'
assert root.stat().st_uid == os.getuid()
old = Path.home() / 'projects/attention-trained-budget-20261107/source-e17befe4cb3f'
parent = json.loads((old / 'execution.json').read_bytes())
files = {n: (old / n).read_bytes() for n in parent['files_sha256']}
assert all(hashlib.sha256(b).hexdigest() == parent['files_sha256'][n]
           for n, b in files.items())
old_exp = 'experiments/attention_trained_budget_20261107'
new_exp = 'experiments/attention_trained_gapfill_20261114'
budgets = ((64, 64), (64, 128), (128, 16), (256, 16), (256, 128))
cases = [dict(name='bf16', k=None, samples=None, seed=0, overlay=None)]
cases += [dict(name=f'k_wh128_wh_k{k}_s{s}', k=k, samples=s,
               seed=0, overlay='k_wh128') for k, s in budgets]

methods = files[old_exp + '/methods.py'].decode()
tree = ast.parse(methods)
assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'CASES' for t in n.targets))
lines = methods.splitlines(keepends=True)
methods = ''.join(lines[:assignment.lineno-1]) + 'CASES = ' + repr(cases) + '\n' + ''.join(lines[assignment.end_lineno:])
files[new_exp + '/methods.py'] = methods.encode()

runner = files[old_exp + '/run.py'].decode()
def replace_once(a, b):
    global runner
    assert runner.count(a) == 1, (a, runner.count(a))
    runner = runner.replace(a, b)

replace_once("'experiments.attention_trained_budget_20261107.test_sweep'",
             "'experiments.attention_trained_gapfill_20261114.test_sweep'")
replace_once('for case in [CASES[i] for i in (1,4,7,10,13,16,19,20)]:',
             'for case in CASES[1:]:')
replace_once("worst = next(c for c in CASES if c['k']==256 and c['samples']==64)",
             "worst = next(c for c in CASES if c['k']==256 and c['samples']==128)")
replace_once("        assert read_sealed(dest/'cases/00_bf16_seed0/complete.json')['status'] == 'completed'",
             "        assert read_sealed(dest/'cases/00_bf16_seed0/complete.json')['status'] == 'completed'\n"
             "        reference = read_sealed(dest/'cases/00_bf16_seed0/RESULT.json')\n"
             "        assert abs(reference['perplexity'] - 11.538153433607206) < 1e-5, reference['perplexity']")
replace_once("    seal(out/'complete.json', dict(status='completed', result_sha256=sha256(out/'RESULT.json')))",
             "    if a.phase == 'reference':\n"
             "        assert abs(read_sealed(out/'RESULT.json')['perplexity'] - 11.538153433607206) < 1e-5\n"
             "    seal(out/'complete.json', dict(status='completed', result_sha256=sha256(out/'RESULT.json')))")
files[new_exp + '/run.py'] = runner.encode()

test = files[old_exp + '/test_sweep.py'].decode()
test = test.replace('len(CASES), 21', 'len(CASES), 6')
test = test.replace("len({(c['name'], c['seed']) for c in CASES}), 21",
                    "len({(c['name'], c['seed']) for c in CASES}), 6")
test = test.replace('        for c in CASES[1:]:',
                    '        self.assertEqual({(c["k"], c["samples"]) for c in CASES[1:]},\n'
                    '                         {(64,64),(64,128),(128,16),(256,16),(256,128)})\n'
                    '        self.assertEqual({c["seed"] for c in CASES}, {0})\n'
                    '        self.assertEqual({c["overlay"] for c in CASES[1:]}, {"k_wh128"})\n'
                    '        for c in CASES[1:]:')
files[new_exp + '/test_sweep.py'] = test.encode()
files[new_exp + '/job.sh'] = files[old_exp + '/job.sh'].replace(
    b'experiments.attention_trained_budget_20261107.run',
    b'experiments.attention_trained_gapfill_20261114.run')

plan = dict(cases=cases, user_scope='Five missing K_WH128 points, seed0 only; reuse all existing points',
            expected_targets=299077, expected_windows=292, context=2048, stride=1024,
            FFN='original exact BF16', weight='K_WH128', rng='independent Philox',
            frontend='S12/F4 absolute-score quantization then max-gap; frozen floor-P8',
            burn=0, initial_winner=0, spacing=1, r=32, recent=32,
            parent_manifest_sha256=hashlib.sha256((old/'execution.json').read_bytes()).hexdigest(),
            git_base='b123a8ba43d72ec863b312e35cc7f18c148ad12b',
            local_branch='task/198-fig5-kwh128-gapfill-20261114', issue=198,
            unchanged_reference_PPL=11.538153433607206, reference_absolute_tolerance=1e-5,
            algorithm_changes=False, training=False, existing_sampling_repeats=False)
files[new_exp + '/PLAN.json'] = (json.dumps(plan, indent=2) + '\n').encode()
for n, b in files.items():
    if n.endswith('.py'):
        ast.parse(b.decode())
hashes = {n: hashlib.sha256(b).hexdigest() for n,b in files.items()}
identity = hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
src = root / ('source-' + identity[:12])
src.mkdir(exist_ok=True)

def immutable_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == payload, str(path)
    else:
        with path.open('xb') as f:
            f.write(payload)

for n, b in files.items():
    immutable_write(src/n, b)
execution = dict(commit=identity, execution_identity=identity, not_git_commit=True,
                 parent_execution=parent['execution_identity'],
                 parent_git_commit=parent.get('parent_git_commit'), git_base=plan['git_base'],
                 files_sha256=hashes)
immutable_write(src/'execution.json', (json.dumps(execution,indent=2)+'\n').encode())
for n in ('logs','results','tmp'):
    (root/n).mkdir(exist_ok=True)

job_path = root / ('JOBS-' + identity[:12] + '.json')
jobs = json.loads(job_path.read_bytes()) if job_path.exists() else {}
def submit(phase, dep=None):
    if phase in jobs:
        return jobs[phase]
    args = ['sbatch','--parsable','--partition=gpu5090','--cpus-per-task=2',
            '--mem=' + ('16G' if phase=='cpu' else '48G'),
            '--time=' + ('00:30:00' if phase=='cpu' else '02:00:00' if phase=='full' else '01:00:00'),
            '--job-name=fig5-kwh128-' + phase,
            '--output=' + str(root/'logs'/(identity[:12]+'-'+phase+'-%A_%a.out'))]
    if phase != 'cpu':
        args += ['--gres=gpu:1']
    if phase == 'full':
        args += ['--array=1-5%2']
    if dep:
        args += ['--dependency=afterok:'+dep]
    script=src/new_exp/'job.sh'
    script.chmod(0o700)
    job = subprocess.check_output(args+[str(script),phase,str(root),str(src)],text=True).strip()
    assert job.isdigit(), job
    jobs[phase]=job
    job_path.write_text(json.dumps(jobs,indent=2)+'\n')
    return job

jobs['cpu']=submit('cpu')
jobs['gate']=submit('gate',jobs['cpu'])
jobs['reference']=submit('reference',jobs['gate'])
jobs['full']=submit('full',jobs['reference'])
out = dict(root=str(root), source=str(src), identity=identity,
           parent_execution=parent['execution_identity'], jobs=jobs, plan=plan,
           source_files_sha256=hashes, GPU_maximum=2, CPU_per_task=2,
           queue=subprocess.getoutput('squeue -u Hongjie_Zeng'))
(root/('SUBMISSION-'+identity[:12]+'.json')).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
