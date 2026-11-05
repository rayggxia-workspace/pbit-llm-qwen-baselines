"""Register this batch by incremental union; preserve all other records."""
from pathlib import Path
import csv,hashlib,io,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[4];WS=ROOT.parents[1];HERE=Path(__file__).parent
RID='matrix-modules-204-20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
 summary=ROOT/'architecture_tlm/module_energy_20261028/results/FINAL_SUMMARY.json';r=json.loads(summary.read_text(encoding='utf-8'))
 artifacts=[{'path':str(summary),'role':'verified_summary','present_at_registration':True,'required':True,'sha256':sha(summary),'bytes':summary.stat().st_size}]
 for a in r['report_archives']+r['source_packages']:
  artifacts.append({k:a[k] for k in ['path','sha256','bytes']} | {'role':'execution_package' if a['path'].endswith('.zip') else 'original_reports_archive','present_at_registration':True,'required':True})
 cases=[]
 for f in r['functional']:
  cases.append(dict(f,kind='RTL_functional_VCS'))
 for p in r['PPA']:cases.append(dict(p,kind='DC_gate_PT_pre_layout'))
 for f in r['failures_preserved']:cases.append(dict(f,kind='failed_pipeline_attempt'))
 power=bool(r['PPA']);violation=any(min(x['setup_slack_ns'],x['hold_slack_ns'])<0 for x in r['PPA'])
 record={'schema_version':1,'id':RID,'name':'参数化popcount/移位加法/饱和累计及组合能耗表征','family':'FFN/矩阵/控制',
  'registered_on':'2026-10-28','owner':'rayggxia','issue':204,'evidence_level':'DC_GATE_PT_PRELAYOUT' if power else 'PARTIAL_FLOW',
  'status':'calculated_with_limits' if power else 'functional_pass_ppa_pending',
  'stages':{'functional':'pass','synthesis':'completed','sta':'violations' if violation else 'reported_nonnegative' if power else 'not_run','power':'calculated' if power else 'not_run','postlayout':'not_run'},
  'boundary':'33 fixed tops: popcount8..64 with output LSB quantization, signed popcount difference, mask/OR4, fixed shift-add, signed7..11 saturation counters, two planes, three77/54/50 state-bit banks, variable alignment16/20/24. No artificial I/O flops on combinational tops. SRAM/RNG/encoding/physical broadcast/CTS/SDF/SPEF excluded; CE not ICG.',
  'conditions':{'node_nm':55,'corner':'SS','voltage_V':1.08,'temperature_C':125,'clock_MHz':100,'seeds':[17,503,1009],
   'window_ns':None,'load_pF':0.02,'sdf':False,'spef':False,'cts':False,'activity':'Three seeds and sparse/dense/replay/idle per top. Synthetic stress and derived old M8 replay; non16 pop replay IIDp=.35, align replay random words. Sequential32 samples/frame; fixed shift replay once/35cycles. No model quality claim.',
   'area_reporting':'raw library area and user-confirmed raw*0.81 55nm-equivalent area both preserved; do not scale power/timing'},
  'source':{'git_commit':None,'source_manifest_sha256':sha(ROOT/'architecture_tlm/module_energy_20261028/EXECUTION_MANIFEST.json'),'binding':'Per-version execution ZIP/manifests and exact archived report member SHA in summary; reused RTL/library/fixture/constraints checked.'},
  'artifacts':artifacts,'cases':cases,
  'limitations':['Prelayout; all reported timing violations and power-model warnings retained; no physical signoff',
   'Pop output reduced precision drops LSB and changes unit; fixed shift and variable shift are different blocks. Bank weights explicitly have7-bit magnitude<=127. Width errors vs bank77 are synthetic, not model quality.',
   'Standalone output load20fF differs from connected-cell loads; raw component sums are evaluated against connected plane/bank. bank54-calibrated delta is validated on bank50 only, not a general whole-chip bound.',
   'All mapped ports/leaf pins verified. Only directly tied indexed dout output bits may complete absent PT activity via explicit mapped assign and identical constant VCD; no leaf pin waiver.',
   'V1 bootstrap failed before VCS/DC/PT due old Python newline keyword; all33 failure logs preserved. V2 changes driver compatibility only. Raw samples field placeholder0 corrected in derived profiles to32/frame; original bytes preserved.',
   'Memory/RNG/encoding/physical broadcast/full-array and real Instruct quality remain outside this batch'],
  'next_action':'Use replay operation units and empirical composition error; characterize real ICG/load/interconnect/storage/RNG separately before full-array estimates. Preserve timing/model warnings; no whole-chip advantage claim.'}
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
 backup=WS/'project_archives/matrix204_module_energy_20261028/registry_preimage';backup.mkdir(exist_ok=True)
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
