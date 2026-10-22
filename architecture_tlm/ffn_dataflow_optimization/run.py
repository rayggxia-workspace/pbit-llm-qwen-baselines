"""Frozen, bounded consumer experiments; every shared candidate runs SC and W8."""
import argparse
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from .dependencies import load, record
from .fixtures import build_fixture, digest
from .model import Config, execute

ROOT=Path(__file__).resolve().parents[2]
SOURCE_FILES=('__init__.py','dependencies.py','fixtures.py','model.py','run.py')

def candidates():
 return [
  {'id':'baseline','config':{}},
  {'id':'restore4_only','config':{'profile':{'restore_lanes':4}}},
  {'id':'read128_only','config':{'counter_read_bytes':128}},
  {'id':'read128_restore4','config':{'counter_read_bytes':128,'profile':{'restore_lanes':4}}},
  {'id':'pipeline2','config':{'counter_read_bytes':128,'weight_slots':2,'counter_slots':2,'profile':{'restore_lanes':4}}},
  {'id':'pipeline2_addII4','config':{'counter_read_bytes':128,'weight_slots':2,'counter_slots':2,'profile':{'restore_lanes':4,'add_ii':4}}},
  {'id':'pipeline2_stage1','config':{'counter_read_bytes':128,'weight_slots':2,'counter_slots':2,'staging_packets':1,'profile':{'restore_lanes':4}}},
  {'id':'weight2_only','config':{'weight_slots':2}},
 ]

def write(path,obj):
 with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')

