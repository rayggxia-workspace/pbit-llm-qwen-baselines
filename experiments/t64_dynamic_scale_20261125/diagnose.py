"""Fixed-tensor posterior diagnostics, not a PPL or physical-PPA experiment."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys


def moments(codes, samples, grid):
    """Exact mean/variance/P(C=0) for the independent within-cell count law."""
    import torch
    full = [q // (256 // n) for q, n in zip(codes, grid)]
    fraction = [(q % (256 // n)).double() / (256 // n) for q, n in zip(codes, grid)]
    repeats = samples // math.prod(grid)
    base = full[0] * full[1] * full[2] * repeats
    mean = base.double()
    var = torch.zeros_like(mean)
    log_zero = torch.zeros_like(mean)
    for partial in itertools.product((False, True), repeat=3):
        if not any(partial):
            continue
        trials = torch.full_like(base, repeats)
        p = torch.ones_like(mean)
        for i in range(3):
            if partial[i]:
                p = p * fraction[i]
            else:
                trials = trials * full[i]
        mean = mean + trials * p
        var = var + trials * p * (1 - p)
        log_zero = log_zero + torch.where(trials > 0, trials * torch.log1p(-p), 0.)
    pzero = torch.where(base > 0, 0., log_zero.exp())
    product = codes[0].double() * codes[1] * codes[2] / 256**3
    assert torch.allclose(mean, samples * product, atol=1e-12, rtol=1e-12)
    assert bool((pzero + 1e-12 >= (1 - mean).clamp_min(0)).all())
    return mean, var, pzero, base


def check_moments():
    import torch
    gen = torch.Generator().manual_seed(27)
    codes = [torch.randint(257, (37,), generator=gen) for _ in range(3)]
    for samples, grid in [(32, (4, 2, 4)), (128, (8, 2, 8))]:
        mu, var, zero, _ = moments(codes, samples, grid)
        probabilities = []
        for cell in itertools.product(*[range(n) for n in grid]):
            p = torch.ones(37, dtype=torch.float64)
            for i in range(3):
                p *= (codes[i].double() / (256 // grid[i]) - cell[i]).clamp(0, 1)
            probabilities.append(p)
        allp = torch.stack(probabilities)
        assert torch.allclose(mu, allp.sum(0))
        assert torch.allclose(var, (allp * (1 - allp)).sum(0))
        assert torch.allclose(zero, (1 - allp).prod(0))
    mu, var, zero, _ = moments([torch.tensor([32]), torch.tensor([128]), torch.tensor([32])], 32, (4, 2, 4))
    assert (mu.item(), var.item(), zero.item()) == (.25, .1875, .75)


def quantiles(x):
    import torch
    return dict(zip(['p10', 'p50', 'p90', 'p99'], torch.quantile(x.double().flatten(),
                    torch.tensor([.1, .5, .9, .99], device=x.device, dtype=torch.float64)).cpu().tolist()))


def scale(value, policy, top, cap):
    import torch
    if policy == 'lane4':
        return __import__('seven_forward').encode_p8(value, top)
    group = 64 if policy == 'max64' else 32 if policy == 'max32' else 16
    a = value.abs().reshape(value.shape[0], -1, group)
    maximum = a.amax(-1, keepdim=True)
    if policy == 'second16':
        maximum = a.topk(2, dim=-1).values[..., 1:2]
    mantissa, exp = torch.frexp(maximum)
    exp = torch.where(maximum == 0, -6, exp - (mantissa == .5).int())
    if policy == 'half16':
        exp = exp - 1
    exp = exp.clamp(-6, int(math.log2(cap)))
    e = exp.expand_as(a).reshape_as(value).long()
    if policy == 'correction1':
        base = torch.ldexp(torch.ones_like(value), e)
        e = torch.where(value.abs() <= base * .25, e - 2, e).clamp_min(-6)
    selected = torch.ldexp(torch.ones_like(value), e)
    q = (value.abs() / selected * 256).round().clamp(0, 255).long()
    q = torch.where((value.abs() >= selected) & (value != 0), 256, q)
    return q, value.sign().long(), e, int(math.log2(cap)) - e


def main():
    p = argparse.ArgumentParser()
    for key in ['assets', 'inputs', 'output']:
        p.add_argument('--' + key, type=Path, required=True)
    a = p.parse_args()
    assert __import__('os').environ.get('SLURM_JOB_ID') and not a.output.exists()
    a.output.mkdir()
    own = Path(__file__).parent
    manifest = json.loads((own / 'EXECUTION_MANIFEST.json').read_bytes())
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((own / name).read_bytes()).hexdigest() == digest, name
    sys.path.insert(0, str(a.assets / 'runtime'))
    import torch
    import numpy as np
    from reference import prepare, load_model
    from score_reference import save, snapshot
    from adapter import SamplingOverride
    from dynamic import DynamicOverride
    import seven_forward as sf
    check_moments()
    inputs, tokens, ledger, protocol = prepare(a.inputs, a.assets / 'runtime', a.output)
    model, context, modules, identity = load_model(inputs)
    case = dict(id='diagnostic', T_x=16, T_and=32, input_law='stratified_T', and_law='joint_grid', grid_g_sig_u=[4, 2, 4])
    patch = SamplingOverride(case)
    patch.configure(modules)
    selected = [0, 9, 18, 27, 35]
    positions = list(range(64, 2048, 128))
    captured = {}
    class Observer(DynamicOverride):
        def __init__(self):
            super().__init__(16)
            self.layer = -1
        def observe(self, name, value, q, e, selected_scale):
            if name == 'x':
                self.layer += 1
            if self.layer in selected and name in ('g', 'u'):
                captured.setdefault(self.layer, {})[name] = value.reshape(-1, value.shape[-1])[positions].clone()
    ids = torch.as_tensor(np.asarray(tokens[:2048], dtype=np.int64), device='cuda')[None]
    state = snapshot(modules)
    context.seed = 101
    with patch, torch.no_grad():
        context.begin(0, 0, domain='ffn-wt2-deployment')
        with DynamicOverride(16):
            expected = model(ids, use_cache=False, logits_to_keep=1).logits.detach().clone()
        context.begin(0, 0, domain='ffn-wt2-deployment')
        with Observer():
            observed = model(ids, use_cache=False, logits_to_keep=1).logits.detach().clone()
    assert torch.equal(expected, observed) and snapshot(modules) == state
    assert len(context.coverage) == 36 and set(captured) == set(selected)
    print('Captured five layers; observer last-token logits bitwise equality PASS', flush=True)
    raw = {str(i): {name: value.cpu() for name, value in pair.items()} for i, pair in captured.items()}
    torch.save(raw, a.output / 'ACTIVATIONS.pt')
    layers = []
    with torch.no_grad():
        for i in selected:
            g, u = captured[i]['g'], captured[i]['u']
            module = modules[i]
            wd = module.frozen_down_decoded.float()
            norm = wd.double().square().sum(0)
            reference = torch.nn.functional.linear(g * torch.sigmoid(g) * u, wd)
            power = float(reference.double().square().sum())
            stats = {}
            for name, value in [('g', g), ('u', u)]:
                v = value.abs().reshape(value.shape[0], -1, 16)
                maximum = v.amax(-1)
                median = v.median(-1).values
                rms = v.square().mean(-1).sqrt()
                tail = maximum / median.clamp_min(1e-30)
                stats[name] = dict(max_over_median=quantiles(tail), max_over_RMS=quantiles(maximum/rms.clamp_min(1e-30)),
                     groups_max_over_8_median=float((maximum>8*median).double().mean()),
                     groups_max_over_16_median=float((maximum>16*median).double().mean()),
                     top1_energy_fraction=quantiles(maximum.square()/v.square().sum(-1).clamp_min(1e-30)))
            results = []
            for policy in ['lane4', 'max64', 'max32', 'max16', 'second16', 'half16', 'correction1']:
                gq, gs, ge, _ = scale(g, policy, module.g_top, 256.)
                uq, us, ue, _ = scale(u, policy, module.u_top, 512.)
                sg = torch.ldexp(torch.ones_like(g), ge)
                su = torch.ldexp(torch.ones_like(u), ue)
                field = sf.sigmoid_field(gq, gs, ge)
                hq = module.lut[field + 128].long()
                factor = (gs*us).double()*sg.double()*su.double()
                zmean = factor*gq.double()*hq.double()*uq.double()/256**3
                bias = torch.nn.functional.linear(zmean.float(), wd)-reference
                bias2 = float(bias.double().square().sum())
                for samples, grid in [(32, (4, 2, 4)), (128, (8, 2, 8))]:
                    mean, variance, pzero, base = moments((gq, hq, uq), samples, grid)
                    noise = float((variance * factor.square() / samples**2 * norm[None]).sum())
                    results.append(dict(policy=policy,T_and=samples,signal_power=power,bias_power=bias2,
                        noise_power=noise,expected_NMSE=(bias2+noise)/power,
                        fraction_mean_count_below1=float((mean<1).double().mean()),
                        expected_zero_count_fraction=float(pzero.mean()),fraction_no_full_cell=float((base==0).double().mean()),
                        g_probability_mean=float(gq.double().mean()/256),u_probability_mean=float(uq.double().mean()/256),
                        g_clipped_fraction=float((g.abs()>sg).double().mean()),u_clipped_fraction=float((u.abs()>su).double().mean())))
            layers.append(dict(layer=i,outlier_statistics=stats,results=results))
            print('Analyzed layer '+str(i), flush=True)
    save(a.output/'RESULT.json',dict(status='completed',scope='one context/five layers/16 tokens per layer fixed-GU posterior diagnostics;not PPL',
         source=manifest,identity=identity,protocol=protocol,source_window=0,positions=positions,layers=layers,
         observer_logits_noop_bitwise=True,numeric_moments_tests=True,
         upstream='dynamic group16,GU16/Wd32',probability_model='independent within-cell/channels as frozen joint_counts',
         reference='floating SiLU and linear solely as diagnostic error reference;not candidate hardware path',
         raw_activations_sha256=hashlib.sha256((a.output/'ACTIVATIONS.pt').read_bytes()).hexdigest()))


if __name__ == '__main__':
    main()
