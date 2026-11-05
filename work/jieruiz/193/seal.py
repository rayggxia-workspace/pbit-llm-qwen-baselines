"""Seal validated, exact bytes; archive small results, never simulation binaries."""
from pathlib import Path
import hashlib, importlib.util, json, shutil, subprocess, tarfile, zipfile
ROOT=Path(__file__).resolve().parents[3]
P=ROOT/'architecture_tlm/ffn_calibration_stage1'
WORK=Path(__file__).resolve().parent
HOME=ROOT.parents[1]
FINAL=Path('C:/Users/86134/AppData/Local/Temp/ffn193_final_functional')
FREEZE='55c607dc'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x): p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
s=json.loads((FINAL/'summary.json').read_text(encoding='utf-8'))
assert s['status']=='passed' and len(s['cases'])==9
for rel,h in s['source_sha256'].items(): assert sha(P/rel)==h,rel
revision=subprocess.check_output(['git','rev-parse',FREEZE],cwd=ROOT,text=True).strip()
sources={}
for f in sorted(P.rglob('*')):
 if not f.is_file() or 'results' in f.relative_to(P).parts or '__pycache__' in f.parts or f.name=='SOURCE_MANIFEST.json':continue
 rel=f.relative_to(P).as_posix()
 assert f.suffix not in ('.vvp','.pyc','.db','.lib','.vcd','.ddc','.fsdb')
 blob=subprocess.check_output(['git','show',revision+':'+f.relative_to(ROOT).as_posix()],cwd=ROOT)
 assert hashlib.sha256(blob).hexdigest()==sha(f),rel
 sources[rel]=dict(sha256=sha(f),bytes=f.stat().st_size)
save(P/'SOURCE_MANIFEST.json',dict(schema_version=1,exact_source_revision=revision,files=sources,note='Execution snapshot bytes equal this commit; no licensed EDA run'))
result=P/'results/local_validation'
for f in FINAL.rglob('*'):
 if f.is_file() and (f.name in ('summary.json','SUMMARY.json','RESULT.json','result.json','compile.log','simulation.log','simulate.log') or f.name.endswith('_command.json')):
  dest=result/'final'/f.relative_to(FINAL);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest)
save(result/'flow_tests.json',dict(status='passed',tests_run=29,skipped=0,command='python -B flow/test_flow.py --tmp-root C:/Users/86134/AppData/Local/Temp/ffn193_flow_integrated',observed_returncode=0,scope='synthetic fixtures/control/Tcl parser; no VCS/DC/PT'))
archive_dir=HOME/'project_archives/ffn_calibration_stage1_issue193_20261025';archive_dir.mkdir(parents=True,exist_ok=True)
archive=archive_dir/'validation_evidence.tar.gz'
assert not archive.exists()
with tarfile.open(archive,'w:gz') as t:
 t.add(P/'SOURCE_MANIFEST.json',arcname='SOURCE_MANIFEST.json')
 t.add(result,arcname='results/local_validation')
record=dict(schema_version=1,id='ffn-stage1-193-rtl-20261025',name='FFN第一轮精确计数与整数恢复校准RTL',family='FFN/转换/部分和',registered_on='2026-10-25',owner='jieruiz',issue=193,evidence_level='RTL_FUNCTIONAL',status='functional_only_eda_prepared',stages=dict(functional='pass',synthesis='not_run',sta='not_run',power='not_run',postlayout='not_run'),boundary='N64; M1/M8; B4/B7; T64/T128; W7mag+sign; exact count CW20/21; integer restore coeff16/rshift6; signed64 saturating local sum. No OR, PRNG, comparator, SRAM, nonlinear or BF16 conversion.',conditions=dict(simulator='Icarus Verilog 10.1',functional_clock_period_ns=10,target_node_nm=55,target_frequency_MHz=100,technology_bound=False,seeds_M1=[17,31,193],seeds_M8=[17]),source=dict(git_commit=revision,source_manifest_sha256=sha(P/'SOURCE_MANIFEST.json'),binding='SOURCE_MANIFEST matches committed blob bytes and final functional source hashes',repository_path='architecture_tlm/ffn_calibration_stage1'),artifacts=[dict(path=str(archive),role='small_functional_evidence_archive',present_at_registration=True,required=True,sha256=sha(archive),bytes=archive.stat().st_size)],cases=[dict(case=c['case_id'],status=c['status'],configuration=next(i for i in json.loads((P/'cases.json').read_text())['cases'] if i['id']==c['case_id'])['parameters'],area_um2=None,power_W=None) for c in s['cases']],limitations=['Only integer arithmetic and handshake validation; VCS/DC/PT and silicon not run.','The 240s Icarus timeout is preserved; final software simulation limit 900s, not a hardware timing violation.','Frame chain supports one outstanding frame; restore II1 is not whole-frame II1.','Real quantization scales to coeff/rshift compiler and end-to-end model quality are not validated.','Main lacks the full registry; this PR adds one record only. Local registry union is a pending integration view.'],next_action='User runs two SS/100MHz smoke cases with licensed VCS/DC; inspect real critical paths before widening or power analysis')
rec=ROOT/'digital_circuit_simulation_registry/records'/ (record['id']+'.json');save(rec,record)
# Incremental local mirror: preserve every other record's exact bytes.
registry=HOME/'digital_circuit_simulation_registry'
before={f.name:sha(f) for f in (registry/'records').glob('*.json')}
spec=importlib.util.spec_from_file_location('registry',registry/'registry.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.add(rec);check=module.check();module.render()
after={f.name:sha(f) for f in (registry/'records').glob('*.json')}
assert all(after[k]==v for k,v in before.items())
assert sha(registry/'records'/rec.name)==sha(rec)
save(WORK/'REGISTRY_CHECK.json',dict(check=check,prior_records_unchanged=len(before),new_record_sha256=sha(rec),formal_registry_reference='pbit-tlm-attention-details-20261016 d6d33995754fcdcea99286e4ce43f91647aa231a, 56 published records',note='root union was 67 pending/mixed records; only our new record enters PR193, no claim all 68 are merged'))
# Portable ZIP; package is small source, docs and receipts, no compiled artifacts.
package=HOME/'ffn_calibration_stage1_20261025.zip'
assert not package.exists()
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for f in sorted(P.rglob('*')):
  if not f.is_file() or '__pycache__' in f.parts:continue
  assert f.suffix not in ('.vvp','.pyc','.db','.lib','.vcd','.ddc','.fsdb')
  info=zipfile.ZipInfo('ffn_calibration_stage1/'+f.relative_to(P).as_posix(),date_time=(2026,10,25,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
  z.writestr(info,f.read_bytes())
with zipfile.ZipFile(package) as z:
 assert z.testzip() is None
 for name in z.namelist():assert z.read(name)==(P/Path(name).relative_to('ffn_calibration_stage1')).read_bytes()
receipt=dict(source_revision=revision,package=str(package),package_sha256=sha(package),package_bytes=package.stat().st_size,evidence_archive=str(archive),evidence_sha256=sha(archive),functional_cases=9,flow_tests=29,licensed_EDA='not_run')
save(WORK/'DELIVERY.json',receipt);print(json.dumps(receipt,ensure_ascii=True))
