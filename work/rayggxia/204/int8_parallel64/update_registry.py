"""Append this run separately to the task subset and full local registry union."""
from pathlib import Path
import csv,hashlib,io,json,shutil,subprocess,sys
H=Path(__file__).resolve().parent;R=H.parents[3];W=R.parents[1];A=W/'project_archives/matrix204_parallel64_20261029';RID='matrix-int8-par64-204-20261029'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 summary=R/'architecture_tlm/int8_parallel64_20261028/results/FINAL_SUMMARY.json';s=json.loads(summary.read_text());stable=A/'FINAL_SUMMARY.json'
 if stable.exists():assert sha(stable)==sha(summary)
 else:shutil.copyfile(summary,stable)
 artifacts=[]
 for p,role in [(stable,'verified_summary'),(A/'EXECUTION_FINGERPRINTS.json','configuration_and_library_fingerprints'),(A/'SLURM_FINAL.txt','slurm_final')]+[(Path(x['path']),'execution_source_package') for x in s['source_packages']]+[(Path(x['path']),'original_reports_archive') for x in s['report_archives']]:
  x=dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,role=role,present_at_registration=True,required=True)
  if role=='original_reports_archive':
   orig=next(z for z in s['report_archives'] if z['path']==str(p));x.update(member='RESULT.json',member_sha256=orig['result_member_sha256'],member_bytes=(p.parent/'RESULT.json').stat().st_size)
  artifacts.append(x)
 cases=[{k:x[k] for k in ['case','raw_area_um2','area_55eq_um2','mapped_sha256','setup_slack_ns','hold_slack_ns','review_flags','latency_cycles','initiation_interval_cycles','profiles']} for x in s['PPA']]
 record=dict(schema_version=1,id=RID,name='同64路并行INT8完整N64：32/22位结果、满速与SC同350ns发帧',family='FFN/矩阵/控制',registered_on='2026-10-29',owner='rayggxia',issue=204,evidence_level='DC_GATE_PT_PRELAYOUT',status='calculated_with_limits',stages=dict(functional='pass',synthesis='completed',sta='reported_nonnegative',power='calculated',postlayout='not_run'),boundary=s['boundary'],
  conditions=dict(node_nm=55,corner='SS',voltage_V=1.08,temperature_C=125,clock_MHz=100,seeds=[17,503,1009],window_ns=None,load_pF=.02,sdf=False,spef=False,cts=False,activity='Same SC16 operands/seed: peak128 outputs/1280ns, paced16/5600ns, fullrange16/160ns,idle0/2560ns; 4 extrema separate;164 transactions/seed/top',area_reporting='raw cell area preserved;55nm-equivalent raw*.81 once; no power/time scaling',reset_contract='Control async/result sync; external release4.5..5.5ns from rising edge;data max/min1/.02ns,slew.05ns,load20fF,uncertainty.5/.05ns;no false/multicycle'),
  source=dict(git_commit=None,source_base=s['source_base'],source_manifest_sha256=s['execution_source_manifest_sha256'],binding='Immutable v1/v2 uncommitted execution ZIPs; all manifest files checked. Final public source byte-identical to v2, fixtures recoverable/generatable from source package.'),artifacts=artifacts,cases=cases+[dict(x,kind='preserved_initial_hold_violation') for x in s['failures_preserved']],
  limitations=['Mapped core prelayout; no CTS/SDF/SPEF/complete delay glitches or physical signoff.24 final PT windows;24 initial calculated windows retained with hold violation.',
   'Fixed N64 M1,64 simultaneous signed8x8 dynamic-input products/balanced tree/registered32-or22-bit result; no temporal multiplier reuse or arbitraryK feedback accumulator. Both external results32bits.',
   'SC operand frames SHA matched, W row f%8 capabs127; SC OR4/T32/drop-plane approximate versus exact INT8. No model/tokenizer/corpus/inference/PPL; no quality-equivalence claim.',
   'Storage/RNG/comparison/format conversion/physical broadcast/trueICG outside boundary. Paced100MHz clock remains running, not optimal gated digital energy.',
   'v1 hold−.061165ns retained. v2 verifies unchanged source/config/library, reads original mapped netlist and native DC hold-only buffers it, +raw1.44um2; no arithmetic recompile/retime/constraint waiver.984 RTL and984 mapped outputs verified for final2top batch.'],next_action='Review same64 comparison and close quality, storage/data delivery, clock and multioutput boundaries; do not re-run finished jobs.')
 rec=H/'private/RECORD.json';save(rec,record);outputs=[]
 for reg,label in [(R/'digital_circuit_simulation_registry','task_branch'),(W/'digital_circuit_simulation_registry','local_full_union')]:
  old={p.name:sha(p) for p in (reg/'records').glob('*.json') if p.stem!=RID};backup=A/'registry_preimages'/label;backup.mkdir(parents=True,exist_ok=True)
  for p in reg.iterdir():
   if p.is_file():
    dst=backup/(sha(p)+'_'+p.name)
    if not dst.exists():shutil.copyfile(p,dst)
  target=reg/'records'/(RID+'.json')
  if target.exists():
   prior=json.loads(target.read_text(encoding='utf-8'));assert prior['owner']=='rayggxia' and prior['issue']==204;shutil.copyfile(rec,target)
  else:subprocess.run([sys.executable,str(reg/'registry.py'),'add',str(rec)],check=True,capture_output=True)
  inventory=list(csv.DictReader((reg/'archive_inventory.csv').open(encoding='utf-8',newline='')));known={x['path'] for x in inventory}
  additions=[dict(path=x['path'],bytes=x['bytes'],sha256=x['sha256'],linked_records=RID,review_state='sha_verified_remote_local_members',note='parallel64 immutable source/report; original bytes and member SHA verified') for x in artifacts if x['role'] in ['execution_source_package','original_reports_archive'] and x['path'] not in known]
  if additions:
   o=io.StringIO(newline='');csv.DictWriter(o,fieldnames=list(inventory[0]),lineterminator='\n').writerows(additions)
   with (reg/'archive_inventory.csv').open('ab') as f:f.write(o.getvalue().encode())
  check=subprocess.run([sys.executable,str(reg/'registry.py'),'check'],capture_output=True,text=True,check=True)
  subprocess.run([sys.executable,str(reg/'registry.py'),'render'],check=True,capture_output=True)
  assert old=={p.name:sha(p) for p in (reg/'records').glob('*.json') if p.stem!=RID}
  outputs.append(dict(scope=label,check=json.loads(check.stdout),foreign_records_preserved=len(old),record_sha256=sha(target),inventory_appended=len(additions)))
 save(H/'REGISTRY_CHECK.json',dict(results=outputs,scope='Each scope incrementally preserves its own latest record union, never replaces full union with task subset.'))
 print(json.dumps(outputs,ensure_ascii=False))
if __name__=='__main__':main()
