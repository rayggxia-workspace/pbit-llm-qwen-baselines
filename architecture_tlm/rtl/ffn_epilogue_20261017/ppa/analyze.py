"""Report measured-window energy and mapped-cell area, never die area."""
import csv
import json
import math
import pathlib
import re
import sys
from cell_report_parser import rows, unit_scales, NUM


def write_csv(path, data):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def totals(text):
    scales = unit_scales(text)
    values = []
    for label, scale in zip(('Cell Internal Power', 'Net Switching Power', 'Cell Leakage Power', 'Total Power'), scales):
        m = re.search(r'^\s*' + label + r'\s*=\s*(' + NUM + ')', text, re.M)
        if not m:
            raise ValueError('Missing ' + label)
        values.append(float(m[1]) * scale)
    if values[3] <= 0 or not math.isclose(sum(values[:3]), values[3], rel_tol=.02, abs_tol=1e-12):
        raise ValueError('Inconsistent total power')
    return values, scales


def coverage(text):
    result = {}
    for key, label in [('total_nets', 'Total number of nets'), ('annotated_nets', 'Number of annotated nets'),
                       ('leaf_cells', 'Total number of leaf cells'), ('fully_annotated_cells', 'Number of fully annotated leaf cells')]:
        m = re.search(re.escape(label) + r'\s*=\s*(\d+)', text)
        if not m:
            raise ValueError('Missing VCD coverage: ' + label)
        result[key] = int(m[1])
    if not 0 < result['annotated_nets'] <= result['total_nets']:
        raise ValueError('Invalid/zero annotation')
    result['net_coverage_percent'] = 100. * result['annotated_nets'] / result['total_nets']
    return result


def summarize(work, names):
    work = pathlib.Path(work)
    data, parts = [], []
    with (work / 'dc/inventory.tsv').open() as f:
        inv = list(csv.DictReader(f, delimiter='\t'))
    area = {}
    for r in inv:
        area[r['category']] = area.get(r['category'], 0) + float(r['area'])
    write_csv(work / 'area_breakdown.csv', [dict(category=k, area_um2=v) for k, v in area.items()])
    for name in names:
        folder = work / 'power' / name
        if not (folder / 'POWER_CALCULATED').exists():
            raise ValueError('Incomplete PT: ' + name)
        meta = json.loads((work / 'gate' / name / 'workload.json').read_text())
        audit = json.loads((work / 'gate' / name / 'wave_audit.json').read_text())
        if audit['xz_signals']:
            raise ValueError('Unknown activity is not waived')
        v, scales = totals((folder / 'power.rpt').read_text())
        with (folder / 'inventory.tsv').open() as f:
            pinv = {r['name']: r for r in csv.DictReader(f, delimiter='\t')}
        groups, seen = {}, set()
        for cell, raw, flags in rows(folder / 'cells.rpt'):
            if cell is None:
                if raw[0] != len(seen):
                    raise ValueError('Cell count mismatch')
                break
            if cell not in pinv or cell in seen:
                raise ValueError('Unknown/duplicate power cell: ' + cell)
            seen.add(cell)
            group = groups.setdefault(pinv[cell]['category'], [0.] * 4)
            for j in range(4):
                group[j] += raw[j] * scales[j]
        if seen != set(pinv):
            raise ValueError('Incomplete cell coverage')
        if any(not math.isclose(sum(g[j] for g in groups.values()), v[j], rel_tol=.025, abs_tol=1e-10) for j in range(4)):
            raise ValueError('Per-cell power does not reconcile with full power')
        for group, values in groups.items():
            parts.append(dict(window=name, category=group, internal_uW=values[0]*1e6,
                              switching_uW=values[1]*1e6, leakage_uW=values[2]*1e6, total_uW=values[3]*1e6))
        setup = float((folder / 'setup_slack_ns.txt').read_text())
        hold = float((folder / 'hold_slack_ns.txt').read_text())
        n, duration = meta['produced'], meta['duration_ns']
        row = dict(meta, window=name, area_um2=sum(area.values()), internal_uW=v[0]*1e6,
                   switching_uW=v[1]*1e6, leakage_uW=v[2]*1e6, total_uW=v[3]*1e6,
                   total_window_pJ=v[3]*duration*1000,
                   total_pJ_per_output=v[3]*duration*1000/n if n else None,
                   dynamic_pJ_per_output=(v[0]+v[1])*duration*1000/n if n else None,
                   setup_slack_ns=setup, hold_slack_ns=hold,
                   timing_status='NONNEGATIVE_REVIEW_CONSTRAINTS' if min(setup, hold)>=0 else 'TIMING_VIOLATION',
                   status='CALCULATED_REVIEW_REQUIRED')
        row.update(coverage((folder / 'activity.rpt').read_text()))
        data.append(row)
    write_csv(work / 'summary.csv', data)
    write_csv(work / 'power_breakdown.csv', parts)
    (work / 'summary.json').write_text(json.dumps(data, indent=2) + '\n')
    return data


if __name__ == '__main__':
    root = pathlib.Path(sys.argv[1])
    summarize(root, json.loads((root / 'configuration.json').read_text())['cases'])
