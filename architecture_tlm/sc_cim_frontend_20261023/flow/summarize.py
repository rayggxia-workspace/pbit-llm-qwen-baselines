"""Report-derived PPA; sum exclusive leaf cells, never sum hierarchy levels."""
import csv
import json
import math
import re
from pathlib import Path

NUM = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'


def power_totals(text):
    factors = dict(W=1., mW=1e-3, uW=1e-6, nW=1e-9, pW=1e-12)
    units = []
    for name in ('Dynamic Power', 'Leakage Power'):
        m = re.search(r'^\s*'+name+r' Units?\s*[:=]\s*('+NUM+r')\s*(W|mW|uW|nW|pW)(?:\s*\([^\n]*\))?\s*$', text, re.M)
        if not m: raise ValueError('Missing power unit: '+name)
        units.append(float(m[1])*factors[m[2]])
    scales = [units[0], units[0], units[1], units[0]]
    values = []
    for name, scale in zip(('Cell Internal Power','Net Switching Power','Cell Leakage Power','Total Power'), scales):
        m = re.search(r'^\s*'+name+r'\s*=\s*('+NUM+')', text, re.M)
        if not m: raise ValueError('Missing '+name)
        values.append(float(m[1])*scale)
    if not all(math.isfinite(v) for v in values) or values[3]<=0 or not math.isclose(sum(values[:3]),values[3],rel_tol=.02,abs_tol=1e-12):
        raise ValueError('Invalid/reconciling power totals')
    return values, scales


def leaf_rows(path):
    # Synopsys report_power -cell_power wraps long instance names over lines.
    row = re.compile(r'^(.*?)\s+('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s+\(\s*'+NUM+r'\s*%\)\s*([a-z ]*)$')
    header = started = False
    pending = ''
    for line in path.read_text().splitlines():
        s = line.strip()
        if not started:
            if re.match(r'^Cell\s+Power\s+Power', s): header = True
            if header and s.startswith('---'): started = True
            continue
        if not s or s.startswith('---'): continue
        pending = (pending+' '+s).strip()
        total = re.match(r'^Totals\s*\((\d+)\s+cells?\)', pending)
        if total:
            yield None, int(total[1])
            return
        m = row.fullmatch(pending)
        if m:
            yield ''.join(m[1].split()), [float(m[j]) for j in range(2,6)]
            pending = ''
        if len(pending)>16384: raise ValueError('Unrecognized cell-power row')
    raise ValueError('Missing cell-power totals')


def check_time_unit(text):
    m = re.search(r'^\s*Time\s*Units?\s*[:=]\s*('+NUM+r')\s*(\w+)\s*$', text, re.I|re.M)
    factors = dict(s=1., second=1., seconds=1., ns=1e-9, ps=1e-12, us=1e-6)
    if not m or m[2].lower() not in factors or not math.isclose(float(m[1])*factors[m[2].lower()],1e-9,rel_tol=1e-9,abs_tol=0):
        raise ValueError('Activity/slack parser requires a 1ns library; inspect units.rpt')


def window_summary(pt, meta):
    check_time_unit((pt/'units.rpt').read_text())
    values, scales = power_totals((pt/'power.rpt').read_text())
    with (pt/'inventory.tsv').open() as f:
        inv = {r['name']:r for r in csv.DictReader(f,delimiter='\t')}
    groups, seen = {}, set()
    for name, raw in leaf_rows(pt/'cells.rpt'):
        if name is None:
            if raw!=len(seen): raise ValueError('Cell count mismatch')
            break
        if name in seen or name not in inv: raise ValueError('Unknown/duplicate cell '+name)
        seen.add(name)
        g = groups.setdefault(inv[name]['category'],dict(cells=0,area_um2=0.,watts=[0.]*4))
        g['cells']+=1; g['area_um2']+=float(inv[name]['area'])
        for j in range(4): g['watts'][j]+=raw[j]*scales[j]
    if seen!=set(inv): raise ValueError('Incomplete cell-power coverage')
    for j in range(4):
        if not math.isclose(sum(g['watts'][j] for g in groups.values()),values[j],rel_tol=.025,abs_tol=1e-10):
            raise ValueError('Cell powers do not reconcile with design total')
    flags=[]
    if min(meta['setup_slack_ns'],meta['hold_slack_ns'])<0: flags.append('TIMING_VIOLATION')
    for name in ('checks.rpt','ranges.rpt','model_checks.rpt','update.rpt','check_timing.rpt','activity.rpt'):
        if re.search(r'^\s*Warning:',(pt/name).read_text(),re.M): flags.append(name)
    act=(pt/'activity.rpt').read_text()
    a=re.search(r'Number of annotated nets\s*=\s*(\d+)',act)
    n=re.search(r'Total number of nets\s*=\s*(\d+)',act)
    coverage=None
    if a and n and int(n[1])>0:
        coverage=100.*int(a[1])/int(n[1])
        if not 0<coverage<=100: raise ValueError('Invalid activity coverage')
        if coverage<99.9: flags.append('INCOMPLETE_ACTIVITY')
    else: flags.append('ACTIVITY_COVERAGE_NOT_PARSED')
    energy=values[3]*meta['duration_ns']*1000
    return dict(area_um2=sum(float(r['area']) for r in inv.values()),cells=len(inv),
        internal_uW=values[0]*1e6,switching_uW=values[1]*1e6,leakage_uW=values[2]*1e6,total_uW=values[3]*1e6,
        window_pJ=energy,pJ_per_frame=energy/meta['frames'] if meta['frames'] else None,
        pJ_per_sample_vector=energy/meta['accepted_samples'] if meta['accepted_samples'] else None,
        net_coverage_percent=coverage,review_flags=flags,
        status='CALCULATED_PROVISIONAL' if flags else 'CALCULATED_PRELAYOUT',
        exclusive_groups=groups)


def write_csv(out, windows):
    if not windows: return
    rows=[{k:v for k,v in row.items() if k!='exclusive_groups'} for row in windows]
    with (out/'summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Reparse existing reports without DC/VCS/PT')
    parser.add_argument('result',type=Path)
    args=parser.parse_args()
    windows=[]
    for path in sorted((args.result/'power').glob('*/WINDOW.json')):
        pt=path.parent
        if json.loads((pt/'ACTIVITY_CHECK.json').read_text())['status']!='PASS':
            raise ValueError('Activity verification missing')
        row=json.loads(path.read_text());row.update(window_summary(pt,row));windows.append(row)
    if not windows: raise ValueError('No verified windows')
    write_csv(args.result,windows)
    (args.result/'REPARSED_SUMMARY.json').write_text(json.dumps(windows,indent=2)+'\n')
    print('Reparsed {} windows; this does not create FLOW_COMPLETE'.format(len(windows)))
