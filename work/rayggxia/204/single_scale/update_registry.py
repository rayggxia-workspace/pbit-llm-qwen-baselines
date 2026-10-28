"""Register this batch by incremental union; preserve all other records."""
from pathlib import Path
import csv,hashlib,io,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[4];WS=ROOT.parents[1];HERE=Path(__file__).parent
RID='matrix-single-scale-204-20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
 summary=ROOT/'architecture_tlm/matrix_single_scale_20261028/results/FINAL_SUMMARY.json';r=json.loads(summary.read_text(encoding='utf-8'))
 artifacts=[{'path':str(summary),'role':'verified_summary','present_at_registration':True,'required':True,'sha256':sha(summary),'bytes':summary.stat().st_size}]
 for a in r['report_archives']+r['source_packages']:
  artifacts.append({k:a[k] for k in ['path','sha256','bytes']} | {'role':'execution_package' if a['path'].endswith('.zip') else 'original_reports_archive','present_at_registration':True,'required':True})
 cases=[]
 for f in r['functional']:
  cases.append(dict(f,kind='RTL_functional'))
 for p in r['PPA']:cases.append(dict(p,kind='DC_gate_PT_pre_layout'))
 for f in r['failures_preserved']:cases.append(dict(f,kind='failed_pipeline_attempt'))
 power=bool(r['PPA']);violation=any(min(x['setup_slack_ns'],x['hold_slack_ns'])<0 for x in r['PPA'])
 record={'schema_version':1,'id':RID,'name':'单尺度INT8 T32 OR4并行计数与数字对照验证','family':'FFN/矩阵/控制',
  'registered_on':'2026-10-28','owner':'rayggxia','issue':204,'evidence_level':'DC_GATE_PT_PRELAYOUT' if power else 'PARTIAL_FLOW',
  'status':'calculated_with_limits' if power else 'functional_pass_ppa_pending',
  'stages':{'functional':'pass','synthesis':'completed','sta':'violations' if violation else 'reported_nonnegative' if power else 'not_run','power':'calculated' if power else 'not_run','postlayout':'not_run'},
  'boundary':'N64/B1/T32 signed INT8[-128,127]; 16 synthesized variants, M1/M8. Compute/control/counting/integer recovery only; external resident weight/events/INT8 source; memory/RNG/comparators/quantization/common scale recovery/CTS/SDF/SPEF excluded.',
  'conditions':{'node_nm':55,'corner':'SS','voltage_V':1.08,'temperature_C':125,'clock_MHz':100,'seeds':[17,503,1009],
   'window_ns':None,'load_pF':0.02,'sdf':False,'spef':False,'cts':False,'activity':'16 synthetic resident-W uniform signed INT8 frames per seed, common R8 across lanes; active and idle; no model-quality claim',
   'area_reporting':'raw library area and user-confirmed raw*0.81 55nm-equivalent area both preserved; do not scale power/timing'},
  'source':{'git_commit':None,'source_manifest_sha256':sha(ROOT/'architecture_tlm/matrix_single_scale_20261028/EXECUTION_MANIFEST.json'),'binding':'Per-version execution ZIP/manifests and exact archived report member SHA in summary; reused RTL/library/fixture/constraints checked.'},
  'artifacts':artifacts,'cases':cases,
  'limitations':['Prelayout; all reported timing violations and power-model warnings retained; no physical signoff',
   'OR4 remains lossy; all counting variants equal the same OR oracle, whose error is separately reported; no matched-quality claim',
   'Parallel and bitserial signed INT8 controls are measured RTL implementations; neither represents a mature best digital baseline',
   'All activity bits/pins verified; only explicit directly-tied top outputs may complete absent PT activity using exact netlist literal and zero-toggle VCD, with original PT table preserved',
   'All three frozen implementation versions preserved; report copying and resummary are not new hardware experiments',
   'Memory/RNG/encoding/physical broadcast/full-array and real Instruct quality remain outside this batch'],
  'next_action':'Review results, close power-table and hold warnings, then resident-weight/ICG/SRAM/full-array and matched-quality mature digital controls; do not infer complete-chip advantages'}
 dst=ROOT/'digital_circuit_simulation_registry/records'/(RID+'.json');save(dst,record)
 reg=WS/'digital_circuit_simulation_registry';check=HERE/'private/registry_union';check.mkdir(parents=True,exist_ok=True)
 tracked=['catalog.json','archive_inventory.csv','00_总览.md','01_结果地址索引.md','runs.csv','artifact_locations.csv']
 pre={n:sha(reg/n) for n in tracked};old={p.name:sha(p) for p in (reg/'records').glob('*.json') if p.name!=dst.name}
 if (check/'records').exists():
  # Only replace our own previous scratch union, after checking its absolute root.
  assert check.resolve().is_relative_to((HERE/'private').resolve())
  for p in (check/'records').glob('*.json'):p.unlink()
 else:(check/'records').mkdir()
 for n in ['registry.py','catalog.json','archive_inventory.csv']:shutil.copyfile(reg/n,check/n)
 for p in (reg/'records').glob('*.json'):shutil.copyfile(p,check/'records'/p.name)
 # Updating metadata for this same experiment is not a new run; preserve others.
 if (check/'records'/dst.name).exists():
  prior=json.loads((check/'records'/dst.name).read_text(encoding='utf-8'))
  assert prior['owner']=='rayggxia' and prior['issue']==204
  shutil.copyfile(dst,check/'records'/dst.name)
 else:subprocess.run([sys.executable,str(check/'registry.py'),'add',str(dst)],check=True)
 inventory=list(csv.DictReader((check/'archive_inventory.csv').open(encoding='utf-8',newline='')));known={x['path'] for x in inventory}
 additions=[]
 for a in artifacts[1:]:
  if a['path'] not in known:additions.append({'path':a['path'],'bytes':a['bytes'],'sha256':a['sha256'],'linked_records':RID,'review_state':'sha_verified_local','note':'Original package/report archive bytes and members verified; authorized local access'})
 if additions:
  out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=list(inventory[0]));writer.writerows(additions)
  with (check/'archive_inventory.csv').open('ab') as f:f.write(out.getvalue().encode('utf-8'))
 result=subprocess.run([sys.executable,str(check/'registry.py'),'check'],capture_output=True,text=True,check=True)
 subprocess.run([sys.executable,str(check/'registry.py'),'render'],check=True)
 assert pre=={n:sha(reg/n) for n in tracked},'Concurrent catalog update: rerun union'
 assert old=={p.name:sha(p) for p in (reg/'records').glob('*.json') if p.name!=dst.name},'Concurrent record update: rerun union'
 backup=WS/'project_archives/matrix204_single_scale_20261028/registry_preimage';backup.mkdir(exist_ok=True)
 for n in tracked:
  b=backup/n
  if not b.exists():shutil.copyfile(reg/n,b)
 shutil.copyfile(dst,reg/'records'/dst.name)
 for n in tracked:shutil.copyfile(check/n,reg/n)
 subprocess.run([sys.executable,str(reg/'registry.py'),'check'],check=True)
 assert all(sha(reg/'records'/n)==h for n,h in old.items())
 save(HERE/'REGISTRY_CHECK.json',{'union_check':json.loads(result.stdout),'old_records_unchanged':len(old),'record_sha256':sha(dst),
   'generated_SHA256':{n:sha(check/n) for n in tracked},'inventory_appended':len(additions),
   'publication_scope':'main lacks full registry; this PR adds only our run record. Union check/render updates central local reading mirror without copying foreign records into this task PR.'})
 print('REGISTRY_INCREMENTAL_UNION_DONE',len(old)+1)
if __name__=='__main__':main()
