"""Immutable Slurm execution: RTL preflight, then synthesis and gate/PT replay."""
import os,json,subprocess,re,hashlib
from pathlib import Path
S=Path(os.environ['P8_SOURCE']);R=Path(os.environ['P8_RESULTS'])
STAGE=os.environ['P8_STAGE']
C=json.loads((S/'CASES.json').read_text())[int(os.environ.get('SLURM_ARRAY_TASK_ID','0'))]
T=C['top'];D=R/(STAGE+'_'+T)
def save(p,x):p.write_bytes((json.dumps(x,indent=2)+'\n').encode())
def call(args,d,log):
 with (d/log).open('w') as f:p=subprocess.run(args,cwd=str(d),stdout=f,stderr=subprocess.STDOUT)
 if p.returncode:raise RuntimeError('%s failed: %s'%(args[0],d/log))
def compile_sim(phase):
 d=D/phase;d.mkdir()
 inputs=[str(S/'tb.sv')]
 if phase=='rtl':inputs += [str(S/'design.sv'),str(S/'rng_bivium_map.sv'),str(S/(T+'.sv'))]
 else:inputs += [os.environ['P8_NETLIST'],os.environ['P8_MODEL']]
 call(['vcs','-full64','-sverilog','-timescale=1ns/1ps','+notimingcheck','-debug_access+all','-top','tb','-o','simv',
       '+incdir+'+str(S),'+define+TOP='+T,'+define+LANES='+str(C['lanes']),'+define+MODE='+str(C['mode'])]+inputs,d,'compile.log')
 return d
def replay(d,seed,stall):
 f=S/'fixtures';p=d/('s%d_stall%d'%(seed,stall));p.mkdir()
 call([str(d/'simv'),'+INPUT='+str(f/('score%d.mem'%seed)),
       '+EXPECT='+str(f/('expect_m%d_s%d.mem'%(C['mode'],seed))),'+SEEDS='+str(f/('seed%d.mem'%seed)),
       '+FLAGS='+str(f/('flags%d.mem'%seed)),'+STALL='+str(stall)],p,'sim.log')
 log=(p/'sim.log').read_text();assert 'PASS checked=1024 queries=8' in log
 return p,log
def main():
 D.mkdir(exist_ok=False);checks=[];windows=[]
 if STAGE=='preflight':
  d=compile_sim('rtl')
  for seed,stall in [(17,0),(503,0),(1009,0),(17,1)]:
   p,log=replay(d,seed,stall);checks.append(dict(seed=seed,stall=stall,log=log))
 elif STAGE=='ppa':
  assert (R/('preflight_'+T)/'COMPLETE.json').exists()
  os.environ.update(P8_TOP=T)
  if os.environ.get('P8_REUSE_DC'):
   dc=Path(os.environ['P8_REUSE_DC'])/('ppa_'+T)/'dc';assert (dc/'DC_COMPLETE').exists()
  else:
   dc=D/'dc';dc.mkdir();call(['dc_shell','-f',str(S/'dc.tcl')],dc,'dc.log');assert (dc/'DC_COMPLETE').exists()
  os.environ.update(P8_NETLIST=str(dc/'mapped.v'),P8_SDC=str(dc/'mapped.sdc'))
  d=compile_sim('gate')
  for seed,stall in [(17,0),(503,0),(1009,0),(17,1)]:
   p,log=replay(d,seed,stall);checks.append(dict(seed=seed,stall=stall,log=log))
   if not stall:
    for name,start,end in re.findall(r'WINDOW (\w+) (\d+) (\d+)',log):
     pt=p/name;pt.mkdir();os.environ.update(P8_VCD=str(p/'activity.vcd'),P8_START=start,P8_END=end)
     call(['pt_shell','-f',str(S/'pt.tcl')],pt,'pt.log');assert (pt/'PT_COMPLETE').exists()
     windows.append(dict(seed=seed,window=name,start_ns=int(start),end_ns=int(end),path=str(pt.relative_to(R))))
     save(D/'PROGRESS.json',dict(checks=checks,windows=windows))
 else:raise ValueError(STAGE)
 result=dict(case=C,checks=checks,windows=windows,source_sha256=hashlib.sha256((S/'SOURCE.json').read_bytes()).hexdigest())
 if STAGE=='ppa':result.update(dc_reference=str(dc),netlist_sha256=hashlib.sha256((dc/'mapped.v').read_bytes()).hexdigest(),sdc_sha256=hashlib.sha256((dc/'mapped.sdc').read_bytes()).hexdigest(),reused_synthesis=bool(os.environ.get('P8_REUSE_DC')))
 save(D/'COMPLETE.json',result)
if __name__=='__main__':
 try:main()
 except Exception as e:
  if D.exists():save(D/'FAILURE.json',dict(error=str(e)))
  raise
