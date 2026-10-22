"""Measured windows only. No total/internal/clock double counting."""
import csv
import json
import math
from pathlib import Path
import re
import sys
from cell_report_parser import rows, unit_scales, NUM


def library_units(text):
    aliases = {'timeunit': 'time_s', 'timeunits': 'time_s'}
    aliases.update({x: 'capacitance_F' for x in
                    ('capacitanceunit', 'capacitanceunits', 'capacitiveloadunit', 'capacitiveloadunits')})
    factors = {
        'time_s': {'s': 1., 'second': 1., 'seconds': 1., 'ns': 1e-9, 'ps': 1e-12, 'us': 1e-6, 'fs': 1e-15},
        'capacitance_F': {'f': 1., 'farad': 1., 'farads': 1., 'pf': 1e-12, 'ff': 1e-15, 'nf': 1e-9}}
    found = {}
    for line in text.splitlines():
        pair = re.split(r'[:=]', line, maxsplit=1)
        if len(pair) != 2:
            continue
        kind = aliases.get(re.sub(r'[\s_]', '', pair[0]).lower())
        if kind is None:
            continue
        m = re.fullmatch(r'\s*('+NUM+r')\s*([A-Za-z]+)\s*', pair[1])
        if not m or m[2].lower() not in factors[kind]:
            raise ValueError('Unsupported library unit line: '+line)
        value = float(m[1]) * factors[kind][m[2].lower()]
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid library unit: '+line)
        if kind in found and not math.isclose(found[kind], value, rel_tol=1e-9, abs_tol=0):
            raise ValueError('Conflicting library units: '+line)
        found[kind] = value
    for kind, expected in (('time_s', 1e-9), ('capacitance_F', 1e-12)):
        if kind not in found or not math.isclose(found[kind], expected, rel_tol=1e-9, abs_tol=0):
            raise ValueError('Expected 1ns/1pF library units; {}={}; inspect units.rpt'.format(kind, found.get(kind)))
    return found


def totals(text):
    scales = unit_scales(text)
    values = []
    for label, scale in zip(('Cell Internal Power', 'Net Switching Power', 'Cell Leakage Power', 'Total Power'), scales):
        m = re.search(r'^\s*'+label+r'\s*=\s*('+NUM+')', text, re.M)
        if not m:
            raise ValueError('Missing '+label)
        values.append(float(m[1])*scale)
    if not all(math.isfinite(v) for v in values) or values[3] <= 0 or not math.isclose(sum(values[:3]), values[3], rel_tol=.02, abs_tol=1e-12):
        raise ValueError('Inconsistent total power')
    return values, scales


def coverage(text):
    result = {}
    for key, label in [('total_nets', 'Total number of nets'), ('annotated_nets', 'Number of annotated nets')]:
        m = re.search(re.escape(label)+r'\s*=\s*(\d+)', text)
        if not m:
            raise ValueError('Missing annotation statistic: '+label)
        result[key] = int(m[1])
    if not 0 < result['annotated_nets'] <= result['total_nets']:
        raise ValueError('Invalid/zero annotation')
    result['net_coverage_percent'] = 100.*result['annotated_nets']/result['total_nets']
    return result


def csvwrite(path, data):
    if not data:
        return
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)


