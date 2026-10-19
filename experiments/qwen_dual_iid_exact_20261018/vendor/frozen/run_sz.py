"""Fixed Sz study. Frozen historical core/evaluator; no training or attention changes."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import torch
from torch.nn import functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from core import StochasticMatrixFFN, encode_fixed, quantize_int8, sample_counts

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def suite():
    configs = []
    for variant in ('sz_group', 'sz_layer', 'sz_dynamic', 'legacy'):
        for cycles in (256, 1024, 4096):
            for seed in (range(3) if variant == 'sz_group' else (0,)):
                configs.append(dict(variant=variant, cycles=cycles, seed=seed,
                                    backend='gaussian', split='test', max_tokens=0))
    configs.append(dict(variant='sz_matched_gu', cycles=4096, seed=0,
                        backend='gaussian', split='test', max_tokens=0))
    configs.append(dict(variant='baseline', cycles=4096, seed=0,
                        backend='gaussian', split='test', max_tokens=0))
    # Identical held-out text for exact conditional-binomial vs Gaussian checks.
    # Short samples cannot be compared numerically with full test PPL.
    for variant in ('sz_group', 'legacy'):
        for cycles in (256, 1024, 4096):
            for backend in ('binomial', 'gaussian'):
                configs.append(dict(variant=variant, cycles=cycles, seed=0,
                                    backend=backend, split='validation', max_tokens=128))
    return configs


def calibrate():
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    tok = AutoTokenizer.from_pretrained('models/Qwen2.5-0.5B', local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained('models/Qwen2.5-0.5B', local_files_only=True,
                torch_dtype=torch.bfloat16, attn_implementation='sdpa').cuda().eval()
    model.requires_grad_(False)
    all_ids = tok(Path('data/wikitext-2/wiki.train.raw').read_text(),
                  add_special_tokens=False, return_tensors='pt').input_ids
    assert all_ids.shape[-1] - 65536 > 8192
    ids = all_ids[:, :8192]
    old = json.loads(Path('results/calibration.json').read_text())['policies']['group_max']
    maxima, handles = {}, []
    for i, layer in enumerate(model.model.layers):
        _, w, _ = quantize_int8(torch.cat((layer.mlp.gate_proj.weight,
                                          layer.mlp.up_proj.weight), 0))
        scales = {s: torch.tensor(old[str(i)][s], device='cuda').repeat_interleave(64)
                  for s in ('x', 'g', 'u')}
        def hook(module, args, i=i, w=w, scales=scales):
            _, xq = encode_fixed(args[0].float(), scales['x'], 12)
            g, u = F.linear(xq, w).chunk(2, -1)
            _, gq = encode_fixed(g, scales['g'], 12)
            _, uq = encode_fixed(u, scales['u'], 12)
            z = F.silu(g) * u
            zm = F.silu(gq) * uq
            m = torch.maximum(z.abs(), zm.abs()).reshape(-1, z.shape[-1] // 64, 64).amax((0, 2))
            maxima[i] = m if i not in maxima else torch.maximum(maxima[i], m)
        handles.append(layer.mlp.register_forward_pre_hook(hook))
    with torch.inference_mode():
        for start in range(0, 8192, 2048):
            model.model(input_ids=ids[:, start:start+2048].cuda(), use_cache=False)
            print('calibrated', start + 2048, flush=True)
    groups = {str(i): torch.pow(2., m.clamp_min(2.**-24).log2().ceil()).cpu().tolist()
              for i, m in maxima.items()}
    write('results/sz_calibration.json', dict(
        source='first8192 WT2 train tokens; original teacher states; no stochastic noise or fitting to test',
        z_path='INT8 gate/up on fixed N12 input, exact SiLU*up; also covers quantized-g/u ablation',
        group=64, bits=12, calibration_tokens=8192,
        input_sha256=hashlib.sha256(ids.numpy().tobytes()).hexdigest(),
        old_calibration_sha256=sha('results/calibration.json'),
        fixed_group=groups, fixed_layer={i: [max(v)] for i, v in groups.items()},
        observed_maxima={str(i): v.cpu().tolist() for i, v in maxima.items()},
        scale_ratio_old_over_sz={i: [a*b/c for a,b,c in zip(old[i]['g'], old[i]['u'], v)]
                                for i,v in groups.items()}))
    write('results/suite.json', suite())


class SzFFN(StochasticMatrixFFN):
    def __init__(self, *args, variant, backend, sz, **kwargs):
        super().__init__(*args, **kwargs)
        self.variant, self.backend = variant, backend
        scale = torch.tensor(sz, device=self.gu_decoded.device, dtype=torch.float32)
        scale = scale.expand(self.width) if scale.numel() == 1 else scale.repeat_interleave(64)
        assert scale.shape == (self.width,) and bool((scale > 0).all())
        self.register_buffer('scale_z', scale.clone())
        self.register_buffer('z_stats', torch.zeros(5, device=scale.device, dtype=torch.float64))

    def _count_projection(self, counts, sign, input_scale, name, generator, stochastic_weight):
        if self.backend == 'gaussian' or not stochastic_weight:
            return super()._count_projection(counts, sign, input_scale, name, generator, stochastic_weight)
        # Exact distribution conditional on shared input counts, independent weights.
        # Only temporal order is compressed; no Gaussian approximation or literal T loop.
        shape = counts.shape
        n = counts.reshape(-1, shape[-1])
        coeff = (sign * input_scale).expand_as(counts).reshape_as(n)
        w = getattr(self, name + '_decoded')
        codes = getattr(self, name + '_codes')
        scales = getattr(self, name + '_tile_scales').repeat_interleave(64, 0).repeat_interleave(64, 1)
        out = torch.empty((n.shape[0], w.shape[0]), device=w.device)
        for t in range(0, n.shape[0], 16):
            for o in range(0, w.shape[0], 32):
                pw = codes[o:o+32].abs().float() / 127.
                cnt = n[t:t+16, None, :].expand(-1, pw.shape[0], -1)
                events = torch.binomial(cnt, pw[None].expand_as(cnt), generator=generator)
                amplitude = scales[o:o+32] * 127. * codes[o:o+32].sign()
                out[t:t+16, o:o+32] = (events * coeff[t:t+16, None, :] * amplitude[None]).sum(-1) / self.cycles
        return out.reshape(*shape[:-1], w.shape[0])

    def forward(self, x):
        if self.variant == 'legacy':
            return super().forward(x)
        self.calls += 1
        px, _ = encode_fixed(x.float(), self.scale_x, self.bits)
        counts = sample_counts(px, self.cycles, self.rng_input)
        gu = self._count_projection(counts, x.sign(), self.scale_x, 'gu', self.rng_weight_gu, True)
        g, u = gu.chunk(2, -1)
        if self.variant == 'sz_matched_gu':
            _, g = encode_fixed(g, self.scale_g, self.bits)
            _, u = encode_fixed(u, self.scale_u, self.bits)
        z = F.silu(g) * u
        scale = self.scale_z
        if self.variant == 'sz_dynamic':
            shape = z.shape
            scale = z.abs().reshape(*shape[:-1], self.width//64, 64).amax(-1, keepdim=True)
            scale = torch.pow(2., scale.clamp_min(2.**-24).log2().ceil()).expand(*shape[:-1], self.width//64, 64).reshape(shape)
        pz, zq = encode_fixed(z, scale, self.bits)
        zcounts = sample_counts(pz, self.cycles, self.rng_product)
        y = self._count_projection(zcounts, z.sign(), scale, 'down', self.rng_weight_down, True)
        self.z_stats[0] += z.numel()
        self.z_stats[1] += (z.abs() >= scale).sum()
        self.z_stats[2] += pz.sum(dtype=torch.float64)
        self.z_stats[3] += (zq-z).square().sum(dtype=torch.float64)
        self.z_stats[4] += z.square().sum(dtype=torch.float64)
        return y.to(x.dtype)

    def diagnostics(self):
        if self.variant == 'legacy':
            d = super().diagnostics()
        else:
            n, clipped, psum, err, power = self.z_stats.tolist()
            d = dict(calls=self.calls, z_values=int(n), z_clip_fraction=clipped/max(n,1),
                     z_mean_probability=psum/max(n,1), z_events_per_T=psum*self.cycles/max(n,1),
                     z_encoding_nmse=err/max(power,1e-30),
                     z_fixed_scale_min=self.scale_z.min().item(), z_fixed_scale_max=self.scale_z.max().item())
        d.update(variant=self.variant, weight_count_backend=self.backend)
        return d


def evaluate(index):
    cfg = suite()[index]
    cal = json.loads(Path('results/sz_calibration.json').read_text())
    import evaluate as historical
    def factory(*args, **kwargs):
        layer = args[6]
        sz = cal['fixed_layer' if cfg['variant']=='sz_layer' else 'fixed_group'][str(layer)]
        return SzFFN(*args, **kwargs, variant=cfg['variant'], backend=cfg['backend'], sz=sz)
    historical.StochasticMatrixFFN = factory
    name = f"{cfg['variant']}_T{cfg['cycles']}_s{cfg['seed']}_{cfg['backend']}_{cfg['split']}"
    out = Path('results/runs') / (name + '.json')
    sys.argv = ['evaluate.py', '--mode', 'baseline' if cfg['variant']=='baseline' else 'dual_exact',
                '--cycles', str(cfg['cycles']), '--seed', str(cfg['seed']), '--bits', '12',
                '--split', cfg['split'], '--max-tokens', str(cfg['max_tokens']), '--output', str(out)]
    historical.main()
    result = json.loads(out.read_text())
    result.update(configuration=cfg, slurm_job_id=os.environ.get('SLURM_JOB_ID'),
                  sz_calibration_sha256=sha('results/sz_calibration.json'))
    result['source_sha256']['run_sz.py'] = sha('run_sz.py')
    result['ffn_activation'] = ('original BF16 SiLU*up' if cfg['variant']=='baseline' else
        'historical quantized-g/u Bernoulli triple product' if cfg['variant']=='legacy' else
        'exact SiLU(g)*u followed by a new N12 magnitude encoding using Sz; no triple AND')
    result['dual_note'] = ('exact conditional binomial per connection; shared input counts' if cfg['backend']=='binomial'
                            else 'conditional Gaussian approximation; exact conditional mean/variance, not bit-exact')
    result['or_note'] = 'No OR approximation in this experiment'
    write(out, result)


def summarize():
    rows = []
    for path in sorted(Path('results/runs').glob('*.json')):
        d = json.loads(path.read_text())
        if 'configuration' not in d:
            continue
        rows.append(dict(file=str(path), **d['configuration'], ppl=d['perplexity'],
                         scored_tokens=d['scored_tokens'], seconds=d['seconds']))
    write('results/summary.json', rows)
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    os.chdir(ROOT)
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['calibrate', 'evaluate', 'summarize'])
    parser.add_argument('--index', type=int, default=0)
    a = parser.parse_args()
    if a.action == 'calibrate': calibrate()
    elif a.action == 'evaluate': evaluate(a.index)
    else: summarize()
