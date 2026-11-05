"""VCS functional / DC + gate replay + strict mapped-boundary PrimeTime flow."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,sys,tarfile
from power_vcd import scalarize
from power_parse import parse
from vcd_alias import normalize as normalize_aliases
ROOT=Path(__file__).resolve().parents[1];FLOW=ROOT/'flow'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def run(cmd,cwd,log,env=None):
 with (cwd/log).open('wb') as f:
  p=subprocess.run([str(x) for x in cmd],cwd=str(cwd),stdout=f,stderr=subprocess.STDOUT,env=env,timeout=3500)
 if p.returncode:raise RuntimeError('Failed '+str(cwd/log))
def sources():return [ROOT/'rtl'/n for n in ['pbit_icg.sv','sc_counter_merged.sv','matrix_variants.sv','tops.sv']]
def replay(sim,folder,m,seed,env=None):
 folder.mkdir(parents=True,exist_ok=False)
 for p in (ROOT/'fixtures'/('m%d_s%d'%(m,seed))).glob('*.hex'):shutil.copyfile(p,folder/p.name)
 run([sim],folder,'simulation.log',env)
 s=(folder/'simulation.log').read_text()
 if 'FUNCTION_PASS' not in s or re.search(r'(?:Fatal|Error|Warning:.*timing)',s):raise RuntimeError('Replay did not pass '+str(folder))
 frames=[list(map(int,z)) for z in re.findall(r'^FRAME (\d+) (\d+)$',s,re.M)]
 if len(frames)!=15:raise RuntimeError('Wrong frame count')
 windows=[{'mode':z[0],'start_ns':float(z[1]),'end_ns':float(z[2]),'operations':int(z[3])} for z in re.findall(r'^WINDOW (\w+) ([\d.]+) ([\d.]+) (\d+)$',s,re.M)]
 if len(windows)!=2:raise RuntimeError('Missing measurement windows')
 r={'status':'pass','frames':frames,'windows':windows,'VCD_sha256':sha(folder/'activity.vcd')}
 save(folder/'REPLAY.json',r);return r
def archive(out):
 # Reports only: no proprietary libraries, mapped netlist, waveform or binary.
 files=[p for p in out.rglob('*') if p.is_file() and p.suffix in ('.json','.log','.txt','.rpt','.tsv')
        and p.name not in ('library_private.rpt','RETURN_MANIFEST.json') and not any(x in p.parts for x in ('csrc','simv.daidir'))]
 save(out/'RETURN_MANIFEST.json',{'files':{str(p.relative_to(out)):sha(p) for p in files}})
 with tarfile.open(str(out/'reports.tar.gz'),'w:gz') as t:
  for p in files+[out/'RETURN_MANIFEST.json']:t.add(str(p),arcname=str(p.relative_to(out)))
def functional(out,m):
 out.mkdir(parents=True,exist_ok=False);r={'status':'running','M':m,'cases':[]};save(out/'RESULT.json',r)
 try:
  for mode in range(6):
   d=out/('mode%d'%mode);d.mkdir()
   run(['vcs','-full64','-sverilog','+nospecify','+notimingcheck','-top','tb','-o',d/'simv',*sources(),ROOT/'benches'/('m%d_mode%d_stress1.sv'%(m,mode))],d,'compile.log')
   for seed in (17,503,1009):
    x=replay(d/'simv',d/('seed%d'%seed),m,seed)
    r['cases'].append({'mode':mode,'M':m,'seed':seed,'frames':len(x['frames']),'status':'pass'})
    save(out/'RESULT.json',r)
   print('FUNCTIONAL_MODE_PASS',m,mode,flush=True)
  r['status']='pass'
 except Exception as e:r['status']='failed';r['error']=str(e);raise
 finally:save(out/'RESULT.json',r);archive(out)
def config(top,db):
 vals={'CV2_TOP':top,'CV2_LIBRARY_DB':db,'CV2_REF_CELL':'INVX1_9TSVT','CV2_CORNER':'ss',
   'CV2_CORNER_PATTERN':'ss|slow','CV2_VOLTAGE':1.08,'CV2_TEMPERATURE':125,'CV2_GATE_MODE':0,'CV2_ICG_CELL':'CKGTX8_9TSVT',
   'CV2_PERIOD_NS':10,'CV2_UNCERTAINTY_NS':0.5,'CV2_HOLD_UNCERTAINTY_NS':0.05,
   'CV2_CLOCK_TRANSITION_NS':0.05,'CV2_INPUT_TRANSITION_NS':0.05,'CV2_INPUT_DELAY_MAX_NS':1.,'CV2_INPUT_DELAY_MIN_NS':0.02,
   'CV2_OUTPUT_DELAY_MAX_NS':1.,'CV2_OUTPUT_DELAY_MIN_NS':0.02,'CV2_LOAD_PF':0.02}
 lines=['set %s {%s}'%(k,v) for k,v in vals.items()]
 lines+=['set CV2_RTL [list '+' '.join('{%s}'%p for p in sources())+']','set CV2_DEFINES [list SYNTHESIS]','set CV2_INCLUDE [list]']
 return '\n'.join(lines)+'\n'
def window(src,dst,start_ns,end_ns):
 with src.open() as f,dst.open('w') as out:
  header=[];scope=[];excluded_real=set()
  for line in f:
   tokens=line.split()
   if tokens[:1]==['$scope']:scope.append(tokens[2])
   elif tokens[:1]==['$upscope']:scope.pop()
   elif tokens[:2]==['$var','real']:
    name='/'.join(scope+[tokens[4]])
    if name.startswith('tb/dut/'):raise ValueError('Real-valued signal inside DUT '+name)
    excluded_real.add(tokens[3]);continue
   header.append(line)
   if '$enddefinitions' in line:break
  text=''.join(header);out.write(text)
  z=re.search(r'\$timescale\s*(\d+)\s*(s|ms|us|ns|ps|fs)\s*\$end',text)
  if not z:raise ValueError('VCD timescale')
  tick=int(z[1])*dict(s=1e9,ms=1e6,us=1e3,ns=1,ps=.001,fs=.000001)[z[2]]
  start=round(start_ns/tick);end=round(end_ns/tick);now=0;states={};opened=False
  for line in f:
   s=line.strip()
   if not s or s.startswith('$'):continue
   if s.startswith('#'):
    now=int(s[1:])
    if now>=start and not opened:
     out.write('#0\n'+'\n'.join(states.values())+'\n');opened=True
    if now>=end:break
    if opened:out.write('#%d\n'%(now-start))
   else:
    code=s.split()[-1] if s[0] in 'bBrR' else s[1:]
    if code in excluded_real:continue
    if not opened:states[code]=s
    else:out.write(s+'\n')
  if not opened:raise ValueError('Empty VCD window')
  out.write('#%d\n'%(end-start))
def ppa(out,mode,m=1,reuse=None):
 out.mkdir(parents=True,exist_ok=False);top='matrix_s%d_m%d'%(mode,m)
 r={'status':'running','top':top,'mode':mode,'M':m,'windows':[]};save(out/'RESULT.json',r)
 env=os.environ.copy();binding=json.loads(Path(env['MATRIX_PRIVATE_LIBRARY']).read_text())
 cfg=out/'configuration.tcl';cfg.write_text(config(top,binding['db']))
 env.update(CV2_FLOW=str(FLOW),CV2_CONFIG=str(cfg))
 try:
  if reuse is None:
   synth=out/'synthesis';synth.mkdir();run(['dc_shell','-f',FLOW/'dc.tcl'],synth,'dc.log',env)
  else:
   original=reuse.parents[1];manifest=json.loads((original/'EXECUTION_MANIFEST.json').read_text())
   for p in sources()+list((ROOT/'benches').glob('*.sv'))+list((ROOT/'fixtures').rglob('*.hex'))+[FLOW/x for x in ['common.tcl','library_conditions.tcl','dc.tcl','power_strict.tcl','power_vcd.py','power_parse.py']]:
    name=p.relative_to(ROOT).as_posix()
    if sha(p)!=manifest['files'][name] or sha(original/name)!=manifest['files'][name]:raise RuntimeError('Reuse input mismatch '+name)
   oldlib=json.loads((original/'private_library.json').read_text())
   if binding!=oldlib:raise RuntimeError('Reused library differs')
   if (reuse/'configuration.tcl').read_text().replace(str(original),str(ROOT))!=cfg.read_text():raise RuntimeError('Reused synthesis constraints differ')
   synth=reuse/'synthesis';old=json.loads((reuse/'RESULT.json').read_text())
   if old['mapped_netlist_sha256']!=sha(synth/'mapped.v'):raise RuntimeError('Reused netlist differs')
   save(out/'REUSED_SYNTH.json',{'from':str(reuse),'mapped_netlist_sha256':old['mapped_netlist_sha256'],
    'source_manifest_sha256':sha(original/'EXECUTION_MANIFEST.json'),'all_RTL_bench_fixture_constraint_inputs_verified':True})
  if not (synth/'STAGE_COMPLETE').exists():raise RuntimeError('DC marker missing')
  r['raw_area_um2']=float((synth/'area_library_units.txt').read_text());r['area_55eq_um2']=r['raw_area_um2']*.81
  r['area_multiplier']=.81;r['mapped_netlist_sha256']=sha(synth/'mapped.v')
  env.update(CV2_NETLIST=str(synth/'mapped.v'),CV2_BOUNDARY_ONLY='1')
  boundary=out/'boundary';boundary.mkdir();run(['pt_shell','-f',FLOW/'power_strict.tcl'],boundary,'pt.log',env)
  if not (boundary/'BOUNDARY_COMPLETE').exists():raise RuntimeError('PT boundary marker missing')
  comp=reuse/'gate_compile' if reuse else out/'gate_compile'
  if reuse is None:
   comp.mkdir()
   run(['vcs','-full64','-sverilog','+nospecify','+notimingcheck','-top','tb','-o',comp/'simv',
        binding['model'],synth/'mapped.v',ROOT/'benches'/('m%d_mode%d_stress0.sv'%(m,mode))],comp,'compile.log',env)
  for seed in (17,503,1009):
   prior=reuse/('gate_s%d'%seed) if reuse else None
   if prior and (prior/'REPLAY.json').is_file():
    rr=json.loads((prior/'REPLAY.json').read_text())
    if rr['status']!='pass' or rr['VCD_sha256']!=sha(prior/'activity.vcd'):raise RuntimeError('Reused replay mismatch')
    gate=prior
   else:
    gate=out/('gate_s%d'%seed);rr=replay(comp/'simv',gate,m,seed,env)
   for w in rr['windows']:
    d=out/('%s_s%d'%(w['mode'],seed));d.mkdir();prefix='tb/dut/'
    window(gate/'activity.vcd',d/'window.raw.vcd',w['start_ns'],w['end_ns'])
    alias_proof=normalize_aliases(d/'window.raw.vcd',d/'window.unique.vcd')
    names={prefix+n for n in (boundary/'activity_boundary.txt').read_text().splitlines()}
    audit=scalarize(d/'window.unique.vcd',d/'window.vcd',1,'unused',required_names=names,scope_prefix=prefix)
    audit['duplicate_alias_proof']=alias_proof
    save(d/'wave_audit.json',audit)
    pt=d/'pt';pt.mkdir();pe=dict(env,CV2_BOUNDARY_ONLY='0',CV2_VCD=str(d/'window.vcd'),CV2_STRIP_PATH='tb/dut')
    run(['pt_shell','-f',FLOW/'power_strict.tcl'],pt,'pt.log',pe)
    duration=w['end_ns']-w['start_ns'];meta={'core':top,'seed':seed,'mode':w['mode'],'duration_ns':duration,
      'operations':w['operations'],'accepted_samples':w['operations']*32 if mode<4 else 0,'measurement_cycles':round(duration/10)}
    row=parse(pt,meta,audit);row['raw_area_um2']=row['area_um2'];row['area_55eq_um2']=row['area_um2']*.81
    row['latency_cycles_per_frame']=[x[1] for x in rr['frames']]
    row['output_scale']='event_sum' if mode<4 else 'probability_numerator256'
    row['boundary']='compute core plus late integer recovery/control; external static weights/config/q9/events, RNG/SRAM/CTS/SDF/SPEF excluded'
    save(d/'RESULT.json',row);r['windows'].append(row);save(out/'RESULT.json',r)
    print('PPA_WINDOW',top,seed,w['mode'],row['total_W'],row['setup_slack_ns'],row['hold_slack_ns'],flush=True)
  r['status']='calculated'
 except Exception as e:r['status']='failed';r['error']=str(e);raise
 finally:save(out/'RESULT.json',r);archive(out)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['functional','ppa']);p.add_argument('--out',type=Path,required=True);p.add_argument('--m',type=int,default=1);p.add_argument('--mode',type=int,default=0);p.add_argument('--reuse',type=Path);a=p.parse_args()
 if a.stage=='functional':functional(a.out.resolve(),a.m)
 else:ppa(a.out.resolve(),a.mode,a.m,a.reuse.resolve() if a.reuse else None)