def source_record(deps):
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
 files={}
 for name in SOURCE_FILES:
  p=Path(__file__).with_name(name);rel=p.relative_to(ROOT).as_posix()
  committed=subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT)
  if committed!=p.read_bytes():raise ValueError('commit exact source before execution: '+rel)
  files[rel]=record(p)
 return dict(commit=commit,files=files,source_sha256=digest(files),dependencies=deps.lock,
  dependency_source_sha256=deps.source_sha256,command=sys.argv,python=sys.version,platform=platform.platform(),
  scope='Local CPU short projection, frozen sample replay; not full FFN/PPL/STA/physical PPA')

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);p.add_argument('--dependencies',type=Path,required=True)
 p.add_argument('--fixtures',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--seeds',type=int,nargs='+',default=[0,1,2])
 p.add_argument('--groups',type=int,default=4);p.add_argument('--tiles',type=int,default=8)
 p.add_argument('--candidates',nargs='+',default=['all']);p.add_argument('--mode',choices=['both','event'],default='both');p.add_argument('--max-cases',type=int,default=48)
 a=p.parse_args();deps=load(a.dependencies);source=source_record(deps)
 if len(set(a.seeds))!=len(a.seeds):raise ValueError('duplicate seeds')
 if a.output.exists():raise ValueError('fresh output directory required')
 if a.action=='prepare':
  a.output.mkdir(parents=True);write(a.output/'EXECUTION.json',source);items=[]
  for seed in a.seeds:
   t=time.perf_counter();fixture=build_fixture(deps.restore,seed=seed,groups=a.groups,tiles=a.tiles)
   path=a.output/f'seed{seed}.json';write(path,fixture);items.append(dict(seed=seed,path=path.name,**record(path),fixture_sha256=fixture['fixture_sha256']))
   print(json.dumps({'fixture':path.name,'seconds':time.perf_counter()-t}),flush=True)
  write(a.output/'FIXTURES.json',dict(groups=a.groups,tiles=a.tiles,seeds=a.seeds,files=items));return
 if a.fixtures is None:raise ValueError('--fixtures required')
 manifest=json.loads((a.fixtures/'FIXTURES.json').read_text(encoding='utf-8'))
 if (manifest['groups'],manifest['tiles'])!=(a.groups,a.tiles):raise ValueError('fixture shape differs')
 available={c['id']:c for c in candidates()};names=list(available) if a.candidates==['all'] else a.candidates
 if len(set(names))!=len(names) or len(names)*len(a.seeds)*2>a.max_cases:raise ValueError('unique bounded cases required')
 cases=[]
 for name in names:
  for seed in a.seeds:
   for method in ['sc','w8']:
    cfg=Config(groups=a.groups,tiles=a.tiles,**available[name]['config'])
    cases.append(dict(id=f'{name}_{method}_seed{seed}',candidate=name,seed=seed,method=method,config=asdict(cfg)))
 a.output.mkdir(parents=True);write(a.output/'EXECUTION.json',source)
 write(a.output/'RUN_MANIFEST.json',dict(cases=cases,mode=a.mode,source_sha256=source['source_sha256'],execution_commit=source['commit'],fixture_manifest=record(a.fixtures/'FIXTURES.json')))
 fixtures={}
 for spec in cases:
  seed=spec['seed']
  if seed not in fixtures:
   item=next(x for x in manifest['files'] if x['seed']==seed);path=a.fixtures/item['path']
   if record(path)!={k:item[k] for k in ('bytes','sha256')}:raise ValueError('fixture bytes changed')
   fixture=json.loads(path.read_text(encoding='utf-8'));check=dict(fixture);check.pop('fixture_sha256')
   if digest(check)!=fixture['fixture_sha256']:raise ValueError('fixture identity changed')
   fixtures[seed]=fixture
  fixture=fixtures[seed];cfg=Config(groups=a.groups,tiles=a.tiles,**available[spec['candidate']]['config']);t=time.perf_counter()
  try:
   ev=execute(deps,fixture,cfg,method=spec['method'],mode='event')
   observations=('partial_receipts','feed_receipts','row_receipts','final_sram_sha256','storage')
   equal=None;cycle_steps=None;cycle_equivalence_sha256=None;cycle_output_sha256=None;cycle_observables_sha256=None
   if a.mode=='both':
    cy=execute(deps,fixture,cfg,method=spec['method'],mode='cycle')
    equal=(ev['result'].equivalence_payload()==cy['result'].equivalence_payload() and ev['output_words']==cy['output_words']
           and all(ev[key]==cy[key] for key in observations))
    if not equal:raise AssertionError('cycle/event mismatch')
    cycle_steps=cy['result'].steps
    cycle_equivalence_sha256=digest(cy['result'].equivalence_payload())
    cycle_output_sha256=digest(cy['output_words'])
    cycle_observables_sha256=digest({key:cy[key] for key in observations})
   if ev['output_words']!=fixture['expected_'+spec['method']]:raise AssertionError('numeric reference mismatch')
   recheck=dict(fixture);recheck.pop('fixture_sha256')
   if digest(recheck)!=fixture['fixture_sha256']:raise AssertionError('execution mutated shared fixture')
   native=asdict(ev['result']);assert not native['memory_reads'],'unexpected byte-valued memory payload'
   value={k:v for k,v in ev.items() if k not in ('kernel','result')}
   value.update(case=spec,native_result=native,cycle_event_equal=equal,cycle_steps=cycle_steps,
    event_equivalence_sha256=digest(ev['result'].equivalence_payload()),cycle_equivalence_sha256=cycle_equivalence_sha256,
    event_output_sha256=digest(ev['output_words']),cycle_output_sha256=cycle_output_sha256,
    event_observables_sha256=digest({key:ev[key] for key in observations}),cycle_observables_sha256=cycle_observables_sha256,
    output_reference_equal=True,fixture_sha256=fixture['fixture_sha256'],input_sha256=fixture['hashes']['inputs'],
    source=source,wall_seconds=time.perf_counter()-t,full_physical_area_mm2=None,full_physical_energy_J=None,quality_ppl=None)
   raw=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
   path=a.output/(spec['id']+'.json.gz')
   with path.open('xb') as f:f.write(gzip.compress(raw,mtime=0))
   write(a.output/(spec['id']+'.receipt.json'),dict(case=spec,file=path.name,**record(path),
    json_bytes=len(raw),json_sha256=hashlib.sha256(raw).hexdigest(),
    finish_ps=ev['result'].finish_ps,cycle_event_equal=equal,output_reference_equal=True,
    event_equivalence_sha256=value['event_equivalence_sha256'],cycle_equivalence_sha256=cycle_equivalence_sha256,
    event_output_sha256=value['event_output_sha256'],cycle_output_sha256=cycle_output_sha256,
    event_observables_sha256=value['event_observables_sha256'],cycle_observables_sha256=cycle_observables_sha256,
    fixture_sha256=fixture['fixture_sha256'],source_sha256=source['source_sha256'],metrics=ev['metrics'],storage=ev['storage']))
   print(json.dumps({'case':spec['id'],'finish_ns':ev['result'].finish_ps/1000,'wall_seconds':value['wall_seconds'],'cycle_event_equal':equal}),flush=True)
  except Exception as error:
   write(a.output/(spec['id']+'.FAILURE.json'),dict(case=spec,error=repr(error),source=source));raise

if __name__=='__main__':main()
