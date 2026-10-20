"""Issue50 Ising observation-count sweep with a fixed B4/T32 FFN; no training."""
import argparse
from datetime import datetime,timezone
import json,math,os,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO))
from experiments.qwen_joint_stratified_attention_20261019 import run_joint as joint
from experiments.qwen_joint_stratified_attention_20261019.run_full import prior_gate


def cases(phase='suffix'):
    rows=[]
    if phase not in ('suffix','full'):
        raise ValueError('unknown sample-count phase')
    counts=(32,64,256,1024) if phase=='suffix' else (256,512)
    for samples in counts:
        for seed in (0,1,2):
            rows.append(dict(name=f'b4_t32_screen_ising_S{samples}_s{seed}',ffn='b4_t32',
                mode='screen_ising',samples=samples,seed=seed,burn=16.,spacing=4.,
                selection='fixed',budget_blocks=8,target_fraction=.30,context=2048,
                decode=128,examples=32,batch=8 if phase=='suffix' else 32,
                protocol=phase,stride=1024))
    if phase=='suffix':
        for seed in (0,1,2):
            rows.append(dict(rows[0],name=f'b4_t32_screen_exact_S128_s{seed}',
                mode='screen_exact',samples=128,seed=seed))
    assert len(rows)==(15 if phase=='suffix' else 6)
    assert len(rows)==len({r['name'] for r in rows})
    return rows


def _read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def prepare(a):
    out=joint.output_dir(a)
    if any(out.iterdir()):raise FileExistsError('Immutable preparation; refuse overwrite')
    identity=joint.verify(a.model,a.data,out/'identity.json')
    prior=prior_gate(a,identity)
    identity.update(execution_commit=a.code_commit,joint_sources=joint.sources(),
        calibration_sha256=joint.CAL_SHA,prior_preparation=prior,
        randomness='unchanged B4T32/K32 shared64 FFN plus independent selector/finiteCTMC domains')
    joint.write_json(out/'identity.json',identity)
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='')
    check=subprocess.run([sys.executable,'-B',str(ROOT/'test_sample_plan.py')],
        cwd=REPO,env=env,text=True,capture_output=True)
    (out/'plan_tests.stdout.txt').write_text(check.stdout,encoding='utf-8',newline='\n')
    (out/'plan_tests.stderr.txt').write_text(check.stderr,encoding='utf-8',newline='\n')
    check.check_returncode()
    # Rerun an unchanged reference on exactly the scored targets before a new
    # comparison; prior vectorized BF16 remains an environment anchor only.
    reference=dict(cases('suffix')[0],name='none_sdpa_S128_s0',ffn='none',mode='sdpa',samples=128,seed=0)
    result=joint.evaluate(a,reference,identity)
    if result['scored_tokens']!=4096 or not math.isclose(result['perplexity'],10.37155678462956,rel_tol=0.,abs_tol=1e-8):
        raise ValueError('Unchanged suffix BF16 mismatch')
    joint.write_json(out/'reference'/('none_sdpa_S128_s0.json'),result)
    suite=dict(code_commit=a.code_commit,created_utc=datetime.now(timezone.utc).isoformat(),
        suffix=cases('suffix'),full=cases('full'),
        reused_suffix='B4T32 S128/S512 and B4T32 SDPA from d61, unchanged config/batch8',
        reused_full='B4T32 S128, B4T32 SDPA and fullBF16 from ongoing53dd/Slurm2430; do not resubmit',
        prior_preparation=prior,only_quality_metric='PPL; no downstream tasks, training, PPA or TLM changes',
        full_submission='Only after suffix completion/review; validate original53dd full readiness and unchanged numerical source files',
        observation_count='S retained CTMC observations/head/query, not hardware updates or independent-sample count',
        fixed_parameters='burn16 spacing4, max4/train-calibration/fixed8blocks; B4T32 FFN always unchanged',
        scope='all24 scored decode Attention; selectedFFN bothprefill/decode; Attentionprefix exactSDPA')
    joint.write_json(out/'suite.json',suite)
    joint.write_json(out/'READY.json',dict(code_commit=a.code_commit,
        unchanged_suffix_bf16_passed=True,baseline_gate_passed=True,sdpa_wrapper_bitwise_passed=True,
        identity_sha256=joint.digest(out/'identity.json'),suite_sha256=joint.digest(out/'suite.json'),
        prior_ready_sha256=prior['artifact_sha256']['READY.json']))


