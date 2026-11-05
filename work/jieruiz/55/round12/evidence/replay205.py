from pathlib import Path
import subprocess,json,re,hashlib,shutil
A=Path(__file__).resolve().parent;BASE=A.parent.parent;R=BASE/'pbit-llm-qwen-baselines';H='9f762ced3d25b47bf3963fbf38ff8d321850854b';PREFIX='architecture_tlm/matrix_single_scale_20261028/'
OUT=A/'rtl205';SRC=OUT/'source';SRC.mkdir(parents=True,exist_ok=True);iv=BASE/'sc_weight_storage_or4_20261014/tools/iverilog'
paths=subprocess.check_output(['git','-C',str(R),'ls-tree','-r','--name-only',H,PREFIX]).decode().splitlines();sources={}
for p in paths:
 rel=p[len(PREFIX):]
 if not rel.startswith(('rtl/','benches/','fixtures/')):continue
 b=subprocess.check_output(['git','-C',str(R),'show',H+':'+p]);f=SRC/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b);sources[rel]=hashlib.sha256(b).hexdigest()
rows=json.loads((OUT/'SUMMARY.json').read_text())['cases'] if (OUT/'SUMMARY.json').exists() else []
def run(cmd,cwd,log):
 p=subprocess.run(list(map(str,cmd)),cwd=cwd,capture_output=True,timeout=180);(cwd/log).write_bytes(p.stdout+p.stderr);assert p.returncode==0,(cwd,log);return p.stdout.decode()
for tb in sorted((SRC/'benches').glob('*stress1.sv')):
 if tb.name=='m8_mode0_stress1.sv':continue
 if sum(x['bench']==tb.name for x in rows)==3:continue
 m=int(re.search(r'm(1|8)_',tb.name)[1]);d=OUT/tb.stem;d.mkdir();exe=d/'sim.vvp'
 run([iv/'bin/iverilog.exe','-B',iv/'lib/ivl','-g2012','-s','tb','-o',exe,*sorted((SRC/'rtl').glob('*.sv')),tb],d,'compile.log')
 for seed in [17,503,1009]:
  f=d/str(seed);f.mkdir()
  for q in (SRC/'fixtures'/f'm{m}_s{seed}').glob('*.hex'):shutil.copyfile(q,f/q.name)
  log=run([iv/'bin/vvp.exe','-M',iv/'lib/ivl',exe],f,'simulation.log');assert 'FUNCTION_PASS' in log;assert len(re.findall(r'^FRAME ',log,re.M))==16
  wave=f/'activity.vcd';receipt=dict(bench=tb.name,seed=seed,frames=16,status='pass',vcd_sha256=hashlib.sha256(wave.read_bytes()).hexdigest(),vcd_bytes=wave.stat().st_size)
  # Only replay-generated waveforms, after hashing; original experiment evidence is untouched.
  assert wave.resolve().is_relative_to(OUT.resolve());wave.unlink();rows.append(receipt)
 print('PASS',tb.name,flush=True)
 (OUT/'SUMMARY.json').write_text(json.dumps(dict(head=H,status='running',source_sha256=sources,cases=rows),indent=2)+'\n',encoding='utf-8')
(OUT/'SUMMARY.json').write_text(json.dumps(dict(head=H,status='passed_with_limitations',source_sha256=sources,cases=rows,frames=sum(x['frames'] for x in rows),limitation='M8 mode0 seed17 timed out after180s with time advancing to3175ns; three M8 mode0 seeds not locally completed. Original VCS complete evidence independently hashed.',scope='unchanged published DUT/bench/fixtures; Icarus replay only, no PPA'),indent=2)+'\n',encoding='utf-8');print('PASS WITH LIMITATION',len(rows),sum(x['frames'] for x in rows),flush=True)
