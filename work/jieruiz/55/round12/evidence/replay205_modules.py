from pathlib import Path
import subprocess,json,hashlib,re,shutil
A=Path(__file__).resolve().parent;SRC=A/'module205_source';OUT=A/'rtl205_modules';OUT.mkdir(exist_ok=False);iv=A.parent.parent/'sc_weight_storage_or4_20261014/tools/iverilog';rows=[]
def run(cmd,cwd,log):
 p=subprocess.run(list(map(str,cmd)),cwd=cwd,capture_output=True,timeout=120);(cwd/log).write_bytes(p.stdout+p.stderr);assert p.returncode==0,(cwd,log);return p.stdout.decode()
for tb in sorted((SRC/'benches').glob('*.sv')):
 d=OUT/tb.stem;d.mkdir();exe=d/'sim.vvp'
 run([iv/'bin/iverilog.exe','-B',iv/'lib/ivl','-g2012','-s','tb','-o',exe,SRC/'rtl/primitives.sv',SRC/'rtl/tops.sv',tb],d,'compile.log')
 for seed in [17,503,1009]:
  f=d/str(seed);f.mkdir();ref=SRC/'fixtures'/tb.stem/str(seed)
  for name in ['stim.hex','expect.hex']:shutil.copyfile(ref/name,f/name)
  text=run([iv/'bin/vvp.exe','-M',iv/'lib/ivl',exe],f,'simulation.log');n=int(re.search(r'FUNCTION_PASS transactions=(\d+)',text)[1]);assert n==json.loads((ref/'WINDOWS.json').read_text())['transactions']
  wave=f/'activity.vcd';rows.append(dict(top=tb.stem,seed=seed,transactions=n,status='pass',wave_sha256=hashlib.sha256(wave.read_bytes()).hexdigest()));assert wave.resolve().is_relative_to(OUT.resolve());wave.unlink()
 print('PASS',tb.stem,flush=True)
 (OUT/'SUMMARY.json').write_text(json.dumps(dict(status='running',cases=rows),indent=2)+'\n',encoding='utf-8')
(OUT/'SUMMARY.json').write_text(json.dumps(dict(status='passed',head='5bfb221544daca8c345773a4741c30d2712f75ba',cases=rows,replays=len(rows),transactions=sum(x['transactions'] for x in rows),scope='unchanged archived v2 RTL/bench/fixtures with hashes bound to published source'),indent=2)+'\n',encoding='utf-8');print('ALL PASS',len(rows),sum(x['transactions'] for x in rows),flush=True)
