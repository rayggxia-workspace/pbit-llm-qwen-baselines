"""Check fixed-top power stimulus and windows; not a technology/PPA test."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main(a):
 out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
 icg=Path(a.icg).resolve();ivl=str(Path(a.ivl).resolve()) if a.ivl else None
 mock=out/'FUNCTIONAL_ONLY_mock_icg.sv'
 mock.write_text('module pbit_icg_tech(input clk,en,test_en,output gclk);reg hold_en;always @* if(!clk)hold_en<=en|test_en;assign gclk=clk & hold_en;endmodule\n',encoding='ascii')
 results=[];profiles=[]
 for bins,t,m,p,g,aw in [(4,64,1,1,0,26),(7,128,8,2,2,33)]:
  top=f'counter_b{bins}_t{t}_m{m}_p{p}_g{g}'
  folder=out/top;folder.mkdir();exe=folder/'sim.vvp'
  defs=[f'-DDUT_TOP={top}',f'-DDUT_M={m}',f'-DDUT_BINS={bins}',f'-DDUT_T={t}',f'-DDUT_AW={aw}']
  if g==2:defs+=['-DPB_ICG_TECH_MAPPED']
  cmd=[a.iverilog]+(['-B',ivl]if ivl else[])+['-g2012','-s','tb_counter_power',*defs,'-o',str(exe),str(icg),str(ROOT/'rtl/sc_counter_merged.sv'),str(ROOT/'rtl/counter_tops.sv'),str(ROOT/'tests/tb_counter_power.sv')]+([str(mock)]if g==2 else[])
  c=subprocess.run(cmd,cwd=folder,capture_output=True,text=True,timeout=180)
  (folder/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
  if c.returncode:raise RuntimeError(c.stdout+c.stderr)
  for period in [10,2]:
   for mode in ['continuous','sparse','idle','wake','stall']:
    sub=folder/f'{mode}_{period}ns';sub.mkdir()
    cmd=[a.vvp]+(['-M',ivl]if ivl else[])+[str(exe),f'+MODE={mode}',f'+PERIOD_NS={period}','+SEED=17','+P8=128','+FRAMES=2','+VCD=activity.vcd']
    z=subprocess.run(cmd,cwd=sub,capture_output=True,text=True,timeout=180)
    (sub/'simulation.log').write_text(z.stdout+z.stderr,encoding='utf-8')
    if z.returncode or 'PASS counter_power'not in z.stdout or 'FATAL' in z.stdout:raise RuntimeError(z.stdout+z.stderr)
    w=re.search(r'WINDOW start_ns=([0-9.]+) end_ns=([0-9.]+) frames=(\d+) accepted_samples=(\d+)',z.stdout)
    assert w and float(w[2])>float(w[1]);frames,samples=int(w[3]),int(w[4]);assert frames==(0 if mode=='idle' else 2) and samples==frames*t
    th=sub/'thresholds_used.hex';vals=[int(v,16) for v in th.read_text().splitlines() if not v.startswith('//')];assert len(vals)==64 and min(vals)==64 and max(vals)==192 and len(set(vals))==64
    results.append(dict(top=top,gate_mode=g,mock_tech_for_functional_only=g==2,period_ns=period,mode=mode,start_ns=float(w[1]),end_ns=float(w[2]),frames=frames,accepted_samples=samples,threshold_profile='swept',threshold_seed=193,thresholds=vals,thresholds_sha256=hashlib.sha256(th.read_bytes()).hexdigest(),vcd_bytes=(sub/'activity.vcd').stat().st_size,vcd_sha256=hashlib.sha256((sub/'activity.vcd').read_bytes()).hexdigest(),status='passed'))
    print(top,mode,period,'PASS',flush=True)
  if g==0:
   for profile in ['uniform','file','file_invalid']:
    sub=folder/profile;sub.mkdir();extra=['+THRESHOLD_PROFILE=uniform']
    if profile.startswith('file'):
     vals=[i*256//63 for i in range(64)];(sub/'input.hex').write_text(''.join(f'{x:x}\n' for x in (vals[:2]if profile=='file_invalid'else vals)),encoding='ascii');extra=['+THRESHOLD_FILE=input.hex']
    z=subprocess.run([a.vvp]+(['-M',ivl]if ivl else[])+[str(exe),'+MODE=continuous','+FRAMES=2','+VCD=activity.vcd',*extra],cwd=sub,capture_output=True,text=True,timeout=180)
    (sub/'simulation.log').write_text(z.stdout+z.stderr,encoding='utf-8')
    if profile=='file_invalid':
     # Some Windows vvp builds return zero after $fatal. Require the failure log and no PASS.
     assert 'FATAL' in z.stdout and 'invalid or missing lane threshold' in z.stdout and 'PASS counter_power'not in z.stdout
    else:
     assert z.returncode==0 and 'PASS counter_power'in z.stdout and 'FATAL'not in z.stdout
     actual=[int(v,16)for v in (sub/'thresholds_used.hex').read_text().splitlines()if not v.startswith('//')]
     assert actual==([128]*64 if profile=='uniform'else vals)
    profiles.append(dict(profile=profile,status='rejected_as_expected'if profile=='file_invalid'else'passed'))
 for case in json.loads((ROOT/'cases.json').read_text(encoding='utf-8')):
  top=case['top'];target=out/(top+'.elab.vvp')
  cmd=[a.iverilog]+(['-B',ivl]if ivl else[])+['-g2012','-DSYNTHESIS','-DPB_ICG_TECH_MAPPED','-s',top,'-o',str(target),str(icg),str(ROOT/'rtl/sc_counter_merged.sv'),str(ROOT/'rtl/counter_tops.sv'),str(mock)]
  c=subprocess.run(cmd,cwd=out,capture_output=True,text=True,timeout=180)
  if c.returncode:raise RuntimeError(c.stdout+c.stderr)
  target.unlink()
 report=dict(status='passed',kind='RTL fixed-top power-bench and declaration check, not STA/PPA',windows=results,profiles_checked=profiles,fixed_tops_elaborated=16,source_sha256={str(x.relative_to(ROOT)) if x.is_relative_to(ROOT)else'common/pbit_icg.sv':hashlib.sha256(x.read_bytes()).hexdigest() for x in [ROOT/'rtl/sc_counter_merged.sv',ROOT/'rtl/counter_tops.sv',ROOT/'tests/tb_counter_power.sv',Path(__file__),icg]})
 (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS windows',len(results),'profiles',len(profiles),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--icg',required=True);p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');p.add_argument('--ivl');main(p.parse_args())
