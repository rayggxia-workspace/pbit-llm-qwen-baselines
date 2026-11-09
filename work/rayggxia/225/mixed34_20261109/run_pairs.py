"""Freeze and replay the requested mixed macro organization with shared ports."""
from pathlib import Path
import argparse,ast,copy,hashlib,json,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];WS=ROOT.parents[1]
SOURCE=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,indent=2)+'\n').encode())
parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true')
parser.add_argument('--run-dir',type=Path);parser.add_argument('--reuse-base',type=Path);args=parser.parse_args()
OUT=args.run_dir or HERE;OUT.mkdir(parents=True,exist_ok=True)
delivery=WS/'architecture_tlm/process_28nm/SRAM_CHARACTERIZATION_RESULTS_20261109.json'
library=json.loads(delivery.read_bytes());lib={r['macro_id']:r for r in library['library_records'] if r['VDD_V']==.9}
def scalar(record,condition):
    for p in record['conditional_power_tables']:
        raw=p['raw'];children=raw['children'];attrs={x['name']:x.get('value') for x in children if x['kind']=='attr'}
        if condition=='leak':
            if p['path'].endswith('/leakage_power()') and attrs.get('when')=='!SD & !SLP':return float(attrs['value'])*1e-6
        elif '/pin(CLK)/internal_power()' in p['path'] and attrs.get('when')==condition:
            return sum(float(x['args'][0]) for g in children if g['kind']=='group' and g['name'] in ('rise_power','fall_power') for x in g['children'] if x['name']=='values')
    raise ValueError(condition)
read='!SD & !SLP &!CEB & WEB & !BIST';write='!SD & !SLP &!CEB & !WEB & !BIST'
delta={k:scalar(lib['S2'],v)-scalar(lib['S0'],v) for k,v in [('read',read),('write',write)]}
names=('run_whole.py','whole_model.py','whole_pricing.py','sram_characterization.py','candidate_sram.py','mixed_sram.py')
inputs={n:sha(SOURCE/n) for n in names}
for hz in (250,500):
    for name in ('BINDINGS.json','WHOLE_CONFIG.json'):inputs[f'{hz}MHz/{name}']=sha(SOURCE/f'{hz}MHz/{name}')
digest=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()[:12]
snap=OUT/('execution_'+digest);snap.mkdir(exist_ok=True)
for n in inputs:
    dest=snap/n;dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():assert sha(dest)==inputs[n]
    else:dest.write_bytes((SOURCE/n).read_bytes())
for n in names:ast.parse((snap/n).read_text(),filename=n)
plan=[]
for hz in (250,500):
    for mixed in (False,True):
        name=f'p{hz}_'+('mixed' if mixed else 'base')
        cfg=json.loads((snap/f'{hz}MHz/WHOLE_CONFIG.json').read_bytes());s=cfg['SRAM'];assert s['bank_count']==208
        if mixed:
            card0=dict(bytes=4096,area_mm2=lib['S0']['area_um2']/1e6,
                read_pJ_per16B=s['read_pJ_per16B'],write_pJ_per16B=s['write_pJ_per16B'],
                idle_W=s['leak_W_per4KiB'],clock_on_idle_W=s['clock_on_idle_W_per4KiB'],source='S0_PT')
            card2=dict(bytes=8192,area_mm2=lib['S2']['area_um2']/1e6,
                read_pJ_per16B=card0['read_pJ_per16B']+delta['read'],
                write_pJ_per16B=card0['write_pJ_per16B']+delta['write'],
                idle_W=scalar(lib['S2'],'leak'),
                clock_on_idle_W=scalar(lib['S2'],'leak')+card0['clock_on_idle_W']-card0['idle_W'],
                source='S2_library;S0_PT_plus_CLK_delta_estimate;not newS2PT')
            s.update(bank_count=178,mixed_CIM_30x8_4x4=True,macro_models={'S0':card0,'S2':card2},
                price_status='S0_PT_PLUS_S2_LIBRARY_DELTA_ESTIMATE')
        cfgpath=snap/f'{hz}MHz/{name}.json'
        if cfgpath.exists():assert json.loads(cfgpath.read_bytes())==cfg
        else:dump(cfgpath,cfg)
        cmd=[sys.executable,'-X','utf8','-B',str(snap/'run_whole.py'),
            '--snapshot',str(WS/'tmp/cross-model245-20261106/work/rayggxia/245/mainline_20261108/revision2/snapshot'),
            '--runtime',str(WS/'project_archives/ffn_sram_batch204_20261106/runtime'),
            '--dependencies',str(WS/'project_archives/sram1216_225_20261106/dependencies'),
            '--bindings',str(snap/f'{hz}MHz/BINDINGS.json'),'--macros',str(cfgpath),
            '--cores','3' if hz==250 else '2','--layers','2' if hz==250 else '1',
            '--head','--head-probe-rows','384','--seed','17','--backend','analytic','--out',str(OUT/name)]
        plan.append(dict(name=name,clock_MHz=hz,mixed=mixed,command=cmd,config_sha256=sha(cfgpath)))
dump(OUT/'PLAN.json',dict(status='IMMUTABLE_MIXED_MACRO_PAIRS',execution=str(snap),source_sha256=inputs,
    library_source_sha256=sha(delivery),S2_energy_estimate='S0_PT_increment+samePVT_CLK_internal_energy_difference',
    library_CLK_delta_pJ=delta,cases=plan,workers=1,backend='analytic',default_changed=False))
if args.prepare:print(json.dumps(dict(prepared=4,snapshot=str(snap),delta_pJ=delta)));raise SystemExit
for p in plan:
    out=OUT/p['name'];log=OUT/(p['name']+'.log')
    old=args.reuse_base/p['name'] if args.reuse_base else None
    if not p['mixed'] and old and (old/'SEAL.json').exists():
        sealed=json.loads((old/'SEAL.json').read_bytes());assert sealed['status']=='completed'
        for n,v in sealed['files_sha256'].items():assert sha(old/n)==v
        result=json.loads((old/'RESULT.json').read_bytes())
        assert result['macro_config_sha256']==p['config_sha256']
        for n,v in result['code_sha256'].items():
            if n!='sram_characterization.py':assert v==inputs[n]
        dump(OUT/(p['name']+'_REUSED.json'),dict(path=str(old),files_sha256=sealed['files_sha256'],
            reason='Only mixed-bank binary64 energy audit bound changed;unmixed scheduling and budget branch unchanged'))
        print(json.dumps(dict(case=p['name'],status='sealed_baseline_reused',path=str(old))),flush=True);continue
    if (out/'SEAL.json').exists():
        sealed=json.loads((out/'SEAL.json').read_bytes());assert sealed['status']=='completed'
        for n,v in sealed['files_sha256'].items():assert sha(out/n)==v
        print(json.dumps(dict(case=p['name'],status='existing_sealed_reused')),flush=True);continue
    if out.exists():raise RuntimeError('Unsealed attempt preserved;use new run directory')
    started=time.time();print(json.dumps(dict(case=p['name'],status='starting')),flush=True)
    with log.open('w',encoding='utf8') as stream:code=subprocess.run(p['command'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT).returncode
    dump(OUT/(p['name']+'_RETURN.json'),dict(exit_code=code,wall_seconds=time.time()-started,log_sha256=sha(log)))
    print(json.dumps(dict(case=p['name'],status='completed' if code==0 else 'failed',exit_code=code,wall_seconds=time.time()-started)),flush=True)
    if code:raise SystemExit(code)
print(json.dumps(dict(status='FOUR_MIXED_PAIRS_FINISHED')),flush=True)
