"""Freeze and replay four small paired cases, one process at a time."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];WS=ROOT.parents[1]
SOURCE=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,indent=2)+'\n').encode())
parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');args=parser.parse_args()
names=('run_whole.py','whole_model.py','whole_pricing.py','sram_characterization.py','candidate_sram.py')
inputs={n:sha(SOURCE/n) for n in names}
for hz in (250,500):
    for name in ('BINDINGS.json','WHOLE_CONFIG.json'):inputs[f'{hz}MHz/{name}']=sha(SOURCE/f'{hz}MHz/{name}')
digest=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()[:12]
snap=HERE/('execution_'+digest);snap.mkdir(exist_ok=True)
for name in inputs:
    dest=snap/name;dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():assert sha(dest)==inputs[name]
    else:dest.write_bytes((SOURCE/name).read_bytes())
plan=[]
for hz in (250,500):
    for capacity in (960,832):
        name=f'p{hz}_{capacity}';cfg=json.loads((snap/f'{hz}MHz/WHOLE_CONFIG.json').read_bytes())
        cfg['SRAM'].update(layout_profile='compact960' if capacity==960 else 'activation96_attention36',
            capacity_KiB=capacity,bank_count=capacity//4)
        cfgpath=snap/f'{hz}MHz/{capacity}.json'
        if cfgpath.exists():assert json.loads(cfgpath.read_bytes())==cfg
        else:dump(cfgpath,cfg)
        command=[sys.executable,'-X','utf8','-B',str(snap/'run_whole.py'),
            '--snapshot',str(WS/'tmp/cross-model245-20261106/work/rayggxia/245/mainline_20261108/revision2/snapshot'),
            '--runtime',str(WS/'project_archives/ffn_sram_batch204_20261106/runtime'),
            '--dependencies',str(WS/'project_archives/sram1216_225_20261106/dependencies'),
            '--bindings',str(snap/f'{hz}MHz/BINDINGS.json'),'--macros',str(cfgpath),
            '--cores','3' if hz==250 else '2','--layers','2' if hz==250 else '1',
            '--head','--head-probe-rows','384','--seed','17','--backend','analytic','--out',str(HERE/name)]
        plan.append(dict(name=name,clock_MHz=hz,capacity_KiB=capacity,command=command,
            config_sha256=sha(cfgpath)))
dump(HERE/'PLAN.json',dict(status='PREPARED_IMMUTABLE_SMALL_PAIRED_REPLAYS',source_sha256=inputs,
    execution=str(snap),cases=plan,workers=1,backend='analytic',no_new_PPA=True,default_changed=False))
if args.prepare:
    print(json.dumps(dict(prepared=4,snapshot=str(snap),source=digest)));raise SystemExit
for p in plan:
    out=HERE/p['name'];log=HERE/(p['name']+'.log')
    if (out/'SEAL.json').exists():
        sealed=json.loads((out/'SEAL.json').read_bytes())
        assert sealed['status']=='completed'
        for n,v in sealed['files_sha256'].items():assert sha(out/n)==v
        print(json.dumps(dict(case=p['name'],status='existing_sealed_reused')),flush=True);continue
    if out.exists():raise RuntimeError('Unsealed prior attempt preserved;choose a new run directory')
    started=time.time()
    print(json.dumps(dict(case=p['name'],status='starting',time=time.time())),flush=True)
    with log.open('w',encoding='utf8') as stream:
        code=subprocess.run(p['command'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT).returncode
    dump(HERE/(p['name']+'_RETURN.json'),dict(exit_code=code,wall_seconds=time.time()-started,
         log_sha256=sha(log),source_sha256=inputs))
    if code:
        print(json.dumps(dict(case=p['name'],status='failed',exit_code=code,log=str(log))),flush=True)
        raise SystemExit(code)
    print(json.dumps(dict(case=p['name'],status='completed',wall_seconds=time.time()-started)),flush=True)
print(json.dumps(dict(status='FOUR_SMALL_PAIRS_FINISHED')),flush=True)
