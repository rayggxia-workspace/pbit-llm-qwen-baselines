"""Exact IID categorical occupancy from real vectors; no PPL estimation."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

COUNTS = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384]
GROUPS = [1, 4, 8, 16, 64]
SIGNALS = ['x_raw', 'x_p8mean', 'z_p8mean', 'z_sample']


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def probabilities(value, norm=None):
    score = np.abs(np.asarray(value, dtype=np.float64))
    if norm is not None:
        norm = np.asarray(norm, dtype=np.float64)
        if norm.ndim != 1 or norm.shape[0] != score.shape[-1] or (norm < 0).any():
            raise ValueError('weight norms must match the input dimension')
        score = score * norm
    if not np.isfinite(score).all():
        raise ValueError('nonfinite sampling score')
    total = score.sum(axis=-1, keepdims=True)
    valid = total[:, 0] > 0
    return score[valid] / total[valid], valid


def group_probabilities(p, group):
    if group < 1:
        raise ValueError('positive group size required')
    return np.add.reduceat(p, np.arange(0, p.shape[-1], group), axis=-1)


def hit_probability(p, count):
    if count < 0:
        raise ValueError('nonnegative draw count required')
    if count == 0:
        return np.zeros_like(p)
    if (p < 0).any() or (p > 1+1e-12).any():
        raise ValueError('invalid probabilities')
    with np.errstate(divide='ignore'):
        return -np.expm1(count * np.log1p(-np.minimum(p, 1)))


def occupancy(p, count, group=1):
    """Return expected unique units, fetched-row ratio, and covered probability mass.

    Groups are a CONDITIONAL layout scenario: every hit fetches all adjacent
    input rows in that group, not a claim about current DMA transactions.
    """
    p = np.asarray(p, dtype=np.float64)
    n = p.shape[-1]
    mass = group_probabilities(p, group)
    hit = hit_probability(mass, count)
    sizes = np.minimum(group, n-np.arange(0, n, group))
    return hit.sum(-1), (hit*sizes).sum(-1)/n, (hit*mass).sum(-1)


def stats(a):
    return dict(mean=float(np.mean(a)), p10=float(np.quantile(a, .1)),
                median=float(np.median(a)), p90=float(np.quantile(a, .9)),
                minimum=float(np.min(a)), maximum=float(np.max(a)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--capture', type=Path, required=True)
    ap.add_argument('--capture-result', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    meta = json.loads(args.capture_result.read_bytes())
    assert meta['status'] == 'completed' and meta['no_op_all_window_logits_bitwise_equal']
    assert sha(args.capture) == meta['capture_sha256']
    assert sorted(meta['layers']) == list(range(36))
    data = np.load(args.capture, allow_pickle=False)
    all_rows, layer_rows, sample_checks, distributions = [], [], [], []
    for signal in SIGNALS:
        n = 2560 if signal.startswith('x_') else 9728
        norm_name = 'norm_gu' if signal.startswith('x_') else 'norm_wd'
        for law in ['abs', 'abs_weight_norm']:
            ps, labels = [], []
            for layer in range(36):
                tag = 'L%02d_' % layer
                v = data[tag+signal]
                assert v.shape == (len(meta['positions']), n)
                norm = None if law == 'abs' else data[tag+norm_name]
                p, valid = probabilities(v, norm)
                ps.append(p)
                labels += [(layer, j) for j in np.flatnonzero(valid)]
            p = np.concatenate(ps)
            labels = np.array(labels)
            distributions.append(dict(signal=signal, law=law, n=n, vectors=len(p),
                positive_support=stats((p>0).sum(-1)),
                effective_support=stats(1/np.square(p).sum(-1))))
            for count in COUNTS:
                for group in GROUPS:
                    unique, ratio, mass = occupancy(p, count, group)
                    row = dict(signal=signal, law=law, n=n, draws=count, group=group,
                               vectors=len(p), unique_mean=float(unique.mean()),
                               mass_mean=float(mass.mean()))
                    row.update({'coverage_'+k:v for k,v in stats(ratio).items()})
                    all_rows.append(row)
                    for layer in range(36):
                        a = labels[:, 0] == layer
                        if a.any():
                            layer_rows.append(dict(signal=signal, law=law, layer=layer,
                                n=n, draws=count, group=group,
                                unique_mean=float(unique[a].mean()),
                                coverage_mean=float(ratio[a].mean())))
            # Observations only validate the exact occupancy calculation. All
            # headline expectations use all 576 real vectors, not this subset.
            for seed in [17, 503, 1009]:
                rng = np.random.default_rng(seed)
                observed = {k:[] for k in COUNTS}
                expected = {k:[] for k in COUNTS}
                for j, prob in enumerate(p):
                    if int(labels[j, 0]) not in [0, 17, 35]:
                        continue
                    draws = rng.choice(n, max(COUNTS), p=prob)
                    first = np.full(n, max(COUNTS)+1, dtype=np.int64)
                    np.minimum.at(first, draws, np.arange(1, len(draws)+1))
                    for count in COUNTS:
                        observed[count].append(float((first <= count).sum())/n)
                        expected[count].append(float(occupancy(prob[None], count)[1][0]))
                for count in COUNTS:
                    sample_checks.append(dict(signal=signal, law=law, seed=seed,
                        draws=count, vectors=len(observed[count]),
                        observed_mean=float(np.mean(observed[count])),
                        expected_matching_subset_mean=float(np.mean(expected[count]))))

    def write_csv(name, rows):
        with (args.out/name).open('w', encoding='utf-8', newline='') as f:
            w=csv.DictWriter(f, fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write_csv('COVERAGE.csv', all_rows)
    write_csv('PER_LAYER.csv', layer_rows)
    write_csv('MC_THREE_SEEDS.csv', sample_checks)
    report = dict(status='completed', date='2026-11-22',
        sampler='IID categorical with replacement, whole-vector address budget',
        formula='E[unique]=sum_i(1-(1-p_i)^K)',
        laws=['p proportional to abs(input)', 'p proportional to abs(input)*decoded_weight_row_norm'],
        gu_norm='sqrt(sum_outputs(Wg^2+Wu^2)), frozen W8 with actual PoT scales',
        wd_norm='sqrt(sum_outputs(Wd^2)), frozen W8 with actual PoT scales',
        counts=COUNTS, groups=GROUPS, distributions=distributions,
        rows=all_rows, capture=meta,
        provenance=dict(capture_path=str(args.capture), capture_sha256=sha(args.capture),
            capture_result_path=str(args.capture_result), capture_result_sha256=sha(args.capture_result),
            analysis_code_sha256=sha(__file__)),
        scope='One real WT2 window, all36 layers x16 positions; no PPL/accuracy '
              'or native GF64/Ising-address distribution claim. Grouped transfer '
              'is an explicit hypothetical input-row grouping, not measured DMA traffic.')
    report['artifacts']={p.name:sha(p) for p in args.out.glob('*.csv')}
    (args.out/'RESULTS.json').write_bytes((json.dumps(report, indent=2)+'\n').encode())
    print(json.dumps(dict(status='completed', rows=len(all_rows), vectors_per_signal=576)), flush=True)


if __name__ == '__main__':
    main()
