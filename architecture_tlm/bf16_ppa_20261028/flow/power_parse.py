"""PT 2018 reports, explicit units and exact VCD/port cross-checks."""
import csv
import math
from pathlib import Path
import re
from power_vcd import verify_pt
NUM=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
ROW=re.compile(r'^(.*?)\s+('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s+\(\s*'+NUM+r'\s*%\)\s*([a-z ]*)$')
TOTAL=re.compile(r'^Totals\s*\((\d+)\s+cells?\)')

def totals(text):
    factors={'W':1.,'mW':1e-3,'uW':1e-6,'nW':1e-9,'pW':1e-12}
    def scale(kind):
        m=re.search(r'^\s*'+kind+r' Units?\s*[:=]\s*('+NUM+r')\s*(W|mW|uW|nW|pW)\s*$',text,re.M)
        if not m:raise ValueError('Missing power unit '+kind)
        return float(m[1])*factors[m[2]]
    dyn,leak=scale('Dynamic Power'),scale('Leakage Power')
    scales=[dyn,dyn,leak,dyn];values=[]
    for label,s in zip(('Cell Internal Power','Net Switching Power','Cell Leakage Power','Total Power'),scales):
        m=re.search(r'^\s*'+label+r'\s*=\s*('+NUM+')',text,re.M)
        if not m:raise ValueError('Missing '+label)
        values.append(float(m[1])*s)
    if not all(math.isfinite(v) for v in values) or values[3]<=0 or not math.isclose(sum(values[:3]),values[3],rel_tol=.02,abs_tol=1e-12):raise ValueError('Inconsistent power')
    return values,scales

def parse(pt, meta, audit):
    pt=Path(pt)
    if not (pt/'POWER_CALCULATED').is_file():raise ValueError('No completed power report')
    if not (audit['all_bits_preserved'] or audit.get('full_mapped_boundary_verified')) or audit['xz_signals']:
        raise ValueError('Incomplete/X activity')
    if audit.get('full_mapped_boundary_verified'):
        boundary=set((pt/'activity_boundary.txt').read_text().splitlines())
        if boundary!=set(audit['expected_activity']):raise ValueError('PT boundary changed')
    if abs(audit['duration_ns']-meta['duration_ns'])>1e-6:raise ValueError('Window duration mismatch')
    checked=verify_pt(audit,pt/'output_activity.tsv')
    values,scales=totals((pt/'power.rpt').read_text())
    with (pt/'inventory.tsv').open() as f:inv={r['name']:r for r in csv.DictReader(f,delimiter='\t')}
    seen=set();groups={};pending='';started=False;header=False;count=None
    for line in (pt/'cells.rpt').read_text().splitlines():
        s=line.strip()
        if not started:
            if re.match(r'^Cell\s+Power\s+Power',s):header=True
            if header and s.startswith('---'):started=True
            continue
        if not s or s.startswith('---'):continue
        pending=(pending+' '+s).strip()
        total=TOTAL.match(pending)
        if total:count=int(total[1]);break
        m=ROW.fullmatch(pending)
        if m:
            name=''.join(m[1].split())
            if name in seen or name not in inv:raise ValueError('Unknown/duplicate cell '+name)
            seen.add(name);item=inv[name]
            group=groups.setdefault(item['category'],dict(cells=0,area_um2=0.,watts=[0.]*4))
            group['cells']+=1;group['area_um2']+=float(item['area'])
            for j in range(4):group['watts'][j]+=float(m[j+2])*scales[j]
            pending=''
        if len(pending)>16384:raise ValueError('Unparsed cell row')
    if count!=len(seen) or seen!=set(inv):raise ValueError('Incomplete cell power inventory')
    for j in range(4):
        if not math.isclose(sum(g['watts'][j] for g in groups.values()),values[j],rel_tol=.025,abs_tol=1e-10):raise ValueError('Per-cell totals mismatch')
    activity=(pt/'activity.rpt').read_text()
    def num(label):
        m=re.search(re.escape(label)+r'\s*=\s*(\d+)',activity)
        if not m:raise ValueError('Missing '+label)
        return int(m[1])
    nets,annotated=num('Total number of nets'),num('Number of annotated nets')
    if not 0<annotated<=nets:raise ValueError('Invalid annotation counts')
    coverage=100.*annotated/nets
    leaf_count=num('Total number of leaf cells')
    full_leaves=num('Number of fully annotated leaf cells')
    if leaf_count!=len(inv) or not 0<=full_leaves<=leaf_count:raise ValueError('Invalid leaf annotation counts')
    flags=[]
    if audit.get('full_mapped_boundary_verified'):
        if full_leaves!=leaf_count:raise ValueError('Incomplete mapped cell activity')
    elif coverage<99.9:flags.append('INCOMPLETE_ACTIVITY')
    setup=float((pt/'setup_slack_ns.txt').read_text());hold=float((pt/'hold_slack_ns.txt').read_text())
    if min(setup,hold)<0:flags.append('TIMING_VIOLATION')
    for fn in ('activity.rpt','checks.rpt','model_checks.rpt','update.rpt','check_timing.rpt'):
        if re.search(r'^\s*Warning:',(pt/fn).read_text(),re.M):flags.append(fn)
    n=meta['operations'];energy=values[3]*meta['duration_ns']*1000
    return dict(core=meta['core'],mode=meta['mode'],seed=meta['seed'],frequency_MHz=100,
                status='CALCULATED_PROVISIONAL' if flags else 'CALCULATED_PRELAYOUT',review_flags=flags,
                area_um2=sum(float(x['area']) for x in inv.values()),cells=len(inv),
                internal_W=values[0],switching_W=values[1],leakage_W=values[2],total_W=values[3],
                window_ns=meta['duration_ns'],operations=n,samples=meta['accepted_samples'],
                window_energy_pJ=energy,gross_pJ_per_operation=energy/n if n else None,
                cycles_per_operation=meta['measurement_cycles']/n if n else None,
                setup_slack_ns=setup,hold_slack_ns=hold,net_coverage_percent=coverage,
                leaf_coverage_percent=100.*full_leaves/leaf_count,
                unannotated_net_count=nets-annotated,
                all_mapped_pin_activity_verified=bool(audit.get('full_mapped_boundary_verified')),
                zero_time_delta_transitions=audit.get('zero_time_delta_transitions',0),
                activity_checked_bits=checked['checked_bits'],groups=groups,
                boundary='Only mapped DUT; external weights/config memory, RNG, CTS and wires excluded. Register internal power is not isolated clock power.')
