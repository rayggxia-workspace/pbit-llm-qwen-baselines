"""Fixed-top combinational and sequential microbenchmark DC/VCS/PT flow."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil
import upstream as U
from power_vcd import scalarize
from power_parse import parse
from vcd_alias_v2 import normalize
ROOT=Path(__file__).resolve().parents[1];FLOW=ROOT/'flow'
U.ROOT=ROOT;U.FLOW=FLOW;U.sources=lambda:[ROOT/'rtl/primitives.sv',ROOT/'rtl/tops.sv']
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def replay(binary,folder,c,seed,env=None):
 folder.mkdir();source=ROOT/'fixtures'/c['name']/str(seed)
 for n in ('stim.hex','expect.hex','WINDOWS.json'):shutil.copyfile(source/n,folder/n)
 U.run([binary],folder,'simulation.log',env)
 s=(folder/'simulation.log').read_text()
 if 'FUNCTION_PASS' not in s or re.search(r'(?:Fatal|Error|Warning:.*timing)',s):raise RuntimeError('Functional replay failed')
 r=json.loads((folder/'WINDOWS.json').read_text());r['status']='pass';r['VCD_sha256']=U.sha(folder/'activity.vcd');save(folder/'REPLAY.json',r);return r
def complete_ties(pt,audit,netlist,top):
 # New benchmark outputs may have a directly tied low bit from fixed <<1.
 # Extend only that top-output proof; never waive leaf-cell activity.
 import csv
 path=pt/'output_activity.tsv';raw=path.read_bytes()
 with path.open() as f:rows=list(csv.DictReader(f,delimiter='\t'))
 proofs=[];source=netlist.read_text();z=re.search(r'\bmodule\s+'+re.escape(top)+r'\b(.*?)\bendmodule',source,re.S)
 if z is None:raise ValueError('Mapped top missing')
 for row in rows:
  if row['toggle_rate']!='NA' and row['static_probability']!='NA':continue
  name=row['name'];m=re.fullmatch(r'dout\[(\d+)\]',name)
  if not m:raise ValueError('Unproved absent activity '+name)
  expr=r'\bassign\s+dout\s*\[\s*'+m[1]+r'\s*\]\s*=\s*1\x27[bBhH]([01])\s*;'
  tie=re.search(expr,z[1]);e=audit['expected_activity'][name]
  if tie is None or e['toggle_rate_per_ns']!=0 or e['static_probability']!=int(tie[1]):raise ValueError('Constant output not proved '+name)
  row['toggle_rate']='0';row['static_probability']=str(int(tie[1]));proofs.append({'port':name,'assignment':tie[0],'mapped_sha256':U.sha(netlist),'VCD':e})
 if proofs:
  (pt/'output_activity.unmodified.tsv').write_bytes(raw)
  with path.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['name','toggle_rate','static_probability'],delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
  save(pt/'CONSTANT_OUTPUT_PROOFS.json',{'proofs':proofs,'leaf_pins_relaxed':0})
 return proofs
def functional(out,c):
 out.mkdir(parents=True);r={'status':'running','case':c,'replays':[]};save(out/'RESULT.json',r)
 try:
  U.run(['vcs','-full64','-sverilog','-debug_access+all','-debug_region+cell+lib','+nospecify','+notimingcheck','-top','tb','-o',out/'simv',*U.sources(),ROOT/'benches'/(c['name']+'.sv')],out,'compile.log')
  for seed in (17,503,1009):
   rr=replay(out/'simv',out/str(seed),c,seed);r['replays'].append({'seed':seed,'transactions':rr['transactions'],'status':'pass'});save(out/'RESULT.json',r)
  r['status']='pass'
 except Exception as e:r['status']='failed';r['error']=str(e);raise
 finally:save(out/'RESULT.json',r);U.archive(out)
def ppa(out,c):
 out.mkdir(parents=True);top='me_'+c['name'];r={'status':'running','case':c,'top':top,'windows':[]};save(out/'RESULT.json',r)
 env=os.environ.copy();binding=json.loads(Path(env['MATRIX_PRIVATE_LIBRARY']).read_text());cfg=out/'configuration.tcl';cfg.write_text(U.config(top,binding['db']))
 env.update(CV2_FLOW=str(FLOW),CV2_CONFIG=str(cfg))
 try:
  synth=out/'synthesis';synth.mkdir();U.run(['dc_shell','-f',FLOW/'dc.tcl'],synth,'dc.log',env)
  if not (synth/'STAGE_COMPLETE').is_file():raise RuntimeError('DC marker missing')
  r['mapped_sha256']=U.sha(synth/'mapped.v');r['raw_area_um2']=float((synth/'area_library_units.txt').read_text());r['area_55eq_um2']=.81*r['raw_area_um2']
  env.update(CV2_NETLIST=str(synth/'mapped.v'),CV2_BOUNDARY_ONLY='1')
  bound=out/'boundary';bound.mkdir();U.run(['pt_shell','-f',FLOW/'power_bulk.tcl'],bound,'pt.log',env)
  comp=out/'gate_compile';comp.mkdir();U.run(['vcs','-full64','-sverilog','-debug_access+all','-debug_region+cell+lib','+nospecify','+notimingcheck','-top','tb','-o',comp/'simv',binding['model'],synth/'mapped.v',ROOT/'benches'/(c['name']+'.sv')],comp,'compile.log',env)
  for seed in (17,503,1009):
   gate=out/('gate_'+str(seed));rr=replay(comp/'simv',gate,c,seed,env)
   for w in rr['windows']:
    d=out/(w['mode']+'_'+str(seed));d.mkdir();prefix='tb/dut/';names={prefix+n for n in (bound/'activity_boundary.txt').read_text().splitlines()}
    U.window(gate/'activity.vcd',d/'window.raw.vcd',w['start_ns'],w['end_ns'])
    proof=normalize(d/'window.raw.vcd',d/'window.unique.vcd',required_names=names)
    audit=scalarize(d/'window.unique.vcd',d/'window.vcd',1,'unused',required_names=names,scope_prefix=prefix);audit['duplicate_alias_proof']=proof;save(d/'wave_audit.json',audit)
    pt=d/'pt';pt.mkdir();pe=dict(env,CV2_BOUNDARY_ONLY='0',CV2_VCD=str(d/'window.vcd'),CV2_STRIP_PATH='tb/dut');U.run(['pt_shell','-f',FLOW/'power_bulk.tcl'],pt,'pt.log',pe)
    const=complete_ties(pt,audit,synth/'mapped.v',top);duration=w['end_ns']-w['start_ns']
    meta={'core':top,'seed':seed,'mode':w['mode'],'duration_ns':duration,'operations':w['operations'],'accepted_samples':0,'measurement_cycles':round(duration/10)}
    row=parse(pt,meta,audit);row.update(area_55eq_um2=.81*row['area_um2'],constant_top_output_proofs=const,
     operation_definition='one combinational evaluation' if c['family'] not in ('acc','plane','bank') else 'one32-sample frame including reset/control',
     boundary='Only named mapped microbenchmark; no artificial input/output flops for combinational cases. No SRAM/RNG/comparator/CTS/SDF/SPEF.')
    save(d/'RESULT.json',row);r['windows'].append(row);save(out/'RESULT.json',r);print('WINDOW',c['name'],seed,w['mode'],row['total_W'],flush=True)
  r['status']='calculated'
 except Exception as e:r['status']='failed';r['error']=str(e);raise
 finally:save(out/'RESULT.json',r);U.archive(out)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('stage',choices=['functional','ppa']);a.add_argument('--case',type=int,required=True);a.add_argument('--out',type=Path,required=True);z=a.parse_args();c=json.loads((ROOT/'CASES.json').read_text())[z.case]
 (functional if z.stage=='functional' else ppa)(z.out.resolve(),c)
