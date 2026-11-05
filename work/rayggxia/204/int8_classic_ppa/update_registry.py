"""Incremental registration in this branch and the latest full local mirror."""
from pathlib import Path
import csv,hashlib,io,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;R=HERE.parents[3];W=R.parents[1]
A=W/'project_archives/matrix204_int8_classic_ppa_20261028';RID='matrix-int8-classic-204-20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 summary=R/'architecture_tlm/int8_classic_ppa_20261028/results/FINAL_SUMMARY.json';s=json.loads(summary.read_text(encoding='utf-8'));stable=A/'FINAL_SUMMARY.json'
 if stable.exists():assert sha(stable)==sha(summary)
 else:shutil.copyfile(summary,stable)
 artifacts=[]
 for p,role in [(stable,'verified_summary')]+[(Path(x['path']),'execution_source_package') for x in s['source_packages']]+[(Path(x['path']),'original_reports_archive') for x in s['report_archives']]:
  x=dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,role=role,present_at_registration=True,required=True)
  if role=='original_reports_archive':
   orig=next(x for x in s['report_archives'] if x['path']==str(p));x.update(member='RESULT.json',member_sha256=orig['result_member_sha256'],member_bytes=(p.parent/'RESULT.json').stat().st_size)
  artifacts.append(x)
 fingerprints=A/'EXECUTION_FINGERPRINTS.json'
 artifacts.append(dict(path=str(fingerprints),role='configuration_and_library_fingerprints',sha256=sha(fingerprints),bytes=fingerprints.stat().st_size,present_at_registration=True,required=True))
 record=dict(schema_version=1,id=RID,name='经典四lane INT8 DOT4：INT32主参考与N64精确INT22',family='FFN/矩阵/控制',registered_on='2026-10-28',owner='rayggxia',issue=204,evidence_level='DC_GATE_PT_PRELAYOUT',status='calculated_with_limits',stages=dict(functional='pass',synthesis='completed',sta='violations' if any(min(x['setup_slack_ns'],x['hold_slack_ns'])<0 for x in s['PPA']) else 'reported_nonnegative',power='calculated',postlayout='not_run'),boundary=s['boundary'],
  conditions=dict(node_nm=55,corner='SS',voltage_V=1.08,temperature_C=125,clock_MHz=100,seeds=[17,503,1009],window_ns=None,load_pF=.02,sdf=False,spef=False,cts=False,activity='Three seeds,16 complete BF16-value-matched N64 frames +16 fullrange signedINT8 frames +idle per seed;4 extrema frames and1 abort separate from power',area_reporting='raw cell area preserved; 55nm-equivalent raw*.81 once; no power/time scaling',reset_contract='Async control reset and synchronous accumulator; products no reset, valid masked. External release4.5..5.5ns from rising edge, identical to BF16 supplemental contract. Data max/min delay1/.02ns, no false/multicycle paths.'),
  source=dict(git_commit=None,source_base=s['source_base'],source_manifest_sha256=s['execution_source_manifest_sha256'],binding='Immutable uncommitted execution ZIP/manifests with all RTL/bench/fixture/constraint SHA. Final v4 copied publicly byte-for-byte; v1/v2 failures and v3 intermediate functional checks retained.'),artifacts=artifacts,cases=s['PPA']+[dict(x,kind='preserved_failed_attempt') for x in s['failures_preserved']],
  limitations=['Prelayout mapped DUT only, no CTS/SDF/SPEF, true ICG, SRAM or physical data delivery. Library-range and timing warnings retained; not chip/signoff measurements.',
   'Same48 integer-derived synthetic values as BF16: integer result /128 equals exact BF16 output. Output-format conversion excluded; no new real-model quantization/quality/PPL.',
   'AW22 exactly covers fixed64 full signedINT8 pairs without bias. Main reusable convention AW32; neither module implements arbitraryK. Both external outputs32-bit, sign-extension load included.',
   'Classical architectural reference to pinned Gemmini/NVDLA, not a full import or proof of globally optimal integer engine. Explicit product pipeline; final DC no retime, set_fix_hold core.',
   'v1/v2 mapped gate X first frame rejected despite passing RTL; v2 removed retime and still failed. Wave traced X control counter LSB under sync reset. v3 actual async control reset; v4 same circuit with strict four-state handshake. No forced register initialization, X waivers or library model edits.',
   'SC54/old INT8 have different stimuli/operation interfaces; core-only rough comparison not a precision-matched full-array/LLM claim. Multiple versions/replays not counted as new architectures.'],next_action='Review classic INT8 versus SC precision/bandwidth/storage contracts; close reset/clock/weight delivery and largerM array costs before full-chip claims.')
 rec=HERE/'private/RECORD.json';save(rec,record);outputs=[]
 for reg,label in [(R/'digital_circuit_simulation_registry','task_branch'),(W/'digital_circuit_simulation_registry','local_full_union')]:
  old={p.name:sha(p) for p in (reg/'records').glob('*.json') if p.stem!=RID};backup=A/'registry_preimages'/label;backup.mkdir(parents=True,exist_ok=True)
  for p in reg.iterdir():
   if p.is_file():
    dst=backup/(sha(p)+'_'+p.name)
    if not dst.exists():shutil.copyfile(p,dst)
  target=reg/'records'/(RID+'.json')
  if target.exists():
   previous=json.loads(target.read_text(encoding='utf-8'));assert previous['owner']=='rayggxia' and previous['issue']==204;shutil.copyfile(rec,target)
  else:subprocess.run([sys.executable,str(reg/'registry.py'),'add',str(rec)],check=True,capture_output=True)
  inventory=list(csv.DictReader((reg/'archive_inventory.csv').open(encoding='utf-8',newline='')));known={x['path'] for x in inventory}
  additions=[dict(path=x['path'],bytes=x['bytes'],sha256=x['sha256'],linked_records=RID,review_state='sha_verified_remote_local_members',note='INT8 immutable execution/report archive; original bytes/member SHA verified') for x in artifacts[1:] if x['path'] not in known and x['role']!='configuration_and_library_fingerprints']
  if additions:
   out=io.StringIO(newline='');csv.DictWriter(out,fieldnames=list(inventory[0]),lineterminator='\n').writerows(additions)
   with (reg/'archive_inventory.csv').open('ab') as f:f.write(out.getvalue().encode())
  check=subprocess.run([sys.executable,str(reg/'registry.py'),'check'],capture_output=True,text=True,check=True)
  subprocess.run([sys.executable,str(reg/'registry.py'),'render'],check=True,capture_output=True)
  assert old=={p.name:sha(p) for p in (reg/'records').glob('*.json') if p.stem!=RID}
  outputs.append(dict(scope=label,check=json.loads(check.stdout),foreign_records_preserved=len(old),record_sha256=sha(target),inventory_appended=len(additions)))
 save(HERE/'REGISTRY_CHECK.json',dict(results=outputs,scope='Incremental union; full local mirror never replaced by smaller task branch. Foreign record bytes preserved.'))
 print(json.dumps(outputs,ensure_ascii=False))
if __name__=='__main__':main()
