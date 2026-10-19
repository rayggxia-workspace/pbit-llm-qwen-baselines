"""Allocated Slurm stages for Issue48; no submission or downloads here."""
from pathlib import Path
import argparse,datetime,hashlib,json,math,os,signal,subprocess,sys,time,traceback

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parents[1]

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def inside(path,root,exists=True):
    target=Path(path).resolve(strict=exists)
    if not target.is_relative_to(root) or target==root:raise ValueError('Path outside approved personal root: '+str(target))
    return target
def matrix(config):
    base={k:config[k] for k in ['context','decode','examples','batch','burn','spacing','budget_blocks','selection','target_fraction']}
    base['protocol']='suffix';cases=[]
    def add(mode,samples,seed,**extra):cases.append({**base,'mode':mode,'samples':samples,'seed':seed,**extra})
    add('sdpa',128,0);add('digital_exact',128,0)
    for seed in config['seeds']:add('screen_exact',128,seed)
    for samples in [512,128,32,64,256,1024]:
        for seed in config['seeds']:add('screen_ising',samples,seed)
    for samples in [32,128,512]:
        for seed in config['seeds']:add('screen_iid',samples,seed)
    add('ising_only',512,0);add('screen_ising',512,0,selection='variable')
    assert len(cases)==34
    for i,c in enumerate(cases):c['case_id']=f'case_{i:03d}'
    return cases
def state_hash(model,torch):
    h=hashlib.sha256()
    for name,value in model.state_dict().items():
        h.update(name.encode());h.update(str(value.dtype).encode());h.update(str(tuple(value.shape)).encode())
        h.update(value.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes())
    return h.hexdigest()
