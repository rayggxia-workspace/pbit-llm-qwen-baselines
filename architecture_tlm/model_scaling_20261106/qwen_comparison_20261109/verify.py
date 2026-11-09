from pathlib import Path
import hashlib,json,math,statistics

p=Path(__file__).resolve().parent
load=lambda f:json.loads(f.read_bytes())
s=load(p/'SUMMARY.json');idx=load(p/'SOURCE_INDEX.json');raw=load(Path(idx['input_path']))
assert hashlib.sha256(Path(idx['input_path']).read_bytes()).hexdigest()==idx['input_sha256']==s['input_sha256']
assert hashlib.sha256((p/'summarize.py').read_bytes()).hexdigest()==idx['script_sha256']
assert len(raw['rows'])==12 and len(s['rows'])==8 and len(s['ratios'])==12
assert {r['index'] for r in raw['rows']}==set(range(12))
for r in raw['rows']:
    assert r['backend']=='native' and r['source_manifest_sha256']==s['source_manifest_sha256']
    assert len(r['files_sha256'])==4
    assert math.isclose(sum(z['total_uJ'] for z in r['components'])/1000,r['including_head']['onchip_mJ'],abs_tol=1e-9)
    assert math.isclose(sum(r['phase_totals_ns'].values())/1e6,r['including_head']['time_ms'],abs_tol=1e-9)
for r in s['rows']:
    assert r['FMA_lanes']%16==0
    for boundary in ('including_head','excluding_head_stage'):
        z=r[boundary]
        assert math.isclose(z['system_average_W']*z['time_ms'],z['system4pJ_mJ'],rel_tol=1e-12)
        assert math.isclose(z['onchip_average_W']*z['time_ms'],z['onchip_mJ'],rel_tol=1e-12)
        assert z['onchip_mJ']<z['system4pJ_mJ']<z['system6p6_mJ']<z['system8_mJ']
    assert r['including_head']['time_ms']>r['excluding_head_stage']['time_ms']
    assert r['including_head']['system4pJ_mJ']>r['excluding_head_stage']['system4pJ_mJ']
    assert r['deployment_seeds']==(3 if r['scheme']=='SC_ising' else 1)
by={(r['clock_MHz'],r['scheme']):r for r in s['rows']}
for x in s['ratios']:
    a=by[x['clock_MHz'],'SC_ising'];b=by[x['clock_MHz'],x['control']];k=x['boundary']
    assert math.isclose(x['speedup'],b[k]['time_ms']/a[k]['time_ms'])
    assert math.isclose(x['total_energy_reduction_percent'],100*(1-a[k]['system4pJ_mJ']/b[k]['system4pJ_mJ']))
    assert -3<x['digital_area_gap_percent']<0 # explicitly approximate area, not equal bits
assert s['all36_complete_not_claimed'] and s['no_new_simulation']
out=dict(status='PASS',executions=12,configurations=8,comparisons=12,
    checks=['sealed-input-identity','all12unique','threeSCseeds','sameclockarea-cap-gap-retained',
        'phase-time-sum','component-energy-sum','head-boundary-not-nohead-rerun','E=P*T',
        'speed-and-energy-ratios','external-price-sensitivity','no-all36-or-qualityclaim'])
(p/'VALIDATION.json').write_bytes((json.dumps(out,indent=2)+'\n').encode())
print(json.dumps(out))