def summarize(work, output=None):
    output = work if output is None else output
    data, parts = [], []
    for complete in sorted((work/'power').glob('*/*/POWER_CALCULATED')):
        pt = complete.parent
        name, label = pt.parent.name, pt.name
        sim = work/'gate'/name
        meta = json.loads((sim/'workload.json').read_text())
        win = next(w for w in meta['windows'] if w['label'] == label)
        audit = json.loads((sim/'wave_audit.json').read_text())[label]
        if audit['xz_signals']:
            raise ValueError('X/Z not waived')
        v, scales = totals((pt/'power.rpt').read_text())
        with (pt/'inventory.tsv').open() as f:
            inv = {r['name']: r for r in csv.DictReader(f, delimiter='\t')}
        groups, seen = {}, set()
        for cell, raw, flags in rows(pt/'cells.rpt'):
            if cell is None:
                if raw[0] != len(seen):
                    raise ValueError('Cell count mismatch')
                break
            if cell in seen or cell not in inv:
                raise ValueError('Unknown/duplicate cell '+cell)
            seen.add(cell)
            group = groups.setdefault(inv[cell]['category'], dict(area=0., watts=[0.]*4, cells=0))
            group['area'] += float(inv[cell]['area'])
            group['cells'] += 1
            for j in range(4):
                group['watts'][j] += raw[j]*scales[j]
        if seen != set(inv):
            raise ValueError('Incomplete per-cell power')
        for j in range(4):
            if not math.isclose(sum(g['watts'][j] for g in groups.values()), v[j], rel_tol=.025, abs_tol=1e-10):
                raise ValueError('Per-cell powers do not reconcile with total')
        cov = coverage((pt/'activity.rpt').read_text())
        setup = float((pt/'setup_slack_ns.txt').read_text())
        hold = float((pt/'hold_slack_ns.txt').read_text())
        review = []
        if min(setup, hold) < 0:
            review.append('TIMING_VIOLATION')
        if cov['net_coverage_percent'] < 99.9:
            review.append('INCOMPLETE_ACTIVITY')
        for fn in ('checks.rpt', 'model_checks.rpt', 'update.rpt', 'check_timing.rpt', 'activity.rpt'):
            if re.search(r'^\s*Warning:', (pt/fn).read_text(), re.M):
                review.append(fn)
        # Library units are unchanged across the frequency sweep.
        units = library_units((pt/'units.rpt').read_text())
        counts = win['counts']
        n = counts['responses_consumed']
        generated = counts['frames_generated']
        energy = v[3]*win['duration_ns']*1000
        row = dict(core=meta['core'], scenario=meta['scenario'], phase=label, seed=meta['seed'],
                   nominal_MHz=meta.get('nominal_MHz', 100),
                   effective_MHz=meta.get('effective_MHz', 100), clock_ns=meta['clock_ns'],
                   setup_uncertainty_ns=meta.get('setup_uncertainty_ns', 2.0),
                   reseed_cycles=meta['reseed_cycles'], area_um2=sum(float(x['area']) for x in inv.values()),
                   cells=len(inv), duration_ns=win['duration_ns'], frames_generated=generated,
                   responses_consumed=n, seed_loads=counts['seed_loads'], seed_bus_beats=counts['seed_bus_beats'],
                   internal_uW=v[0]*1e6, switching_uW=v[1]*1e6, leakage_uW=v[2]*1e6, total_uW=v[3]*1e6,
                   window_pJ=energy, pJ_per_consumed_frame=energy/n if n else None,
                   pJ_per_generated_frame=energy/generated if generated else None,
                   setup_slack_ns=setup, hold_slack_ns=hold,
                   library_time_s=units['time_s'], library_capacitance_F=units['capacitance_F'],
                   net_coverage_percent=cov['net_coverage_percent'], xz_signals=0,
                   status='CALCULATED_PROVISIONAL' if review else 'CALCULATED_PRELAYOUT',
                   review_flags=';'.join(review), waveform='zero_delay_gate_no_glitches_no_CTS')
        data.append(row)
        for category, g in groups.items():
            p = g['watts']
            parts.append(dict(core=meta['core'], scenario=meta['scenario'], phase=label, seed=meta['seed'],
                              nominal_MHz=meta.get('nominal_MHz', 100),
                              effective_MHz=meta.get('effective_MHz', 100),
                              category=category, cells=g['cells'], area_um2=g['area'], internal_uW=p[0]*1e6,
                              switching_uW=p[1]*1e6, leakage_uW=p[2]*1e6, total_uW=p[3]*1e6))
    csvwrite(output/'summary.csv', data)
    csvwrite(output/'power_breakdown.csv', parts)
    (output/'summary.json').write_text(json.dumps(data, indent=2)+'\n')
    return data


if __name__ == '__main__':
    summarize(Path(sys.argv[1]))