def elapsed_timeout(signum,frame):raise TimeoutError('Registered per-case runtime budget exceeded')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',required=True,choices=['cpu_preflight','gpu_preflight','sweep','full_confirm']);parser.add_argument('--config',required=True);parser.add_argument('--source-manifest',required=True);parser.add_argument('--source-commit',required=True);args=parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('SLURM_JOB_NODELIST'):raise RuntimeError('Explicit Slurm allocation required')
    gpu=args.stage!='cpu_preflight'
    if not gpu:os.environ['CUDA_VISIBLE_DEVICES']=''
    elif not os.environ.get('CUDA_VISIBLE_DEVICES'):raise RuntimeError('Scheduler GPU assignment is missing')
    import pwd
    user=pwd.getpwuid(os.getuid());personal=Path(user.pw_dir).resolve()
    assert user.pw_name=='Weican_Chen' and str(personal)=='/home/Weican_Chen'
    inside(SOURCE,personal)
    config_path=inside(args.config,personal);config=json.loads(config_path.read_text(encoding='utf-8'))
    assert config['schema']=='attention-joint-ising-v1' and config['ready'] is True
    manifest_path=inside(args.source_manifest,personal);manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    assert manifest['code_commit']==args.source_commit
    declared={row['path'] for row in manifest['files']}
    required={'baselines/common.py','baselines/perplexity.py','experiments/attention_e01/verify_inputs.py','experiments/attention_joint_ising/job.py','experiments/attention_joint_ising/attention.py','experiments/attention_joint_ising/ctmc.py','experiments/attention_joint_ising/evaluate.py','experiments/attention_joint_ising/scoring.py','experiments/attention_joint_ising/moment.pt'}
    assert required<=declared and len(declared)==len(manifest['files'])
    for row in manifest['files']:
        path=(SOURCE/row['path']).resolve();assert path.is_relative_to(SOURCE)
        assert digest(path)==row['sha256'],row['path']
    output_root=inside(config['output_root'],personal,exists=False);output_root.mkdir(parents=True,exist_ok=True)
    output=output_root/(args.stage+'-'+os.environ['SLURM_JOB_ID']);output.mkdir(exist_ok=False)
    summary=dict(stage=args.stage,started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),job_id=os.environ['SLURM_JOB_ID'],node=os.environ['SLURM_JOB_NODELIST'],source_commit=args.source_commit,source_manifest_sha256=digest(manifest_path),config_sha256=digest(config_path),source_files_verified=len(manifest['files']),gpu_stage=gpu,passed=False,cases=[])
    save(output/'stage_summary.json',summary)
    started=time.monotonic()
    try:
        from experiments.attention_e01.verify_inputs import verify
        inputs=verify(config['model'],config['text'],config['expected_manifest'],str(personal));save(output/'inputs_verified.json',inputs)
        if args.stage in ['cpu_preflight','gpu_preflight']:
            command=[sys.executable,'-B','-X','utf8','-m','unittest','discover','-s','experiments/attention_joint_ising','-p','test_*.py','-v']
            env=dict(os.environ,CUDA_VISIBLE_DEVICES='')
            result=subprocess.run(command,cwd=SOURCE,env=env,text=True,capture_output=True)
            (output/'tests.stdout.txt').write_text(result.stdout,encoding='utf-8',newline='\n');(output/'tests.stderr.txt').write_text(result.stderr,encoding='utf-8',newline='\n')
            summary['tests']={'command':command,'exit_code':result.returncode,'gpu_hidden':True};result.check_returncode()
        if not gpu:
            summary['passed']=True;return
        import torch,transformers
        from transformers import AutoModelForCausalLM,AutoTokenizer
        assert transformers.__version__=='4.45.2'
        import transformers.models.qwen2.modeling_qwen2 as qwen
        assert digest(qwen.__file__)=='c0f712cc217640b9dd3d168ed000a5dc92079fc850385e5604a150c134d70fec'
        if args.stage=='gpu_preflight':
            command=[sys.executable,'-B','-X','utf8',str(SOURCE/'baselines/perplexity.py'),'--model',config['model'],'--text-file',config['text'],'--output',str(output/'bf16_full.json')]
            with (output/'bf16_full.stdout.txt').open('x',encoding='utf-8') as out,(output/'bf16_full.stderr.txt').open('x',encoding='utf-8') as err:subprocess.run(command,cwd=SOURCE,stdout=out,stderr=err,check=True)
            baseline=json.loads((output/'bf16_full.json').read_text(encoding='utf-8'))
            assert baseline['scored_tokens']==config['expected_targets'] and baseline['source_tokens']==config['expected_tokens']
            assert abs(baseline['perplexity']-config['expected_bf16_full_ppl'])<1e-8
            summary['original_bf16_full']=baseline
        else:
            predecessor=inside(config['passing_gpu_preflight'],personal)
            previous=json.loads(predecessor.read_text(encoding='utf-8'))
            assert previous['passed'] and previous['source_commit']==args.source_commit and previous['stage']=='gpu_preflight'
            summary['passing_gpu_preflight']=str(predecessor)
        torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False
        tokenizer=AutoTokenizer.from_pretrained(config['model'],local_files_only=True)
        token_ids=tokenizer(Path(config['text']).read_text(encoding='utf-8'),add_special_tokens=False,return_tensors='pt').input_ids[0]
        token_hash=hashlib.sha256(token_ids.to(torch.int64).contiguous().numpy().tobytes()).hexdigest()
        assert token_ids.numel()==config['expected_tokens'] and token_hash==config['token_sha256']
        model=AutoModelForCausalLM.from_pretrained(config['model'],local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval()
        assert len(model.model.layers)==24 and all(type(layer.mlp).__name__=='Qwen2MLP' for layer in model.model.layers)
        before=state_hash(model,torch)
        calibration=torch.load(HERE/'moment.pt',map_location='cpu',weights_only=True)[f'{config["context"]}_0.3_max4']
        from experiments.attention_joint_ising.evaluate import evaluate_case
        cases=matrix(config)
        if args.stage=='gpu_preflight':
            cases=[{**cases[0],'examples':4,'decode':8,'batch':4,'audit_logits':True},
                   {**cases[0],'examples':4,'decode':8,'batch':4,'audit_logits':True},
                   {**cases[1],'mode':'digital_sdpa','examples':4,'decode':8,'batch':4,'audit_logits':True},
                   {**cases[1],'examples':4,'decode':8,'batch':4},
                   {**cases[2],'examples':4,'decode':8,'batch':4},
                   *[{**cases[5],'samples':n,'examples':4,'decode':8,'batch':4} for n in [32,128,512,1024]]]
            for i,c in enumerate(cases):c['case_id']=f'pilot_{i:03d}'
        elif args.stage=='full_confirm':
            selected=config.get('full_confirm_samples');assert isinstance(selected,int) and selected in config['samples']
            cases=[{**cases[0],'protocol':'full','case_id':'full_sdpa'},{**cases[5],'samples':selected,'protocol':'full','case_id':'full_screen_ising'},{**cases[23],'mode':'screen_iid','samples':selected,'protocol':'full','case_id':'full_screen_iid'}]
        save(output/'registered_cases.json',cases)
        summary.update(token_sha256=token_hash,source_tokens=token_ids.numel(),model_state_before_sha256=before,environment={'torch':torch.__version__,'transformers':transformers.__version__,'gpu':torch.cuda.get_device_name(),'python':sys.version},registered_case_count=len(cases))
        save(output/'stage_summary.json',summary)
        signal.signal(signal.SIGALRM,elapsed_timeout)
        for case in cases:
            if time.monotonic()-started>config['max_stage_seconds']:raise TimeoutError('Stage runtime budget exceeded; unrun cases remain incomplete')
            case.update(source_commit=args.source_commit,input_report=str(output/'inputs_verified.json'),model_revision=inputs['model_revision'],token_sha256=token_hash)
            signal.alarm(int(config['max_case_seconds']))
            begin=time.monotonic()
            logits_hash=hashlib.sha256();handle=None
            if case.get('audit_logits'):
                def hash_logits(module,inputs,values):
                    logits_hash.update(str(tuple(values.shape)).encode())
                    logits_hash.update(values.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes())
                handle=model.lm_head.register_forward_hook(hash_logits)
            try:result=evaluate_case(model,token_ids,case,calibration)
            finally:
                if handle is not None:handle.remove()
            if case.get('audit_logits'):result['scored_logits_sha256']=logits_hash.hexdigest()
            signal.alarm(0)
            result.update(execution_source_commit=args.source_commit,input_manifest_sha256=inputs['expected_manifest_sha256'],full_model_state_before_sha256=before,case_wall_seconds=time.monotonic()-begin)
            path=output/(case['case_id']+'.json');save(path,result)
            line=dict(case_id=case['case_id'],mode=case['mode'],samples=case['samples'],seed=case['seed'],selection=case['selection'],protocol=case['protocol'],perplexity=result['perplexity'],scored_tokens=result['scored_tokens'],wall_seconds=result['case_wall_seconds'],file=path.name,sha256=digest(path))
            with (output/'journal.jsonl').open('a',encoding='utf-8',newline='\n') as log:log.write(json.dumps(line)+'\n');log.flush()
            summary['cases'].append(line);save(output/'stage_summary.json',summary);print(json.dumps(line),flush=True)
        after=state_hash(model,torch);assert before==after,'Model parameters/buffers changed during Attention evaluation'
        summary['model_state_after_sha256']=after
        if args.stage=='gpu_preflight':
            p0=json.loads((output/'pilot_000.json').read_text(encoding='utf-8'));p1=json.loads((output/'pilot_001.json').read_text(encoding='utf-8'));p2=json.loads((output/'pilot_002.json').read_text(encoding='utf-8'));p3=json.loads((output/'pilot_003.json').read_text(encoding='utf-8'))
            assert p0['scored_logits_sha256']==p1['scored_logits_sha256'],'Raw SDPA is not bitwise reproducible on the registered pilot'
            assert p0['scored_logits_sha256']==p2['scored_logits_sha256'],'Adapter with original SDPA core changes scored logits'
            assert p0['nll_sum']==p1['nll_sum']==p2['nll_sum']
            summary['wrapper_original_sdpa_logits_bitwise_equal']=True
            summary['smoke_manual_FP32_vs_BF16_sdpa_delta_nll']=p3['mean_nll']-p0['mean_nll']
            summary['suffix_sweep_estimate_upper_seconds']=sum(r['wall_seconds'] for r in summary['cases'] if r['mode']=='screen_ising')/4*128*34
        summary['passed']=True
    except BaseException as error:
        summary.update(error=repr(error),traceback=traceback.format_exc());raise
    finally:
        signal.alarm(0) if hasattr(signal,'alarm') else None
        summary.update(finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),wall_seconds=time.monotonic()-started)
        save(output/'stage_summary.json',summary)
        files=[dict(path=str(path.relative_to(output)),bytes=path.stat().st_size,sha256=digest(path)) for path in sorted(output.iterdir()) if path.is_file() and path.name!='artifacts.json']
        save(output/'artifacts.json',{'source_commit':args.source_commit,'files':files})

if __name__=='__main__':main()
