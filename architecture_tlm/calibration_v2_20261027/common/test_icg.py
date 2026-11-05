"""Portable ICG functional/guard checks; no cell timing or power claims."""
import argparse, hashlib, importlib.util, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
 p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');p.add_argument('--ivl')
 a=p.parse_args();out=a.output.resolve()
 if a.ivl: a.ivl=str(Path(a.ivl).resolve())
 if out.exists(): raise SystemExit('Use a new output directory')
 out.mkdir(parents=True)
 spec=importlib.util.spec_from_file_location('mapping',ROOT/'make_icg_mapping.py')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 cfg=dict(cell='test_library_cell',clock_pin='CK',enable_pin='E',test_enable_pin='TE',output_pin='Q')
 (out/'mapping.sv').write_text(m.generate(cfg),encoding='utf-8')
 # This stub tests pin mapping only. It is NOT a real ICG library/PPA model.
 (out/'fake_library.sv').write_text('module test_library_cell(input CK,E,TE,output Q);reg q;always @* if(!CK) q<=E|TE;assign Q=CK&q;endmodule\n',encoding='utf-8')
 bad=0
 for config in [dict(cfg,cell='FILL_CELL'),dict(cfg,enable_pin='CK'),dict(cfg,cell='bad;code')]:
  try: m.generate(config)
  except ValueError: bad+=1
 assert bad==3
 bench='`timescale 1ns/1ps\nmodule tb;\n reg clk=0,en=0,te=0;wire g0,g1,g2;\n pbit_icg #(.GATE_MODE(0)) a(clk,en,te,g0);\n pbit_icg #(.GATE_MODE(1)) b(clk,en,te,g1);\n pbit_icg #(.GATE_MODE(2)) c(clk,en,te,g2);\n task check(input expected);\n begin #1;if(g0!==clk || g1!==expected || g2!==expected)$fatal(1,"clock mismatch");end endtask\n initial begin\n  #1;check(0);clk=1;check(0);\n  en=1;check(0); // enable rising during high phase must NOT create clock edge\n  clk=0;check(0);clk=1;check(1);\n  en=0;check(1); // enable falling during high phase must NOT truncate pulse\n  clk=0;check(0);clk=1;check(0);\n  te=1;check(0);clk=0;check(0);clk=1;check(1);\n  te=0;check(1);clk=0;check(0);clk=1;check(0);\n  clk=0;en=1;check(0);clk=1;check(1);\n  $display("PASS ICG functional mapping and phase checks");$finish;\n end\nendmodule\n'
 (out/'tb.sv').write_text(bench,encoding='utf-8')
 cmd=[a.iverilog]+(['-B',a.ivl] if a.ivl else [])+['-g2012','-DPB_ICG_TECH_MAPPED','-s','tb','-o',str(out/'sim.vvp'),str(ROOT/'pbit_icg.sv'),str(out/'mapping.sv'),str(out/'fake_library.sv'),str(out/'tb.sv')]
 def run(cmd):
  q=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
  return q.returncode,q.stdout+q.stderr
 rc,log=run(cmd);assert rc==0,log
 rc,sim=run([a.vvp]+(['-M',a.ivl] if a.ivl else [])+[str(out/'sim.vvp')]);assert rc==0 and 'PASS ICG' in sim,sim
 (out/'functional.log').write_text(log+sim,encoding='utf-8')
 guards=[]
 for mode,defs in [(1,['-DSYNTHESIS']),(2,[])]:
  (out/'guard.sv').write_text(f'module tb;wire q;pbit_icg #(.GATE_MODE({mode})) dut(1\'b0,1\'b0,1\'b0,q);endmodule\n',encoding='utf-8')
  rc,glog=run([a.iverilog]+(['-B',a.ivl] if a.ivl else [])+['-g2012',*defs,'-s','tb','-o',str(out/'guard.vvp'),str(ROOT/'pbit_icg.sv'),str(out/'guard.sv')])
  assert rc!=0 and 'ERROR_' in glog,glog
  guards.append(dict(mode=mode,expected_elaboration_failure=True))
 summary=dict(status='pass',test='functional_icg_and_fail_closed_mapping',mapping_rejections=bad,guards=guards,
  functional_library_is_stub=True,technology_validation=False,ppa=False,
  source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'pbit_icg.sv',ROOT/'make_icg_mapping.py',Path(__file__)]})
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(summary))
if __name__=='__main__': main()
