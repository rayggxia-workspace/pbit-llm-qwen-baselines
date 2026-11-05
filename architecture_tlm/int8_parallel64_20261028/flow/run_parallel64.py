"""RTL/gate/strict PT characterization of complete signed INT8 N64 frames."""
from pathlib import Path
import argparse,json,os,re,shutil
import upstream as U
from power_vcd import scalarize
from power_parse import parse
from vcd_alias_v2 import normalize
from constant_ports import complete
ROOT=Path(__file__).resolve().parents[1];FLOW=ROOT/'flow';U.ROOT=ROOT;U.FLOW=FLOW
def sources():return [ROOT/'rtl/par64.sv']
U.sources=sources
def save(p,x):Path(p).write_bytes((json.dumps(x,indent=2)+'\n').encode())
def replay(binary,d,c,seed):
 d.mkdir()
 for n in ['stim.hex','expect.hex','WINDOWS.json']:shutil.copyfile(ROOT/'fixtures'/c['name']/str(seed)/n,d/n)
 U.run([binary],d,'simulation.log');s=(d/'simulation.log').read_text()
 if 'FUNCTION_PASS transactions=164' not in s or re.search(r'(?:Fatal|Error|Warning:.*timing)',s):raise RuntimeError('Replay failed '+str(d))
 rr=json.loads((d/'WINDOWS.json').read_text());dynamic=re.findall(r'^WINDOW (\w+) (\d+) (\d+) (\d+)$',s,re.M)
 if len(dynamic)!=4:raise RuntimeError('Wrong window count')
 rr['windows']=[dict(mode=m,start_ns=int(st),end_ns=int(en),operations=int(n),accepted_samples=int(n)*64,measurement_cycles=(int(en)-int(st))/10) for m,st,en,n in dynamic]
 rr['frame_cycles']=[list(map(int,x)) for x in re.findall(r'^FRAME_CYCLES (\d+) (\d+)$',s,re.M)]
 if rr['frame_cycles']:raise RuntimeError('Unexpected temporal frame log')
 rr['VCD_sha256']=U.sha(d/'activity.vcd');save(d/'REPLAY.json',rr);return rr
