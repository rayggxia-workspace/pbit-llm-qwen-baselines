"""Original Qwen3-4B, W8-only FFN and dense native attention; no training."""
from pathlib import Path
import argparse
import collections
import hashlib
import importlib.util
import json
import math
import os
import platform
import sys
import time


HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(16 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8', newline='\n')
    path.with_suffix(path.suffix + '.sha256').write_text(sha(path) + '\n', encoding='ascii')


def tensor_sha(x):
    return hashlib.sha256(x.detach().cpu().contiguous().view(__import__('torch').uint8).numpy().tobytes()).hexdigest()


def quantize(weight):
    """Offline tile64 max-cover PoT LSB, W8[-127,127], exact dyadic RNE."""
    import torch
    assert weight.ndim == 2 and all(n % 64 == 0 for n in weight.shape)
    assert bool(torch.isfinite(weight).all())
    rows, cols = weight.shape
    tiles = weight.detach().float().reshape(rows // 64, 64, cols // 64, 64).permute(0, 2, 1, 3)
    maximum = tiles.double().abs().amax((-1, -2))
    mantissa, exponent = torch.frexp(maximum / 127)
    exponent = exponent - (mantissa == .5).int()
    exponent = torch.where(maximum == 0, torch.full_like(exponent, -24), exponent)
    assert bool(((exponent >= -126) & (exponent <= 120)).all())
    def pow2(e):
        return ((e.long() + 1023) << 52).contiguous().view(torch.float64)
    codes_tiled = (tiles.double() * pow2(-exponent)[..., None, None]).round().clamp(-127, 127)
    decoded = (codes_tiled * pow2(exponent)[..., None, None]).permute(0, 2, 1, 3).reshape(rows, cols).contiguous()
    codes = codes_tiled.to(torch.int8).permute(0, 2, 1, 3).reshape(rows, cols).contiguous()
    bf16 = decoded.to(torch.bfloat16)
    assert torch.equal(bf16.double(), decoded), 'W8 dyadic weights must be exactly representable in BF16'
    return codes, exponent.to(torch.int8), bf16


def preflight(output):
    import numpy as np
    import torch
    torch.set_num_threads(1)
    spec = importlib.util.spec_from_file_location('existing_pot64', HERE / 'pot64_reference.py')
    upstream = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upstream)
    torch.manual_seed(259)
    cases = [torch.randn(128, 128).to(torch.bfloat16) * .125,
             torch.zeros(64, 64, dtype=torch.bfloat16),
             torch.tensor([0, .5, 1.5, 2.5, -0.5, -1.5, -2.5, 127.],
                          dtype=torch.bfloat16).repeat(64, 8)]
    for x in cases:
        q, e, y = quantize(x)
        assert torch.equal(e, upstream.choose_exponents(x, 8))
        oq, oy, _ = upstream.quantize(x, 8, e)
        assert torch.equal(q.long(), oq.long()) and torch.equal(y.float(), oy)
        for i, j in [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (63, 63)]:
            code = max(-127, min(127, round(math.ldexp(float(x[i, j]), -int(e[i // 64, j // 64])))))
            assert int(q[i, j]) == code
            assert float(y[i, j]) == math.ldexp(code, int(e[i // 64, j // 64]))
    # The exact scorer will be imported unchanged in both configurations.
    from wt2_reference import spans
    windows = list(spans(299078))
    counts = np.zeros(299078, dtype=np.uint8)
    for start, end, first in windows:
        assert start < first < end
        counts[first:end] += 1
    assert len(windows) == 292 and counts[0] == 0 and bool((counts[1:] == 1).all())
    save(output, dict(status='PASS', arithmetic_cases=len(cases),
        independent_scalar_dyadic_RNE=True, unchanged_pot64_initializer_match=True,
        exact_BF16_weight_decode=True, WT2_windows=292, WT2_targets=299077))


class Coverage:
    def __init__(self, model):
        self.coverage = {}
        self.totals = collections.Counter()
        for i, layer in enumerate(model.model.layers):
            def hook(module, args, layer_id=i):
                row = self.coverage.setdefault(layer_id, dict(calls=0, tokens=0))
                row['calls'] += 1
                row['tokens'] += args[0].shape[-2]
                self.totals[layer_id] += 1
            layer.mlp.register_forward_pre_hook(hook)
    def begin(self, *args, **kwargs):
        self.coverage = {}


def run(output):
    import numpy as np
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from wt2_reference import TEXT_SHA, TOKEN_SHA, score
    manifest = json.loads((HERE / 'SOURCE_MANIFEST.json').read_bytes())
    for name, expected in manifest.items():
        assert sha(HERE / name) == expected, name
    assert json.loads((output / 'CPU_RESULT.json').read_bytes())['status'] == 'PASS'
    plan = json.loads((HERE / 'PLAN.json').read_bytes())
    inputs = json.loads((HERE / 'INPUTS.json').read_bytes())
    parent = Path(inputs['parent_model'])
    for name, expected in inputs['parent_files_sha256'].items():
        assert sha(parent / name) == expected, name
    assert sha(inputs['text']) == TEXT_SHA
    tokenizer = AutoTokenizer.from_pretrained(parent, local_files_only=True, trust_remote_code=False)
    tokens = np.asarray(tokenizer.encode(Path(inputs['text']).read_text(encoding='utf-8'),
                                        add_special_tokens=False), dtype='<u4')
    assert len(tokens) == 299078 and hashlib.sha256(tokens.tobytes()).hexdigest() == TOKEN_SHA
    torch.set_num_threads(4)
    torch.manual_seed(101)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    # Gate the CUDA quantizer against the already-checked CPU arithmetic.
    probe = torch.randn(128, 128).to(torch.bfloat16)
    expected = quantize(probe)
    actual = quantize(probe.cuda())
    assert all(torch.equal(a, b.cpu()) for a, b in zip(expected, actual))
    save(output / 'GPU_QUANTIZER_GATE.json', dict(status='PASS', CPU_CUDA_bitwise=True))
    model = AutoModelForCausalLM.from_pretrained(parent, local_files_only=True,
        trust_remote_code=False, torch_dtype=torch.bfloat16, attn_implementation='sdpa').cuda().eval()
    model.requires_grad_(False)
    assert (model.config.num_hidden_layers, model.config.hidden_size, model.config.intermediate_size) == (36, 2560, 9728)
    context = Coverage(model)
    protocol = dict(model=plan['model'], revision=plan['revision'], original_untrained_parent=True,
        window=2048, stride=1024, windows=292, targets=299077,
        text_sha256=TEXT_SHA, token_sha256=TOKEN_SHA, chat_template=False,
        attention='unchanged native dense BF16 SDPA;no K screening;no sampling',
        quantization='only FFN gate/up/down W8;64x64 PoT max-cover offline;RNE;[-127,127]',
        activations='original BF16 native SwiGLU;no activation quantization',
        boundary='W8 weight-only quality control;not A9/P8 or cycle-level RTL replay',
        software=dict(torch=torch.__version__, transformers=transformers.__version__,
                      python=platform.python_version(), gpu=torch.cuda.get_device_name()),
        parent_files_sha256=inputs['parent_files_sha256'], source_sha256=manifest,
        slurm_job_id=os.environ.get('SLURM_JOB_ID'))
    save(output / 'PROTOCOL.json', protocol)
    started = time.monotonic()
    ref = score(model, tokens, output / 'BF16_reference', context, 101)
    assert ref['complete'] and ref['targets'] == 299077 and ref['windows'] == 292
    assert abs(ref['ppl'] - 11.537160373065971) < .02, 'inspect matching reference before W8 comparison'
    save(output / 'REFERENCE.json', ref)
    # All non-FFN parameter versions must remain unchanged.
    non_ffn = {n: (p.data_ptr(), p._version) for n, p in model.named_parameters() if '.mlp.' not in n}
    quantized = []
    for i, layer in enumerate(model.model.layers):
        for name in ['gate_proj', 'up_proj', 'down_proj']:
            parameter = getattr(layer.mlp, name).weight
            original_sha = tensor_sha(parameter)
            q, e, decoded = quantize(parameter)
            error = decoded.float() - parameter.float()
            quantized.append(dict(layer=i, projection=name, shape=list(q.shape),
                original_bf16_sha256=original_sha, codes_int8_sha256=tensor_sha(q),
                exponents_int8_sha256=tensor_sha(e), decoded_bf16_sha256=tensor_sha(decoded),
                exponent_histogram=dict(collections.Counter(e.cpu().flatten().tolist())),
                zero_code_count=int((q == 0).sum()), elements=q.numel(),
                squared_error_sum=float(error.square().sum())))
            parameter.copy_(decoded)
            del q, e, decoded, error
        save(output / 'QUANTIZATION_PROGRESS.json', dict(completed_layers=i + 1))
    assert len(quantized) == 108
    assert all((p.data_ptr(), p._version) == non_ffn[n]
               for n, p in model.named_parameters() if n in non_ffn)
    save(output / 'QUANTIZATION.json', quantized)
    context.totals.clear()
    result = score(model, tokens, output / 'W8_dense_original', context, 101)
    assert result['complete'] and result['targets'] == 299077 and result['windows'] == 292
    assert all(context.totals[i] == 292 for i in range(36))
    assert len(result['ffn_token_coverage']) == 36
    complete = dict(status='completed', BF16_reference_PPL=ref['ppl'],
        W8_dense_original_PPL=result['ppl'], PPL_change_percent=(result['ppl']/ref['ppl']-1)*100,
        windows=292, targets=299077, layers=36, quantized_matrices=108,
        no_training=True, no_sampling=True, no_K_screening=True,
        seconds=time.monotonic()-started, protocol_sha256=sha(output/'PROTOCOL.json'),
        BF16_result_sha256=sha(output/'BF16_reference/RESULT.json'),
        W8_result_sha256=sha(output/'W8_dense_original/RESULT.json'),
        BF16_windows_sha256=sha(output/'BF16_reference/WINDOWS.jsonl'),
        W8_windows_sha256=sha(output/'W8_dense_original/WINDOWS.jsonl'),
        quantization_sha256=sha(output/'QUANTIZATION.json'))
    save(output / 'COMPLETE.json', complete)
    print(json.dumps(complete), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--phase', choices=['cpu', 'gpu'], required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    if a.phase == 'cpu':
        preflight(a.output / 'CPU_RESULT.json')
    else:
        with __import__('torch').no_grad():
            run(a.output)
