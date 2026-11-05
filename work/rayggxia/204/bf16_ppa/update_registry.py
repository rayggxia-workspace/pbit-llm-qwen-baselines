"""Register one BF16 run independently in task branch and full local union."""
from pathlib import Path
import csv,hashlib,io,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];WS=ROOT.parents[1]
A=WS/'project_archives/matrix204_bf16_ppa_20261028';RID='matrix-bf16-204-20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 summary=ROOT/'architecture_tlm/bf16_ppa_20261028/results/FINAL_SUMMARY.json';s=json.loads(summary.read_text(encoding='utf-8'))
 stable=A/'FINAL_SUMMARY.json'
 if stable.exists():assert sha(stable)==sha(summary)
 else:shutil.copyfile(summary,stable)
 artifacts=[]
 for p,role in [(stable,'verified_summary')]+[(Path(x['path']),'execution_source_package') for x in s['source_packages']]+[(Path(x['path']),'original_reports_archive') for x in s['report_archives']]:
  a=dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,role=role,present_at_registration=True,required=True)
  if role=='original_reports_archive':
   source=next(x for x in s['report_archives'] if x['path']==str(p));a.update(member='RESULT.json',member_sha256=source['result_member_sha256'],member_bytes=(p.parent/'RESULT.json').stat().st_size)
  artifacts.append(a)
 record=dict(schema_version=1,id=RID,name='成熟FPnew BF16/FP32单元及折叠DOT4 N64前布局PPA',family='FFN/矩阵/控制',registered_on='2026-10-28',owner='rayggxia',issue=204,evidence_level='DC_GATE_PT_PRELAYOUT',status='calculated_with_limits',
  stages=dict(functional='pass',synthesis='completed',sta='violations' if any(min(x['reset_contract_sta']['setup_slack_ns'],x['reset_contract_sta']['hold_slack_ns'])<0 for x in s['PPA']) else 'reported_nonnegative',power='calculated',postlayout='not_run'),
  boundary=s['boundary'],conditions=dict(node_nm=55,corner='SS',voltage_V=1.08,temperature_C=125,clock_MHz=100,seeds=[17,503,1009],window_ns=None,load_pF=.02,sdf=False,spef=False,cts=False,activity='Independent synthetic normal/int8/idle; scalar1024 ops/window plus drain, N64 sixteen frames/window. Not LLM activations.',area_reporting='Preserve raw library cell area; 55nm-equivalent=raw*.81 once; no power/time scaling',reset_contract='Original0.02..1ns async-release timing violations retained; supplemental STA uses4.5..5.5ns release from rising edge, all data constraints unchanged, no recovery/removal waiver'),
  source=dict(git_commit=None,source_base=s['source_base'],source_manifest_sha256=s['execution_source_manifest_sha256'],binding='Executed uncommitted immutable v6/v7 ZIPs with exact RTL/bench/fixture/constraint SHA; N64 synthesis reused with full equivalence proof; supplemental STA separately frozen; published source blobs verified against ZIP.'),artifacts=artifacts,cases=s['PPA']+[dict(x,kind='preserved_failed_attempt') for x in s['failures_preserved']],
  limitations=['Prelayout; no CTS/SDF/SPEF or silicon signoff. Original timing failures and power warnings retained. Supplemental STA reset contract is an external requirement, not a completed reset-distribution circuit.',
   'FPnew arithmetic is mature upstream; folded four-lane DOT4 is this task conventional non-fused integration, not a proven globally optimal BF16 matrix engine. FP32 rounding at every add differs from fused DOT instructions.',
   'Both scalar and complete N64 windows include gross internal/switching/leakage. No repeated64x scalar proxy for frame energy. Data/weight supply, SRAM, RNG and front/backends remain excluded.',
   'Synthetic three seeds only. BF16 versus OR4/T32 SC does not establish matched quality or full-array advantage. Prior INT8 runs use different traces/boundaries.',
   'V1 old Python; V2 timescale; V3 success marker; V4/V5 DC2018 compatibility failures preserved. No arithmetic algorithm edits. Generator regeneration requires reapplying recorded equivalent compatibility patches.',
   *s['metadata_errata']],next_action='Review PPA and timing/reset contract; compare precision-matched INT8 with classical output-stationary MAC / balanced reduction and shared data delivery; fused BF16 dot and clock gating remain possible optimizations.')
 rec=HERE/'private/RECORD.json';save(rec,record)
 outputs=[]
 for reg,label in [(ROOT/'digital_circuit_simulation_registry','task_branch'),(WS/'digital_circuit_simulation_registry','local_full_union')]:
  old={p.name:sha(p) for p in (reg/'records').glob('*.json') if p.stem!=RID};before={p.name:sha(p) for p in reg.iterdir() if p.is_file()}
  backup=A/'registry_preimages'/label;backup.mkdir(parents=True,exist_ok=True)
  for n,h in before.items():
   dst=backup/(h+'_'+n)
   if not dst.exists():shutil.copyfile(reg/n,dst)
  target=reg/'records'/(RID+'.json')
  if target.exists():
   prior=json.loads(target.read_text(encoding='utf-8'));assert prior['owner']=='rayggxia' and prior['issue']==204
   shutil.copyfile(rec,target)
  else:subprocess.run([sys.executable,str(reg/'registry.py'),'add',str(rec)],check=True,capture_output=True)
  inventory=list(csv.DictReader((reg/'archive_inventory.csv').open(encoding='utf-8',newline='')));known={x['path'] for x in inventory}
  additions=[dict(path=a['path'],bytes=a['bytes'],sha256=a['sha256'],linked_records=RID,review_state='sha_verified_remote_local_members',note='Immutable execution/report archive; original bytes and member SHA verified') for a in artifacts[1:] if a['path'] not in known]
  if additions:
   out=io.StringIO(newline='');csv.DictWriter(out,fieldnames=list(inventory[0]),lineterminator='\n').writerows(additions)
   with (reg/'archive_inventory.csv').open('ab') as f:f.write(out.getvalue().encode())
  check=subprocess.run([sys.executable,str(reg/'registry.py'),'check'],capture_output=True,text=True,check=True)
  subprocess.run([sys.executable,str(reg/'registry.py'),'render'],check=True,capture_output=True)
  assert old=={p.name:sha(p) for p in (reg/'records').glob('*.json') if p.stem!=RID},'Foreign records changed'
  outputs.append(dict(scope=label,check=json.loads(check.stdout),foreign_records_preserved=len(old),record_sha256=sha(target),inventory_appended=len(additions)))
 save(HERE/'REGISTRY_CHECK.json',dict(results=outputs,scope='Task branch and full local mirror each add only this run to their own latest record set. Foreign record bytes preserved; never replace full mirror by task subset. Additional full-mirror foreign records='+str(outputs[1]['foreign_records_preserved']-outputs[0]['foreign_records_preserved'])))
 print(json.dumps(outputs,ensure_ascii=False))
if __name__=='__main__':main()