def main(stage,index,out,reuse=None):
 c=json.loads((ROOT/'CASES.json').read_text())[index];out.mkdir(parents=True,exist_ok=False)
 r=dict(status='running',case=c,stage=stage,windows=[],functional=[]);save(out/'RESULT.json',r)
 try:
  flags=['vcs','-full64','-sverilog','-timescale=1ns/1ps','+define+SYNTHESIS','-debug_access+all','-debug_region+cell+lib','+nospecify','+notimingcheck','-top','tb']
  if stage=='functional':
   U.run(flags+['-o',out/'simv']+sources()+[ROOT/'benches'/(c['name']+'.sv')],out,'compile.log')
   for seed in (17,503,1009):
    x=replay(out/'simv',out/str(seed),c,seed);r['functional'].append(dict(seed=seed,transactions=x['transactions'],latency_cycles=x['logical_latency_cycles'],initiation_interval_cycles=x['initiation_interval_cycles'],passed=True))
   r['status']='pass';return
  binding=json.loads(Path(os.environ['MATRIX_PRIVATE_LIBRARY']).read_text());env=os.environ.copy();cfg=U.config('i8_'+c['name'],binding['db'])
  (out/'configuration.tcl').write_bytes(cfg.encode());env.update(CV2_CONFIG=str(out/'configuration.tcl'),CV2_FLOW=str(FLOW))
  if reuse is not None:
   prior=reuse.parents[1];m=json.loads((prior/'EXECUTION_MANIFEST.json').read_text());old=json.loads((reuse/'RESULT.json').read_text());checked={}
   for n,h in m['files'].items():
    if n in ('flow/dc.tcl','flow/run_parallel64.py'):continue
    if U.sha(ROOT/n)!=h or U.sha(prior/n)!=h:raise RuntimeError('Reuse input mismatch '+n)
    checked[n]=h
   if json.loads((prior/'private_library.json').read_text())!=binding:raise RuntimeError('Reuse library binding mismatch')
   if (reuse/'configuration.tcl').read_text().replace(str(prior),str(ROOT))!=cfg:raise RuntimeError('Reuse config mismatch')
   net=reuse/'synthesis/mapped.v'
   if U.sha(net)!=old['mapped_sha256']:raise RuntimeError('Reuse netlist mismatch')
   env['PAR64_REUSE_NETLIST']=str(net)
   save(out/'REUSED_SYNTH.json',dict(from_result=str(reuse),source_netlist_sha256=U.sha(net),prior_manifest_sha256=U.sha(prior/'EXECUTION_MANIFEST.json'),verified_inputs=checked,library_binding_equal=True,configuration_equal_after_path_normalization=True,purpose='DC native hold-only optimization; no fresh RTL compile/retime'))
  sy=out/'synthesis';sy.mkdir();U.run(['dc_shell','-f',FLOW/'dc.tcl'],sy,'dc.log',env)
  if not (sy/'STAGE_COMPLETE').is_file():raise RuntimeError('DC not complete')
  r.update(raw_area_um2=float((sy/'area_library_units.txt').read_text()),mapped_sha256=U.sha(sy/'mapped.v'));r['area_55eq_um2']=.81*r['raw_area_um2'];save(out/'RESULT.json',r)
  env.update(CV2_NETLIST=str(sy/'mapped.v'),CV2_BOUNDARY_ONLY='1');boundary=out/'boundary';boundary.mkdir();U.run(['pt_shell','-f',FLOW/'power_bulk.tcl'],boundary,'pt.log',env)
  gc=out/'gate_compile';gc.mkdir();U.run(flags+['-o',gc/'simv',binding['model'],sy/'mapped.v',ROOT/'benches'/(c['name']+'.sv')],gc,'compile.log',env)
  for seed in (17,503,1009):
   gate=out/('gate_'+str(seed));rr=replay(gc/'simv',gate,c,seed)
   for w in rr['windows']:
    d=out/(w['mode']+'_'+str(seed));d.mkdir();names={'tb/dut/'+n for n in (boundary/'activity_boundary.txt').read_text().splitlines()}
    U.window(gate/'activity.vcd',d/'window.raw.vcd',w['start_ns'],w['end_ns']);proof=normalize(d/'window.raw.vcd',d/'window.unique.vcd',required_names=names)
    audit=scalarize(d/'window.unique.vcd',d/'window.vcd',1,'unused',required_names=names,scope_prefix='tb/dut/');audit['duplicate_alias_proof']=proof;save(d/'wave_audit.json',audit)
    pt=d/'pt';pt.mkdir();pe=dict(env,CV2_BOUNDARY_ONLY='0',CV2_VCD=str(d/'window.vcd'),CV2_STRIP_PATH='tb/dut');U.run(['pt_shell','-f',FLOW/'power_bulk.tcl'],pt,'pt.log',pe)
    complete(pt,audit,sy/'mapped.v','i8_'+c['name'])
    meta=dict(core='i8_'+c['name'],seed=seed,mode=w['mode'],duration_ns=w['end_ns']-w['start_ns'],operations=w['operations'],accepted_samples=w['accepted_samples'],measurement_cycles=w['measurement_cycles'])
    q=parse(pt,meta,audit);q.update(area_55eq_um2=.81*q['area_um2'],operation_definition='one complete N64 dot product / one output, including the full measured workload cadence',latency_cycles=rr['logical_latency_cycles'],initiation_interval_cycles=rr['initiation_interval_cycles'],compile='verified mapped reuse; set_fix_hold core; compile -incremental_mapping -only_hold_time',boundary='64 parallel signedINT8 multipliers, balanced exact reduction, registered output/valid; no temporal multiplier sharing; external operand delivery and all SRAM/RNG/CTS/SDF/SPEF excluded')
    r['windows'].append(q);save(d/'RESULT.json',q);save(out/'RESULT.json',r);print('WINDOW',c['name'],seed,w['mode'],q['total_W'],flush=True)
  r['status']='calculated'
 except Exception as e:r['status']='failed';r['error']=str(e);raise
 finally:save(out/'RESULT.json',r);U.archive(out)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage');p.add_argument('--case',type=int,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--reuse',type=Path);a=p.parse_args();main(a.stage,a.case,a.out.resolve(),a.reuse.resolve() if a.reuse else None)
