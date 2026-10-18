"""Issue 19: frozen-scale, full-WT2 FFN decomposition. Run only through Slurm.

This is the statistical numerical reference for fixed weights and exact counting.
Its restored matrix readout is FP32 GEMM, as in the historical Qwen experiment.
It does NOT simulate every finite-width tile rescale, SRAM, clock, or PRNG state.
Attention, RMSNorm, residual, embedding and vocabulary readout stay original BF16.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'baselines/llama2_7b'))
from protocol import CORPUS_SHA256, EXPECTED_SHAPE, sha256, verify_identity, windows, write_json
from evaluate import evaluate_window
if __package__:
    from .numeric import quantize_weight, dequantize_weight, encode_fixed, sample_counts, q10_swiglu
else:
    from numeric import quantize_weight, dequantize_weight, encode_fixed, sample_counts, q10_swiglu

TRAIN_SHA = '6707892fa3788b5ab9ed78ab5ff37d9fe825f6011a2ad4fcd6a6d467f0e7da57'
TEST_TOKEN_SHA = 'd47afcd2762c6a3e70f50c5b7de0e4ccad565d812aee21772b7cd276b7b8626c'


def source_record():
    commit = os.environ.get('SOURCE_COMMIT', '')
    if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise RuntimeError('Immutable snapshot needs SOURCE_COMMIT=<40 hex>')
    paths = list(HERE.rglob('*.py')) + list((HERE/'vendor_q10').glob('*.json'))
    paths += [ROOT/'baselines/llama2_7b/protocol.py', ROOT/'baselines/llama2_7b/evaluate.py']
    return {'repository': 'rayggxia-workspace/pbit-llm-qwen-baselines', 'commit': commit,
            'files': {str(p.relative_to(ROOT)).replace('\\', '/'): sha256(p) for p in sorted(set(paths))}}


def setup(args):
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('All GPU execution must use Slurm')
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if transformers.__version__ != '4.45.2':
        raise RuntimeError('Requires Transformers 4.45.2')
    config = json.loads(args.config.read_text(encoding='utf-8'))
    seed = int(config.get('seed', 0))
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    identity = verify_identity(args.model, args.identity_manifest)
    for name, value in [('source.json', source_record()), ('identity.json', identity),
                        ('config.json', config), ('command.json', {'argv': sys.argv})]:
        write_json(args.output/name, value)
    write_json(args.output/'environment.json', {
        'slurm_job_id': os.environ['SLURM_JOB_ID'], 'python': sys.version,
        'torch': torch.__version__, 'transformers': transformers.__version__,
        'cuda': torch.version.cuda, 'gpu': torch.cuda.get_device_name(),
        'platform': platform.platform(), 'tf32': False,
        'config_sha256': sha256(args.config), 'config_path': str(args.config),
        'model_path': str(args.model), 'energy_measurement': 'not performed'})
    tokenizer = AutoTokenizer.from_pretrained(str(args.model), local_files_only=True,
                                             trust_remote_code=False, use_fast=True)
    model = AutoModelForCausalLM.from_pretrained(
        str(args.model), torch_dtype=torch.bfloat16, attn_implementation='sdpa',
        use_safetensors=identity['use_safetensors'], local_files_only=True,
        trust_remote_code=False, low_cpu_mem_usage=True).eval().to('cuda')
    from transformers.models.llama.modeling_llama import LlamaSdpaAttention
    if len(model.model.layers) != 32 or any(not isinstance(l.self_attn, LlamaSdpaAttention)
                                           for l in model.model.layers):
        raise RuntimeError('Unexpected Llama2 architecture or attention')
    for key, expected in EXPECTED_SHAPE.items():
        if getattr(model.config, key, None) != expected:
            raise RuntimeError('Configuration mismatch: '+key)
    return torch, tokenizer, model, config


def token_ids(tokenizer, path, expected_sha, torch):
    actual = sha256(path)
    if actual != expected_sha:
        raise RuntimeError('Raw corpus SHA mismatch: '+actual)
    return tokenizer(path.read_text(encoding='utf-8'), add_special_tokens=False,
                     return_tensors='pt').input_ids


def ids_sha(ids):
    return hashlib.sha256(ids.numpy().astype('<i8', copy=False).tobytes()).hexdigest()


def power2_scale(maximum, torch):
    # Offline calibration only; no runtime max or test-set tuning.
    return torch.pow(2., torch.ceil(torch.log2(maximum.clamp_min(2.**-20))))


def decoded_w8(weight):
    codes, scales = quantize_weight(weight)
    return dequantize_weight(codes, scales)


def calibrate(args):
    torch, tokenizer, model, config = setup(args)
    ids = token_ids(tokenizer, args.train, TRAIN_SHA, torch)
    n = int(config.get('calibration_tokens', 8192))
    length = int(config.get('calibration_window', 2048))
    if n <= 0 or n % length or n > ids.shape[1]:
        raise ValueError('Calibration requires complete nonoverlapping train windows')
    selected = ids[:, :n].contiguous()
    hidden = [[] for _ in range(32)]
    handles = []
    def make_hook(index):
        def hook(_module, inputs):
            hidden[index].append(inputs[0].detach().cpu())
        return hook
    for i, layer in enumerate(model.model.layers):
        handles.append(layer.mlp.register_forward_pre_hook(make_hook(i)))
    with torch.inference_mode():
        for start in range(0, n, length):
            out = model.model(input_ids=selected[:, start:start+length].to('cuda'),
                              use_cache=False, return_dict=True)
            del out
    for h in handles:
        h.remove()
    layers = []
    import torch.nn.functional as F
    with torch.inference_mode():
        for i, layer in enumerate(model.model.layers):
            maxima = torch.zeros(64, device='cuda')
            for xcpu in hidden[i]:
                x = xcpu.to('cuda').float()
                maxima = torch.maximum(maxima, x.reshape(-1, 64, 64).abs().amax((0, 2)))
            sx = power2_scale(maxima, torch)
            wg = decoded_w8(layer.mlp.gate_proj.weight)
            wu = decoded_w8(layer.mlp.up_proj.weight)
            zmax = torch.zeros(172, device='cuda')
            for xcpu in hidden[i]:
                x = xcpu.to('cuda').float()
                _, _, xq = encode_fixed(x, sx)
                g, u = F.linear(xq, wg), F.linear(xq, wu)
                z = F.silu(g)*u
                zmax = torch.maximum(zmax, z.reshape(-1, 172, 64).abs().amax((0, 2)))
            sz = power2_scale(zmax, torch)
            layers.append({'layer': i, 'sx': sx.cpu().tolist(), 'sz': sz.cpu().tolist(),
                           'x_max': maxima.cpu().tolist(), 'z_max': zmax.cpu().tolist()})
            hidden[i].clear()
            del wg, wu, x, xq, g, u, z
            print('calibrated_layer='+str(i), flush=True)
    record = {'schema': 'llama2_fixed_a8mag_v1', 'layers': layers,
              'source_commit': os.environ['SOURCE_COMMIT'],
              'train_raw_sha256': TRAIN_SHA, 'train_token_ids_sha256': ids_sha(ids),
              'selected_train_tokens': n, 'selected_token_ids_sha256': ids_sha(selected),
              'calibration_window': length, 'test_data_used': False,
              'procedure': 'BF16 teacher MLP inputs; fixed per64 pow2 Sx; tile64 W8; deterministic A8 x; accurate FP32 SiLU(g)*u; fixed per64 pow2 Sz',
              'activation_encoding': '8 magnitude bits q/256 plus separate sign; not signed INT8',
              'weight_encoding': 'symmetric INT8 per64x64 tile maxabs/127'}
    write_json(args.output/'calibration.json', record)
    finalize(args.output)


def make_mlp_class(torch):
    import torch.nn.functional as F
    class FixedFFN(torch.nn.Module):
        def __init__(self, original, scale, config, index):
            super().__init__()
            # Retain only decoded weights. No original module, integer full copy,
            # dual-random weight variance, or duplicate shadow checkpoint.
            wg = decoded_w8(original.gate_proj.weight)
            wu = decoded_w8(original.up_proj.weight)
            self.register_buffer('wgu', torch.cat((wg, wu), 0))
            del wg, wu
            self.register_buffer('wd', decoded_w8(original.down_proj.weight))
            self.register_buffer('sx', torch.tensor(scale['sx'], device='cuda').repeat_interleave(64))
            self.register_buffer('sz', torch.tensor(scale['sz'], device='cuda').repeat_interleave(64))
            self.config = config
            self.genx = torch.Generator(device='cuda').manual_seed(int(config['seed'])+1000003*index+101)
            self.genz = torch.Generator(device='cuda').manual_seed(int(config['seed'])+1000003*index+503)
            self.stats = {}

        def add_stats(self, prefix, values):
            for key, value in values.items():
                name = prefix+'_'+key
                if name not in self.stats:
                    self.stats[name] = value.detach().clone()
                else:
                    self.stats[name] += value.detach()

        def encoded_input(self, x, scale, generator, stage):
            q, sign, decoded = encode_fixed(x, scale)
            self.add_stats(stage, {'values': torch.tensor(q.numel(), device=x.device, dtype=torch.int64),
                                   'zero_codes': (q == 0).sum(),
                                   'upper_codes': (q == 255).sum(),
                                   'clipped_codes': ((x.abs()*256/scale).round() > 255).sum(),
                                   'sum_probability': (q.double()/256).sum()})
            if self.config['mode'] == 'deterministic':
                return decoded, 1
            T = int(self.config['T'])
            counts = sample_counts(q, T, method=self.config['method'], share64=True, generator=generator)
            self.add_stats(stage, {'sum_events': counts.to(torch.int64).sum(),
                                   'zero_event_counts': (counts == 0).sum()})
            return sign.float()*scale*counts.float(), T

        def forward(self, x):
            original_dtype = x.dtype
            value = x.float()
            if self.config['mode'] == 'weights_only':
                xi, tx = value, 1
            else:
                xi, tx = self.encoded_input(value, self.sx, self.genx, 'x')
            gu = F.linear(xi, self.wgu)/tx
            g, u = gu.chunk(2, -1)
            if self.config['post'] == 'q10':
                z, qs = q10_swiglu(g, u, return_stats=True)
                self.add_stats('q10', qs)
            else:
                z = F.silu(g)*u
            if self.config['mode'] == 'weights_only':
                zi, tz = z, 1
            else:
                zi, tz = self.encoded_input(z, self.sz, self.genz, 'z')
            return (F.linear(zi, self.wd)/tz).to(original_dtype)
    return FixedFFN


def evaluate(args):
    torch, tokenizer, model, config = setup(args)
    import torch.nn.functional as F
    if config.get('mode') not in ('weights_only', 'deterministic', 'counts'):
        raise ValueError('Unknown FFN mode')
    if config.get('post') not in ('exact', 'q10'):
        raise ValueError('Unknown postprocessor')
    calibration = json.loads(args.calibration.read_text(encoding='utf-8'))
    if calibration.get('schema') != 'llama2_fixed_a8mag_v1' or len(calibration['layers']) != 32:
        raise ValueError('Invalid calibration schema')
    FixedFFN = make_mlp_class(torch)
    with torch.inference_mode():
        for i, layer in enumerate(model.model.layers):
            layer.mlp = FixedFFN(layer.mlp, calibration['layers'][i], config, i)
        torch.cuda.empty_cache()
    ids = token_ids(tokenizer, args.data, CORPUS_SHA256, torch)
    if ids_sha(ids) != TEST_TOKEN_SHA:
        raise RuntimeError('Full WT2 tokenization differs from baseline')
    limit = config.get('prefix_tokens')
    if limit is not None:
        if not 2 <= int(limit) < ids.shape[1]:
            raise ValueError('Prefix screen must be clearly shorter than full corpus')
        ids = ids[:, :int(limit)].contiguous()
    window, stride = int(config.get('window', 2048)), int(config.get('stride', 512))
    if not 0 < stride < window <= 4096:
        raise ValueError('Invalid sliding window')
    protocol = {'name': 'full_wikitext2_raw_sliding_window_ppl' if limit is None else 'prefix_screen_sliding_window_ppl_NOT_FULL',
                'attention': 'unchanged BF16 SDPA; no PV sampling or Ising',
                'ffn_layers': list(range(32)), 'window': window, 'stride': stride,
                'add_special_tokens': False, 'corpus_tokens': ids.shape[1],
                'scored_targets': ids.shape[1]-1, 'target_positions': '1..N-1 exactly once',
                'data_raw_sha256': CORPUS_SHA256, 'full_token_ids_sha256': TEST_TOKEN_SHA,
                'scored_token_ids_sha256': ids_sha(ids), 'calibration_sha256': sha256(args.calibration),
                'config_sha256': sha256(args.config), 'precision': 'BF16 interfaces; restored FP32 GEMM; FP32 CE/FP64 sum',
                'limitation': 'Exact statistical counts, not a full bit-true fixed-width tile-rescaling datapath; no physical RNG or energy measured',
                'warmup': 'none; first scored window starts from seeded generators'}
    write_json(args.output/'protocol.json', protocol)
    begin = time.perf_counter()
    total, counted = 0., 0
    with torch.inference_mode(), (args.output/'windows.jsonl').open('x', encoding='utf-8', newline='\n') as log:
        for number, item in enumerate(windows(ids.shape[1], window, stride), 1):
            nll, count = evaluate_window(model, ids, item, torch, F)
            total = math.fsum((total, nll))
            counted += count
            rec = {'number': number, **item.record(), 'nll': nll, 'scored_so_far': counted,
                   'elapsed_seconds': time.perf_counter()-begin}
            log.write(json.dumps(rec, allow_nan=False)+'\n')
            log.flush()
            print(f"window={number} end={item.end}/{ids.shape[1]} elapsed={rec['elapsed_seconds']:.2f}", flush=True)
    if counted != ids.shape[1]-1:
        raise AssertionError('Did not score every next-token target exactly once')
    torch.cuda.synchronize()
    elapsed = time.perf_counter()-begin
    mean = total/counted
    stats = [{key: value.item() for key, value in l.mlp.stats.items()} for l in model.model.layers]
    write_json(args.output/'layer_stats.json', stats)
    write_json(args.output/'summary.json', {'status': 'completed', 'protocol': protocol['name'],
               'config': config, 'source_commit': os.environ['SOURCE_COMMIT'],
               'total_nll': total, 'scored_tokens': counted, 'mean_nll': mean,
               'ppl': math.exp(mean) if mean < 700 else None, 'wall_seconds': elapsed,
               'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
               'peak_reserved_bytes': torch.cuda.max_memory_reserved(),
               'slurm_job_id': os.environ['SLURM_JOB_ID']})
    finalize(args.output)


def finalize(output):
    write_json(output/'ARTIFACT_MANIFEST.json',
               {p.name: {'sha256': sha256(p), 'bytes': p.stat().st_size}
                for p in sorted(output.iterdir()) if p.is_file()})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['calibrate', 'evaluate'])
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--identity-manifest', type=Path, required=True)
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--train', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--calibration', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.action == 'evaluate' and a.calibration is None:
        p.error('evaluate requires --calibration')
    (calibrate if a.action == 'calibrate' else evaluate)(a)


if __name__ == '__main__':
    main()
