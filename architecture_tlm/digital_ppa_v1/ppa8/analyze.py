"""Reconcile leaf powers/area and count completed transactions, not nominal cycles."""
import csv
import json
import math
from pathlib import Path
import re
import sys
from cell_report_parser import rows
from report_helpers import library_units, totals, coverage, csvwrite


def summarize(work):
    cfg = json.loads((work/'configuration.json').read_text())
    data, breakdown = [], []
    for marker in sorted((work/'power').glob('*/POWER_CALCULATED')):
        pt = marker.parent
        sim = work/'gate'/pt.name
        meta = json.loads((sim/'workload.json').read_text())
        audit = json.loads((sim/'wave_audit.json').read_text())
        if audit['xz_signals']:
            raise ValueError('Unknown values in measured nets')
        power, scales = totals((pt/'power.rpt').read_text())
        library_units((pt/'units.rpt').read_text())
        cov = coverage((pt/'activity.rpt').read_text())
        with (pt/'inventory.tsv').open() as f:
            inv = {r['name']: r for r in csv.DictReader(f, delimiter='\t')}
        groups, seen = {}, set()
        for cell, raw, flags in rows(pt/'cells.rpt'):
            if cell is None:
                if raw[0] != len(seen):
                    raise ValueError('Cell count mismatch')
                break
            if cell in seen or cell not in inv:
                raise ValueError('Duplicate/unknown power cell '+cell)
            seen.add(cell)
            group = groups.setdefault(inv[cell]['category'], dict(area=0., watts=[0.]*4, cells=0))
            group['area'] += float(inv[cell]['area'])
            group['cells'] += 1
            for j in range(4):
                group['watts'][j] += raw[j]*scales[j]
        if seen != set(inv):
            raise ValueError('Incomplete cell-power coverage')
        for j in range(4):
            if not math.isclose(sum(g['watts'][j] for g in groups.values()), power[j], rel_tol=.025, abs_tol=1e-10):
                raise ValueError('Cell totals do not reconcile')
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
        idle = meta['mode'] == 'idle'
        n = 0 if idle else meta['outputs']
        accepts = 0 if idle else meta['inputs']
        energy = power[3]*audit['duration_ns']*1000
        data.append(dict(kind=cfg['kind'], corner=cfg['corner'], MHz=100, seed=meta['seed'], mode=meta['mode'],
            voltage_V=cfg['voltage_V'], temperature_C=cfg['temperature_C'],
            area_um2=sum(float(r['area']) for r in inv.values()), cells=len(inv),
            inputs=accepts, completed_outputs=n, duration_ns=audit['duration_ns'],
            internal_uW=power[0]*1e6, switching_uW=power[1]*1e6, leakage_uW=power[2]*1e6, total_uW=power[3]*1e6,
            window_pJ=energy, pJ_per_input=energy/accepts if accepts else None,
            pJ_per_completed_output=energy/n if n else None,
            setup_slack_ns=setup, hold_slack_ns=hold,
            net_coverage_percent=cov['net_coverage_percent'],
            status='CALCULATED_PROVISIONAL' if review else 'CALCULATED_PRELAYOUT', review_flags=';'.join(review)))
        for category, g in groups.items():
            breakdown.append(dict(kind=cfg['kind'], corner=cfg['corner'], seed=meta['seed'], mode=meta['mode'],
                category=category, cells=g['cells'], area_um2=g['area'],
                internal_uW=g['watts'][0]*1e6, switching_uW=g['watts'][1]*1e6,
                leakage_uW=g['watts'][2]*1e6, total_uW=g['watts'][3]*1e6))
    csvwrite(work/'summary.csv', data)
    csvwrite(work/'power_breakdown.csv', breakdown)
    (work/'summary.json').write_text(json.dumps(data, indent=2)+'\n')
    return data


if __name__ == '__main__':
    summarize(Path(sys.argv[1]))