def check_full_gate(a,identity):
    project=Path(a.project_root).resolve(strict=True);gate=Path(a.full_gate_output).resolve(strict=True)
    if gate.parent!=project/'outputs' or gate.name!='53dd0ff6a04218dc9f2b692464d5b16da284cf17':
        raise ValueError('Expected own existing53dd full preparation')
    r=_read(gate/'READY.json');old=_read(gate/'identity.json')
    if not r.get('memory_pilots_passed') or r.get('approved_full_batch')!=32:
        raise ValueError('Actual32x1023 memory gate not passed')
    if r['identity_sha256']!=joint.digest(gate/'identity.json') or r['suite_sha256']!=joint.digest(gate/'suite.json'):
        raise ValueError('Existing full gate changed')
    # New runner/analysis/docs may differ. The actual numerical kernels and
    # upstream scorer/controller must remain byte-identical to the tested full.
    keys=['experiments/qwen_joint_stratified_attention_20261019/joint_evaluate.py']
    keys += [k for k in old['joint_sources'] if '/upstream_attention/' in k or
             any('/'+d+'/' in k for d in ('qwen_multiscale_stratified_20261019',
                 'qwen_fixedw_multiscale_20261019','qwen_dual_range_20261018'))]
    if any(old['joint_sources'][k]!=identity['joint_sources'][k] for k in keys):
        raise ValueError('Numerical full kernels changed; fresh memory gate required')
    return dict(output=str(gate),ready_sha256=joint.digest(gate/'READY.json'),numerical_source_files=len(keys))


def worker(a):
    out=joint.output_dir(a);ready=_read(out/'READY.json')
    if ready['code_commit']!=a.code_commit or not ready['unchanged_suffix_bf16_passed']:
        raise ValueError('Sample sweep not prepared')
    if ready['identity_sha256']!=joint.digest(out/'identity.json') or ready['suite_sha256']!=joint.digest(out/'suite.json'):
        raise ValueError('Preparation artifacts changed')
    identity,suite=_read(out/'identity.json'),_read(out/'suite.json')
    if identity['joint_sources']!=joint.sources() or identity['source_sha256']!=joint.source_manifest():
        raise ValueError('Execution source changed')
    if prior_gate(a,identity)!=identity['prior_preparation']:
        raise ValueError('Inherited gates changed')
    grid=cases(a.phase)
    if suite[a.phase]!=grid or not 0<=a.index<len(grid):raise ValueError('Suite/index mismatch')
    full_gate=check_full_gate(a,identity) if a.phase=='full' else None
    cfg=grid[a.index];target=out/a.phase/(cfg['name']+'.json')
    if target.exists():raise FileExistsError(target)
    result=joint.evaluate(a,cfg,identity)
    expected=299077 if a.phase=='full' else 4096
    if result['scored_tokens']!=expected:raise RuntimeError('Target coverage mismatch')
    if a.phase=='full' and not result['scoring_plan']['every_full_corpus_target_once']:
        raise RuntimeError('Incomplete full corpus')
    result.update(reused_full_memory_gate=full_gate,quality_only=True)
    joint.write_json(target,result)
    print(json.dumps(dict(event='sample_count_completed',name=cfg['name'],ppl=result['perplexity'],targets=expected)),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','worker'])
    for key in ('model','data','calibration','project-root','output','code-commit','prior-output'):p.add_argument('--'+key,required=True)
    p.add_argument('--full-gate-output');p.add_argument('--phase',choices=['suffix','full'],default='suffix');p.add_argument('--index',type=int,default=0)
    a=p.parse_args()
    if len(a.code_commit)!=40 or any(c not in '0123456789abcdef' for c in a.code_commit):p.error('Exact SHA required')
    if a.phase=='full' and not a.full_gate_output:p.error('Existing full preparation path required')
    {'prepare':prepare,'worker':worker}[a.action](a)
if __name__=='__main__':main()
