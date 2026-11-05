from pathlib import Path
import hashlib,json,subprocess
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3];ROOT=REPO/'architecture_tlm/module_energy_20261028';WS=REPO.parents[1]
TOOLS=WS/'sc_weight_storage_or4_20261014/tools/iverilog/bin';OUT=HERE/'private/local_check';OUT.mkdir(parents=True,exist_ok=True)
rows=[]
for c in json.loads((ROOT/'CASES.json').read_text()):
 d=OUT/c['name'];d.mkdir(exist_ok=True)
 cmd=[str(TOOLS/'iverilog.exe'),'-g2012','-s','tb','-o',str(d/'sim.vvp'),str(ROOT/'rtl/primitives.sv'),str(ROOT/'rtl/tops.sv'),str(ROOT/'benches'/(c['name']+'.sv'))]
 p=subprocess.run(cmd,cwd=d,capture_output=True);(d/'compile.log').write_bytes(p.stdout+p.stderr)
 if p.returncode:raise RuntimeError('Compile failed '+c['name']+' '+p.stderr.decode(errors='replace')[:1000])
 for seed in (17,503,1009):
  case=d/str(seed);case.mkdir(exist_ok=True)
  for name in ('stim.hex','expect.hex'):(case/name).write_bytes((ROOT/'fixtures'/c['name']/str(seed)/name).read_bytes())
  p=subprocess.run([str(TOOLS/'vvp.exe'),str(d/'sim.vvp')],cwd=case,capture_output=True);(case/'run.log').write_bytes(p.stdout+p.stderr)
  if p.returncode or b'FUNCTION_PASS' not in p.stdout:raise RuntimeError(c['name']+' '+str(seed)+' '+p.stdout.decode(errors='replace')[-1000:])
  n=json.loads((ROOT/'fixtures'/c['name']/str(seed)/'WINDOWS.json').read_text())['transactions'];rows.append({'case':c['name'],'seed':seed,'transactions':n,'status':'pass'})
 print('LOCAL_PASS',c['id'],c['name'],flush=True)
(HERE/'LOCAL_CHECK.json').write_text(json.dumps({'status':'pass','replays':rows,'total_transactions':sum(x['transactions'] for x in rows),'source_SHA256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'rtl').glob('*.sv')}},indent=2)+'\n',encoding='utf-8',newline='\n')
print('ALL_LOCAL_PASS',len(rows))
