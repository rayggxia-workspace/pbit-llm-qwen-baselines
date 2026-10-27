"""Check fixed-top power stimulus and event windows; never a technology/PPA test."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main(a):
 out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
 icg=Path(a.icg).resolve();ivl=str(Path(a.ivl).resolve()) if a.ivl else None
 mock=out/'FUNCTIONAL_ONLY_mock_icg.sv'
 mock.write_text('module pbit_icg_tech(input clk,en,test_en,output gclk);reg hold_en;always @* if(!clk)hold_en<=en|test_en;assign gclk=clk & hold_en;endmodule\n',encoding='ascii')
 results=[]
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
    name=f'{mode}_{period}ns';sub=folder/name;sub.mkdir()
    cmd=[a.vvp]+(['-M',ivl]if ivl else[])+[str(exe),f'+MODE={mode}',f'+PERIOD_NS={period}','+SEED=17','+P8=128','+FRAMES=2','+VCD=activity.vcd']
    z=subprocess.run(cmd,cwd=sub,capture_output=True,text=True,timeout=180)
    (sub/'simulation.log').write_text(z.stdout+z.stderr,encoding='utf-8')
    if z.returncode or 'PASS counter_power'not in z.stdout:raise RuntimeError(z.stdout+z.stderr)
    w=re.search(r'WINDOW start_ns=([0-9.]+) end_ns=([0-9.]+) frames=(\d+) accepted_samples=(\d+)',z.stdout)
    assert w and float(w[2])>float(w[1]);frames,samples=int(w[3]),int(w[4]);assert frames==(0 if mode=='idle' else 2) and samples==frames*t
    results.append(dict(top=top,gate_mode=g,mock_tech_for_functional_only=g==2,period_ns=period,mode=mode,start_ns=float(w[1]),end_ns=float(w[2]),frames=frames,accepted_samples=samples,vcd_bytes=(sub/'activity.vcd').stat().st_size,vcd_sha256=hashlib.sha256((sub/'activity.vcd').read_bytes()).hexdigest(),status='passed'))
    print(top,name,'PASS',flush=True)
 # All 16 fixed tops elaborate as synthesizable designs with a FUNCTIONAL mock binding.
 for case in json.loads((ROOT/'cases.json').read_text(encoding='utf-8')):
  top=case['top'];target=out/(top+'.elab.vvp')
  cmd=[a.iverilog]+(['-B',ivl]if ivl else[])+['-g2012','-DSYNTHESIS','-DPB_ICG_TECH_MAPPED','-s',top,'-o',str(target),str(icg),str(ROOT/'rtl/sc_counter_merged.sv'),str(ROOT/'rtl/counter_tops.sv'),str(mock)]
  c=subprocess.run(cmd,cwd=out,capture_output=True,text=True,timeout=180)
  if c.returncode:raise RuntimeError(c.stdout+c.stderr)
  target.unlink()
 report=dict(status='passed',kind='RTL fixed-top power-bench and declaration check, not STA/PPA',windows=results,fixed_tops_elaborated=16,source_sha256={str(x.relative_to(ROOT)) if x.is_relative_to(ROOT)else'common/pbit_icg.sv':hashlib.sha256(x.read_bytes()).hexdigest() for x in [ROOT/'rtl/sc_counter_merged.sv',ROOT/'rtl/counter_tops.sv',ROOT/'tests/tb_counter_power.sv',Path(__file__),icg]})
 (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print('PASS windows',len(results),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--icg',required=True);p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');p.add_argument('--ivl');main(p.parse_args())
