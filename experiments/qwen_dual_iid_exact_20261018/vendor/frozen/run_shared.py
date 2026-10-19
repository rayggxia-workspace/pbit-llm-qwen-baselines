"""Matched input-PRNG sharing study; frozen Sz scales; original attention."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import torch
from torch.nn import functional as F
from core import encode_fixed, sample_counts
from run_sz import SzFFN, sha, write
from shared_counts import shared_counts

ROOT = Path(__file__).resolve().parent


def suite():
    configs = [dict(weight='baseline', bits=16, sharing=0, cycles=4096, seed=0)]
    for weight in ('fixed', 'dual'):
        configs.append(dict(weight=weight, bits=12, sharing=1, cycles=4096, seed=0))
        for sharing in (1, 64):
            for seed in range(3):
                configs.append(dict(weight=weight, bits=8, sharing=sharing, cycles=4096, seed=seed))
        for cycles in (256, 1024):
            configs.append(dict(weight=weight, bits=8, sharing=64, cycles=cycles, seed=0))
    return configs


class SharedFFN(SzFFN):
    def __init__(self, *args, sharing, weight, **kwargs):
        super().__init__(*args, **kwargs)
        self.sharing, self.weight = sharing, weight
        self.register_buffer('input_stats', torch.zeros(5, device=self.scale_z.device, dtype=torch.float64))

    def counts(self, p, generator):
        if self.sharing == 1:
            return sample_counts(p, self.cycles, generator)
        return shared_counts(p, self.cycles, generator, self.sharing)

    def forward(self, x):
        self.calls += 1
        xf = x.float()
        px, xq = encode_fixed(xf, self.scale_x, self.bits)
        counts = self.counts(px, self.rng_input)
        stochastic_weight = self.weight == 'dual'
        gu = self._count_projection(counts, xf.sign(), self.scale_x, 'gu',
                                    self.rng_weight_gu, stochastic_weight)
        g, u = gu.chunk(2, -1)
        z = F.silu(g) * u
        pz, zq = encode_fixed(z, self.scale_z, self.bits)
        zcounts = self.counts(pz, self.rng_product)
        y = self._count_projection(zcounts, z.sign(), self.scale_z, 'down',
                                   self.rng_weight_down, stochastic_weight)
        self.input_stats[0] += xf.numel()
        self.input_stats[1] += (px == 0).sum()
        self.input_stats[2] += px.sum(dtype=torch.float64)
        self.input_stats[3] += (xq-xf).square().sum(dtype=torch.float64)
        self.input_stats[4] += xf.square().sum(dtype=torch.float64)
        self.z_stats[0] += z.numel()
        self.z_stats[1] += (z.abs() >= self.scale_z).sum()
        self.z_stats[2] += pz.sum(dtype=torch.float64)
        self.z_stats[3] += (zq-z).square().sum(dtype=torch.float64)
        self.z_stats[4] += z.square().sum(dtype=torch.float64)
        return y.to(x.dtype)

    def diagnostics(self):
        d = super().diagnostics()
        n, zeros, psum, err, power = self.input_stats.tolist()
        d.update(sharing=self.sharing, weight=self.weight, bits=self.bits,
                 x_zero_fraction=zeros/max(n, 1), x_mean_probability=psum/max(n, 1),
                 x_encoding_nmse=err/max(power, 1e-30))
        return d


def evaluate(index, max_tokens=0, backend='gaussian', preflight=False):
    cfg = dict(suite()[index], backend=backend, split='test', max_tokens=max_tokens)
    cal = json.loads(Path('results/sz_calibration.json').read_text())
    import evaluate as historical
    def factory(*args, **kwargs):
        return SharedFFN(*args, **kwargs, variant='sz_group', backend=backend,
                         sz=cal['fixed_group'][str(args[6])], sharing=cfg['sharing'], weight=cfg['weight'])
    historical.StochasticMatrixFFN = factory
    name = f"{cfg['weight']}_A{cfg['bits']}_share{cfg['sharing']}_T{cfg['cycles']}_s{cfg['seed']}_{backend}"
    folder = 'preflight' if preflight else 'runs'
    out = Path('results') / folder / (name + (f'_n{max_tokens}' if max_tokens else '') + '.json')
    mode = 'baseline' if cfg['weight']=='baseline' else 'fixed_exact' if cfg['weight']=='fixed' else 'dual_exact'
    sys.argv = ['evaluate.py', '--mode', mode, '--cycles', str(cfg['cycles']),
                '--seed', str(cfg['seed']), '--bits', str(cfg['bits']), '--split', 'test',
                '--max-tokens', str(max_tokens), '--output', str(out)]
    historical.main()
    result = json.loads(out.read_text())
    result.update(configuration=cfg, slurm_job_id=os.environ.get('SLURM_JOB_ID'),
                  sz_calibration_sha256=sha('results/sz_calibration.json'))
    for f in ('run_shared.py', 'shared_counts.py', 'run_sz.py'):
        result['source_sha256'][f] = sha(f)
    result['ffn_activation'] = ('original BF16 SiLU*up' if cfg['weight']=='baseline' else
        f"exact SiLU(g)*u then A{cfg['bits']} magnitude encoding with fixed per-64-channel Sz")
    result['input_sharing_note'] = (
        'IID uniform comparator word shared by 64 contiguous inputs, independently per token/group/layer/stage; '
        'exact joint multinomial input count law; same count vector feeds all outputs and gate/up; '
        'input and weight random streams independent' if cfg['sharing']==64 else 'independent input lanes')
    result['dual_note'] = ('not used; fixed INT8 weights and exact spatial/time accumulation' if cfg['weight']!='dual'
        else 'independent weight stream per connection; conditional Gaussian residual approximation'
        if backend=='gaussian' else 'exact conditional binomial weight counts per connection')
    result['or_note'] = 'No OR, no mutual-exclusion remapping; exact spatial addition'
    result['stages'] = 'T input samples for gate/up, exact SiLU*up, T newly encoded z samples for down'
    write(out, result)


def summarize():
    rows = []
    for path in sorted(Path('results/runs').glob('*.json')):
        d = json.loads(path.read_text())
        if 'configuration' in d:
            rows.append(dict(file=str(path), **d['configuration'], ppl=d['perplexity'],
                             scored_tokens=d['scored_tokens'], seconds=d['seconds']))
    write('results/summary.json', rows)
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    os.chdir(ROOT)
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['evaluate', 'summarize', 'suite'])
    parser.add_argument('--index', type=int, default=0)
    parser.add_argument('--max-tokens', type=int, default=0)
    parser.add_argument('--backend', choices=['gaussian', 'binomial'], default='gaussian')
    parser.add_argument('--preflight', action='store_true')
    a = parser.parse_args()
    if a.action == 'evaluate': evaluate(a.index, a.max_tokens, a.backend, a.preflight)
    elif a.action == 'suite': write('results/suite.json', suite())
    else: summarize()
