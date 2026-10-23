"""Slurm-only staged preflight and 4096-target paired pilot, no implicit full sweep."""
import argparse
import gc
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

from qwen3.baselines.support import check_config, check_data, save, sha256, verify_files, verify_source

SOURCE = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).with_name('config.json')


def artifact(path, value):
    if path.exists():
        raise FileExistsError('refusing to overwrite signed result: ' + str(path))
    save(path, value)
    save(path.with_suffix('.sha256.json'), dict(name=path.name, sha256=sha256(path)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True)
    p.add_argument('--stage', choices=['cpu', 'pilot'], required=True)
    p.add_argument('--index', type=int, choices=[0, 1], default=0)
    args = p.parse_args()
    root = Path(args.root).resolve()
    assert str(root).startswith('/home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-')
    assert os.environ.get('SLURM_JOB_ID'), 'all execution must be Slurm allocated'
    os.environ['PBIT_PROJECT_ROOT'] = str(root)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    execution = verify_source(SOURCE)
    config = json.loads(CONFIG_PATH.read_text())
    baseline_root = Path(config['baseline_root'])
    baseline_source = baseline_root / config['baseline_source']
    anchor_source = verify_source(baseline_source)
    assert anchor_source['commit'] == config['baseline_execution_commit']
    baseline_config = json.loads((baseline_source / 'config.json').read_text())
    data = check_data(baseline_config)
    import torch
    import transformers
    assert transformers.__version__ == '4.51.3'
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.manual_seed(0)
    from .test_port import run as test_port
    from .vendor.scoring import ids_sha256
    from .scorer import evaluate_case
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if args.stage == 'cpu':
        tests = test_port('cpu')
        prepared = []
        for spec in baseline_config['models']:
            name = spec['id'].split('/')[-1]
            source = baseline_root / 'prepared' / (name + '.json')
            entry = json.loads(source.read_text())
            assert entry['cpu_prepare_ok'] and entry['model'] == spec
            assert entry['config_sha256'] == sha256(baseline_source / 'config.json')
            verify_files(entry)
            destination = root / 'anchor' / 'prepared' / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            prepared.append(dict(model=spec, manifest_sha256=sha256(source), manifest=str(source)))
        shutil.copyfile(baseline_root / 'prepared/cpu_tests_passed.json', root / 'anchor/prepared/cpu_tests_passed.json')
        artifact(root / 'preflight.json', dict(status='PASS', tests=tests, prepared=prepared,
            data=data, source=execution, config_sha256=sha256(CONFIG_PATH),
            environment=dict(torch=torch.__version__, transformers=transformers.__version__),
            command=[sys.executable, *sys.argv], slurm_job_id=os.environ['SLURM_JOB_ID']))
        print('CPU_PREFLIGHT_COMPLETE', flush=True)
        return

    preflight = json.loads((root / 'preflight.json').read_text())
    assert preflight['status'] == 'PASS' and preflight['source'] == execution
    assert preflight['config_sha256'] == sha256(CONFIG_PATH)
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    spec = baseline_config['models'][args.index]
    name = spec['id'].split('/')[-1]
    prepared_path = baseline_root / 'prepared' / (name + '.json')
    assert sha256(prepared_path) == preflight['prepared'][args.index]['manifest_sha256']
    prepared = json.loads(prepared_path.read_text())
    verify_files(prepared)
    result_dir = root / 'results' / name
    result_dir.mkdir(parents=True, exist_ok=True)
    if (result_dir / 'gates.json').exists():
        raise RuntimeError('pilot already started; inspect existing results before any explicit resume')
    gpu_test = test_port('cuda')
    from .vendor.validate import run as validate_kernel
    kernel_test = validate_kernel()
    artifact(result_dir / 'gates.json', dict(native=gpu_test, kernels=kernel_test,
        source=execution, config_sha256=sha256(CONFIG_PATH)))
    gc.collect()
    torch.cuda.empty_cache()
    # Exact existing vectorized reference, unchanged code/config/weights.
    # New output directory; never overwrite completed Issue136 results.
    command = [sys.executable, str(baseline_source / 'evaluate.py'), '--project',
               str(root / 'anchor'), '--index', str(args.index)]
    subprocess.run(command, check=True)
    anchor_path = root / 'anchor/results' / (name + '.json')
    anchor = json.loads(anchor_path.read_text())
    assert anchor['token_ids_int64_le_sha256'] == config['expected_test_token_sha256']
    assert anchor['scored_tokens'] == 299077
    original_anchor = json.loads((baseline_root / 'results' / (name + '.json')).read_text())
    # No tolerance relaxation; the vectorized anchor must reproduce exactly.
    assert anchor['nll_sum'] == original_anchor['nll_sum'], (anchor['nll_sum'], original_anchor['nll_sum'])
    tokenizer = AutoTokenizer.from_pretrained(prepared['local_path'], local_files_only=True, trust_remote_code=False)
    def tokenize(split):
        text = Path(data[split]['path']).read_bytes().decode('utf-8')
        return tokenizer(text, return_tensors='pt', add_special_tokens=False).input_ids[0]
    ids = tokenize('wiki.test.raw')
    assert ids_sha256(ids.tolist()) == config['expected_test_token_sha256']
    def load():
        model = AutoModelForCausalLM.from_pretrained(prepared['local_path'], local_files_only=True,
            trust_remote_code=False, torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
        check_config(model.config, spec)
        assert all(p.dtype == torch.bfloat16 for p in model.parameters())
        assert model.model.rotary_emb.inv_freq.dtype == torch.float32
        return model
    # Qwen3-specific calibration, only the original model and TRAIN text.
    model = load()
    real_case = dict(mode='sdpa', ffn='none', sampler='none', context=64,
        decode=4, examples=2, batch=2, capture_scored_logits_sha256=True)
    real_native = evaluate_case(model, ids, real_case, None)
    real_wrapper = evaluate_case(model, ids, dict(real_case, mode='digital_sdpa'), None)
    assert real_native['scored_logits_sha256'] == real_wrapper['scored_logits_sha256']
    artifact(result_dir / 'real_model_equivalence.json', dict(native=real_native, wrapper=real_wrapper,
        status='PASS', criterion='bitwise same FP32 scored-logits SHA', source=execution))
    from .calibrate import calibrate
    calibration = calibrate(model, tokenize('wiki.train.raw'), **{k: config['calibration'][k]
        for k in ('context', 'fit_examples', 'holdout_examples')})
    calibration.update(model=spec, data=data['wiki.train.raw'], source=execution)
    artifact(result_dir / 'calibration.json', calibration)
    del model
    gc.collect()
    torch.cuda.empty_cache()
    cases = [dict(label='bf16', mode='sdpa', ffn='none', sampler='none', samples=1, seed=0)]
    for label, mode, sampler, samples in [('ffn', 'sdpa', 'none', 1),
            ('screen_exact_ffn', 'screen_exact', 'none', 1),
            ('rejection128_ffn', 'screen_ising', 'rejection', 128),
            ('winner1024_ffn', 'screen_ising', 'winner', 1024)]:
        cases += [dict(label=label, mode=mode, ffn='b4_t32', sampler=sampler,
                       samples=samples, seed=seed) for seed in config['seeds']]
    environment = dict(torch=torch.__version__, transformers=transformers.__version__,
        cuda=torch.version.cuda, gpu=torch.cuda.get_device_name(), python=platform.python_version(),
        slurm_job_id=os.environ['SLURM_JOB_ID'], hostname=platform.node(),
        pip_freeze=subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True).splitlines())
    for number, case in enumerate(cases):
        print(f'CASE_START {number + 1}/{len(cases)} {name} {case}', flush=True)
        case.update({k: config[k] for k in ('context', 'decode', 'examples', 'batch', 'stride', 'protocol')})
        case.update(selection='fixed', budget_blocks=8, target_fraction=.30,
            input_provenance=dict(model=spec, prepared_sha256=sha256(prepared_path), data=data,
                config_sha256=sha256(CONFIG_PATH), calibration_sha256=sha256(result_dir / 'calibration.json')))
        model = load()
        torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()
        result = evaluate_case(model, ids, case, calibration)
        assert result['scored_tokens'] == 4096
        result.update(model=spec, source=execution, environment=environment,
            config_sha256=sha256(CONFIG_PATH), calibration_sha256=sha256(result_dir / 'calibration.json'),
            anchor_sha256=sha256(anchor_path), command=[sys.executable, *sys.argv],
            wall_seconds=time.monotonic() - started,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved())
        destination = result_dir / (case['label'] + '_s' + str(case['seed']) + '.json')
        artifact(destination, result)
        print(f'CASE_COMPLETE {name} {destination.name} ppl={result["perplexity"]:.8f} seconds={result["wall_seconds"]:.1f}', flush=True)
        del model, result
        gc.collect()
        torch.cuda.empty_cache()
    artifact(result_dir / 'complete.json', dict(status='COMPLETE', cases=len(cases), protocol='suffix',
        scored_tokens_per_case=4096, source=execution, config_sha256=sha256(CONFIG_PATH)))
    print('PILOT_COMPLETE ' + name, flush=True)


if __name__ == '__main__':
    main()
