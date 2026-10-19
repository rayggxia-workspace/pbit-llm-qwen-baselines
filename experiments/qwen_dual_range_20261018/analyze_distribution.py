"""Teacher-only range distribution audit; no sampled FFN or clipping PPL claim.

Inputs are the same hash-gated model/corpora/frozen calibrations as Issue32.
All counters stay on the tensor device until the final compact JSON export.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import torch
from torch.nn import functional as F

from run_ranges import (ROOT, OLD, calibration, digest, expand_scale,
                        load_model, score, test_ids, verify, write_json)
from range_core import encode_input, make_matrix_spec

A_BINS = ((0, 0), (1, 3), (4, 15), (16, 63), (64, 127), (128, 255))
W_BINS = ('p=0', '0<p<=1/64', '1/64<p<=1/16', '1/16<p<=1/4',
          '1/4<p<=1/2', '1/2<p<=1')
CLIP_FACTORS = (1., .5, .25, .125)


def activation_measure(value, probability, decoded, scale):
    """Sufficient statistics, including actual q=255 reconstruction limit."""
    value = value.float()
    q = (probability * 256).round().to(torch.int64)
    histogram = torch.bincount(q.reshape(-1), minlength=256)
    maximum = scale * (255. / 256.)
    clipped = value.abs() > maximum
    limited = value.sign() * torch.minimum(value.abs(), maximum)
    stats = torch.stack((probability.sum(dtype=torch.float64),
        (decoded-value).square().sum(dtype=torch.float64),
        value.square().sum(dtype=torch.float64),
        clipped.sum().to(torch.float64),
        (value.square() * clipped).sum(dtype=torch.float64),
        (limited-value).square().sum(dtype=torch.float64)))
    return histogram, stats


def probability_measure(probability):
    """Probability bins work for legacy |code|/127 and new q/256 alike."""
    boundaries = probability.new_tensor((0., 1/64, 1/16, 1/4, 1/2, 1.))
    indices = torch.bucketize(probability.reshape(-1).contiguous(), boundaries,
                              right=False)
    # finite inputs and probability <=1 are guaranteed by matrix encoding.
    histogram = torch.bincount(indices, minlength=6)
    return histogram, probability.sum(dtype=torch.float64).reshape(1)


class Accumulator:
    def __init__(self, histogram, stats):
        self.histogram = torch.zeros_like(histogram)
        self.stats = torch.zeros_like(stats)

    def add(self, histogram, stats):
        self.histogram += histogram
        self.stats += stats

    def export(self, activation=True):
        histogram = self.histogram.cpu().tolist()
        stats = self.stats.cpu().tolist()
        count = sum(histogram)
        if not count:
            raise ValueError('No values observed')
        if not activation:
            return dict(values=count, mean_probability=stats[0]/count,
                        bins=[dict(bin=label, count=n, fraction=n/count)
                              for label, n in zip(W_BINS, histogram)])
        probability_sum, error, power, clipped, clipped_power, clip_error = stats
        bins = [dict(bin=f'{lo}' if lo == hi else f'{lo}..{hi}',
                     count=sum(histogram[lo:hi+1]),
                     fraction=sum(histogram[lo:hi+1])/count)
                for lo, hi in A_BINS]
        quantiles = {}
        for percentile in (50, 90, 99, 99.9, 100):
            threshold = percentile * count / 100
            cumulative = 0
            for q, n in enumerate(histogram):
                cumulative += n
                if cumulative >= threshold:
                    quantiles[str(percentile)] = q
                    break
        return dict(values=count, mean_probability=probability_sum/count,
            mean_magnitude_code=256*probability_sum/count,
            zero_code_fraction=histogram[0]/count, magnitude_code_quantiles=quantiles,
            bins=bins, signal_energy=power, encoding_error_energy=error,
            encoding_nmse=error/max(power, 1e-30),
            clipping_fraction=clipped/count,
            clipped_value_energy_fraction=clipped_power/max(power, 1e-30),
            clipping_sse_over_signal_energy=clip_error/max(power, 1e-30))


def add_measure(table, key, measured):
    if key not in table:
        table[key] = Accumulator(*measured)
    table[key].add(*measured)


def checked_output(args):
    project = Path(args.project_root).resolve(strict=True)
    output = Path(args.output).resolve()
    snapshot = ROOT.parents[1]
    if project not in output.parents or output == snapshot or snapshot in output.parents:
        raise ValueError('New output must be inside personal project and outside source snapshot')
    if output.exists():
        raise FileExistsError('Use a fresh output directory; do not overwrite an execution')
    output.mkdir(parents=True)
    return output


def audit(args):
    import transformers
    output = checked_output(args)
    configuration = dict(tokens=args.tokens, context=args.context,
        activation_policies=['legacy', 'dynamic64'], weight_policies=['legacy', 'row64'],
        clipping_factors=list(CLIP_FACTORS), clipping_scope='legacy activation scales only',
        source='Unmodified BF16 teacher; nonoverlapping train-prefix windows',
        no_sampling=True, no_training=True, no_raw_activations_saved=True)
    identity = verify(args.model, args.data, output/'identity.json')
    identity.update(distribution_execution_commit=args.code_commit,
        configuration=configuration,
        configuration_sha256=hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest(),
        distribution_source_sha256={p.name:digest(p) for p in sorted(ROOT.iterdir())
                                    if p.is_file() and p.suffix in ('.py', '.md', '.sbatch')},
        environment=dict(torch=torch.__version__, transformers=transformers.__version__,
            cuda=torch.version.cuda, gpu=torch.cuda.get_device_name(), python=sys.version),
        command=sys.argv, slurm_job_id=os.environ.get('SLURM_JOB_ID'),
        created_utc=datetime.now(timezone.utc).isoformat())
    write_json(output/'identity.json', identity)
    tokenizer, model = load_model(args)
    ids = test_ids(args, tokenizer, identity)
    baseline = score(model, ids, True)
    passed = (baseline['scored_tokens'] == 299077
              and abs(baseline['perplexity']-11.652735047455899) < .02)
    write_json(output/'BF16reference.json', dict(baseline,
        protocol='full_WT2_sliding_window', context=2048, stride=1024,
        baseline_gate_passed=passed, code_commit=args.code_commit,
        identity_sha256=digest(output/'identity.json')))
    if not passed:
        raise ValueError('Unmodified BF16 reference gate failed')
    train_ids = tokenizer((Path(args.data)/'wiki.train.raw').read_text(encoding='utf-8'),
        add_special_tokens=False, return_tensors='pt').input_ids[:, :args.tokens]
    if train_ids.shape[-1] != args.tokens:
        raise ValueError('Train prefix too short')
    a_cal, z_cal = calibration()
    activation, weights, clipping = {}, {}, {}
    totals_a, totals_w, totals_c = {}, {}, {}
    handles = []
    for index, layer in enumerate(model.model.layers):
        def inspect(module, inputs, index=index):
            x = inputs[0].detach()
            # Match original BF16 gate/up, SiLU and multiplication order.
            z = F.silu(module.gate_proj(x)) * module.up_proj(x)
            for stage, value, fixed in (('x', x.float(), a_cal[str(index)]['x']),
                                       ('z', z.float(), z_cal[str(index)])):
                scale = expand_scale(fixed, value.shape[-1], value.device)
                for policy in ('legacy', 'dynamic64'):
                    p, decoded, used_scale = encode_input(value, scale, policy)
                    measured = activation_measure(value, p, decoded, used_scale)
                    add_measure(activation, (index, stage, policy), measured)
                    add_measure(totals_a, (stage, policy), measured)
                for factor in CLIP_FACTORS:
                    p, decoded, used_scale = encode_input(value, scale*factor, 'legacy')
                    measured = activation_measure(value, p, decoded, used_scale)
                    add_measure(clipping, (index, stage, factor), measured)
                    add_measure(totals_c, (stage, factor), measured)
        handles.append(layer.mlp.register_forward_pre_hook(inspect))
    try:
        with torch.inference_mode():
            for begin in range(0, args.tokens, args.context):
                # Backbone omits unused lm_head/logits and preserves every decoder operation.
                model.model(input_ids=train_ids[:, begin:begin+args.context].cuda(), use_cache=False)
                print(json.dumps(dict(event='distribution_window', tokens=begin+args.context)), flush=True)
    finally:
        for handle in handles:
            handle.remove()
    with torch.inference_mode():
        for index, layer in enumerate(model.model.layers):
            for projection in ('gate', 'up', 'down'):
                weight = getattr(layer.mlp, projection+'_proj').weight
                for policy in ('legacy', 'row64'):
                    spec = make_matrix_spec(weight, policy)
                    measured = probability_measure(spec.probability)
                    add_measure(weights, (index, projection, policy), measured)
                    add_measure(totals_w, (projection, policy), measured)
                print(json.dumps(dict(event='distribution_weight', layer=index,
                                      projection=projection)), flush=True)
    result = dict(configuration=configuration, code_commit=args.code_commit,
        identity_sha256=digest(output/'identity.json'),
        bf16_reference_sha256=digest(output/'BF16reference.json'),
        tokens_sha256=hashlib.sha256(train_ids.numpy().tobytes()).hexdigest(),
        activations=[dict(layer=k[0], stage=k[1], policy=k[2], **v.export())
                     for k,v in sorted(activation.items())],
        activation_totals=[dict(stage=k[0], policy=k[1], **v.export())
                           for k,v in sorted(totals_a.items())],
        weights=[dict(layer=k[0], projection=k[1], policy=k[2], **v.export(False))
                 for k,v in sorted(weights.items())],
        weight_totals=[dict(projection=k[0], policy=k[1], **v.export(False))
                       for k,v in sorted(totals_w.items())],
        clipping=[dict(layer=k[0], stage=k[1], scale_factor=k[2], **v.export())
                  for k,v in sorted(clipping.items())],
        clipping_totals=[dict(stage=k[0], scale_factor=k[1], **v.export())
                        for k,v in sorted(totals_c.items())],
        warning='Clipping sweep measures scalar encoding error only; no clipped-model PPL, sampled matrix variance, PPA or quality claim.')
    write_json(output/'distribution.json', result)
    print(json.dumps(dict(event='distribution_complete', output=str(output),
        distribution_sha256=digest(output/'distribution.json'))), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('model', 'data', 'project-root', 'output', 'code-commit'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--tokens', type=int, default=8192)
    parser.add_argument('--context', type=int, default=2048)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.code_commit):
        parser.error('Exact 40-character execution commit required')
    if args.context != 2048 or not 0 < args.tokens <= 8192 or args.tokens % args.context:
        parser.error('Context must be 2048; tokens must be a positive multiple of 2048, <=8192')
    audit(args)


if __name__ == '__main__':
    main()
