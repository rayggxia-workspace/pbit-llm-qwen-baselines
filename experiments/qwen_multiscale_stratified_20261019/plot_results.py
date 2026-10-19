"""Plot only measured groups from the multiscale/stratified comparison JSON.

Example:
    python plot_results.py --comparison COMPARISON.json --output COMPARISON.png

No missing observation is interpolated or replaced by an estimate. The figure
compares perplexity only; it does not estimate hardware energy or runtime.
"""
import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


COLORS = {'iid': '#C56A2D', 'fine': '#2674A7', 'pot2': '#2674A7', 'pot4': '#8C4F94'}


def measured(group):
    """Return an actual mean/std pair, or None for an absent observation."""
    if not isinstance(group, dict):
        return None
    mean = group.get('ppl_mean')
    std = group.get('ppl_population_std')
    if mean is None or std is None or group.get('completed', 1) == 0:
        return None
    mean, std = float(mean), float(std)
    if not math.isfinite(mean) or not math.isfinite(std) or mean <= 0 or std < 0:
        raise ValueError('Invalid measured PPL mean/std: ' + str((mean, std)))
    return mean, std


def add_curve(ax, observations, label, color, marker):
    points = []
    for x, group in observations:
        stats = measured(group)
        if stats is not None:
            points.append((float(x), stats[0], stats[1]))
    if not points:
        return
    points.sort()
    x, means, errors = zip(*points)
    ax.errorbar(x, means, yerr=errors, label=label, color=color, marker=marker,
                markersize=5.3, linewidth=1.6, elinewidth=1.15, capsize=3.5,
                capthick=1.15, zorder=3)


def groups_for(data, section, policy):
    entry = next((row for row in data.get(section, [])
                  if row.get('policy') == policy), None)
    return entry.get('groups', []) if entry else []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison', type=Path, required=True,
                        help='Measured COMPARISON.json produced by the result collector')
    parser.add_argument('--output', type=Path, required=True, help='Output PNG path')
    args = parser.parse_args()
    if args.output.suffix.lower() != '.png':
        parser.error('--output must have a .png extension')
    data = json.loads(args.comparison.read_text(encoding='utf-8'))
    bf16 = float(data['bf16'])
    if not math.isfinite(bf16) or bf16 <= 0:
        raise ValueError('BF16 reference must be a positive measured PPL')
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.titlesize': 11.5, 'axes.labelsize': 10.5,
                         'legend.fontsize': 8.8, 'axes.spines.top': False,
                         'axes.spines.right': False, 'figure.facecolor': 'white'})
    fig, axes = plt.subplots(1, 3, figsize=(15.7, 4.8))
    fig.subplots_adjust(left=.055, right=.985, bottom=.24, top=.79, wspace=.29)
    fig.suptitle('Multiscale encoding and random stratification', y=.965,
                 fontsize=16, fontweight='semibold')
    fig.text(.5, .89, 'Qwen2.5-0.5B | all 24 FFNs replaced | fixed INT8 weights | original attention',
             ha='center', fontsize=10.5, color='#3F4851')

    # A: same T and fixed W; only scale count and sampling strategy vary.
    entries = {entry['policy']: entry for entry in data.get('bins64', [])}
    for key, label, color, marker in (
            ('iid', 'IID (K = 1)', COLORS['iid'], 'o'),
            ('fine', 'Fine strata (K = 64)', COLORS['fine'], 's')):
        add_curve(axes[0], [(bins, entries.get('pot' + str(bins), {}).get(key))
                            for bins in (1, 2, 3, 4, 6, 8)], label, color, marker)
    axes[0].set_title('A  Scale bins at T = 64', loc='left', pad=12)
    axes[0].set_xlabel('Amplitude scale bins B')
    axes[0].set_xticks([1, 2, 3, 4, 6, 8])

    # B: same total sample count; K controls strata coverage, not array cycles.
    for policy, label, marker in (('pot2', 'B = 2', 'o'), ('pot4', 'B = 4', 's')):
        observations = [(group.get('strata', 1), group)
                        for group in groups_for(data, 'coarse64', policy)
                        if group.get('strata', 1) in (1, 4, 16, 64)
                        and group.get('cycles') == 64]
        add_curve(axes[1], observations, label, COLORS[policy], marker)
    axes[1].set_title('B  Coarse to fine strata at T = 64', loc='left', pad=12)
    axes[1].set_xlabel('Sampling strata K')
    axes[1].set_xscale('log', base=2)
    axes[1].set_xticks([1, 4, 16, 64], ['1 (IID)', '4', '16', '64'])

    # C: only actual fine-stratified points are shown. In particular, B2/T128
    # remains absent if it was not measured, rather than inheriting B4 results.
    for policy, label, marker in (('pot2', 'B = 2', 'o'), ('pot4', 'B = 4', 's')):
        observations = [(group['cycles'], group)
                        for group in groups_for(data, 'fine_lengths', policy)
                        if group.get('cycles') in (16, 32, 64, 128)
                        and group.get('strata') == group.get('cycles')]
        add_curve(axes[2], observations, label, COLORS[policy], marker)
    axes[2].set_title('C  Shorter streams with fine strata', loc='left', pad=12)
    axes[2].set_xlabel('Total samples T (K = T)')
    axes[2].set_xscale('log', base=2)
    axes[2].set_xticks([16, 32, 64, 128], ['16', '32', '64', '128'])

    for ax in axes:
        ax.axhline(bf16, color='#60666C', linestyle=(0, (4, 3)), linewidth=1.2,
                   label='BF16: ' + format(bf16, '.3f'), zorder=2)
        ax.set_ylabel('Perplexity (lower is better)')
        ax.grid(axis='y', alpha=.20, linewidth=.7, zorder=0)
        ax.margins(x=.08, y=.13)
        ax.legend(loc='best', frameon=True, framealpha=.94, edgecolor='#D9DDE1')
    protocol = data.get('protocol', {})
    targets = protocol.get('targets')
    protocol_label = ('Full WikiText-2: ' + format(int(targets), ',') + ' scored targets'
                      if targets is not None else 'Full WikiText-2')
    fig.text(.055, .115, protocol_label +
             ' | Mean +/- population std over measured seeds (error bars may be small).',
             ha='left', fontsize=9.2, color='#3F4851')
    fig.text(.055, .067,
             'B: amplitude scale count. K: equal sampling strata. Missing points are not drawn. '
             'Perplexity comparison only; no hardware energy claim.',
             ha='left', fontsize=9.2, color='#3F4851')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=200, facecolor='white')
    plt.close(fig)
    print(str(args.output.resolve()))


if __name__ == '__main__':
    main()
