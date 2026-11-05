"""Rebuild local metadata from frozen RTL run; does not run simulations."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

TASK=Path(__file__).resolve().parents[4]
WORKSPACE=TASK.parent.parent
PKG=TASK/'architecture_tlm/random_service/pbit8_char'
RAW=WORKSPACE/'project_archives/pbit8_char_issue95_20261027/rtl_v2'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode())

res=PKG/'results';res.mkdir(exist_ok=True)
shutil.copyfile(RAW/'RESULT.json',res/'VALIDATION.json')
shutil.copyfile(RAW/'SOURCE_MANIFEST.json',res/'SOURCE_MANIFEST.json')
m=json.loads((res/'SOURCE_MANIFEST.json').read_text())
assert all(sha(PKG/f)==v for f,v in m.items())
archive=RAW.with_suffix('.zip')
if not archive.exists():
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(RAW.rglob('*')):
            if f.is_file():z.write(f,f.relative_to(RAW).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for f in RAW.rglob('*'):
        if f.is_file():assert hashlib.sha256(z.read(f.relative_to(RAW).as_posix())).hexdigest()==sha(f)
summary=json.loads((res/'VALIDATION.json').read_text())
record={
 'schema_version':1,'id':'rng-pbit8-95-20261027',
 'name':'8位随机比较器与signed8 sigmoid表：五核RTL活动','family':'随机源架构',
 'registered_on':'2026-10-27','owner':'rayggxia','issue':95,
 'evidence_level':'RTL_FUNCTIONAL','status':'functional_pass_ppa_pending',
 'stages':{'functional':'pass','synthesis':'not_run','sta':'not_run','power':'not_run','postlayout':'not_run'},
 'boundary':'纯8位LT、q/256端点比较、256x9组合sigmoid表、寄存表、LUT+比较+输出寄存；无PRNG/物理源/输入转换/ICG/布线',
 'conditions':{'node_nm':None,'corner':None,'voltage_V':None,'temperature_C':None,
   'clock_MHz':100,'seeds':[17,503,1009],'window_ns':40960,'load_pF':None,
   'sdf':False,'spef':False,'cts':False,'activity':'五种合成活动；307200计量拍；工艺EDA尚未执行'},
 'source':{'git_commit':None,'source_manifest_sha256':sha(res/'SOURCE_MANIFEST.json'),
   'binding':'architecture_tlm/random_service/pbit8_char/results/SOURCE_MANIFEST.json为精确执行源码；main d83eeb1f上新增；不冒用登记时HEAD'},
 'artifacts':[{'path':f.relative_to(TASK).as_posix(),'role':role,
   'present_at_registration':True,'required':True,'sha256':sha(f),'bytes':f.stat().st_size}
   for f,role in [(res/'VALIDATION.json','functional_summary'),(res/'SOURCE_MANIFEST.json','executed_sources')]],
 'cases':[{k:c[k] for k in ('top','mode','seed','cycles','enabled','start_ns','end_ns','functional','power','area_um2','total_uW')}
    for c in summary['runs']],
 'limitations':['仅RTL功能与活动，不是已测PPA；Tcl仅stub语法检查，未执行实际EDA',
   'idle与cadence64假定上游保持输入；en不是ICG',
   '固定三seed激励不是物理熵或模型载荷；不继承LLM质量',
   '完整原始VCD/日志留本机归档，public索引不等于共享访问权限'],
 'next_action':'用户工艺库下逐top DC→门级同激励→STA/PT；三seed、覆盖/XZ/单位/库表检查通过后同Issue登记结果'}
save(TASK/'digital_circuit_simulation_registry/records/rng-pbit8-95-20261027.json',record)
save(Path(__file__).parent/'RAW_INDEX.json',{
 'archive_relative_to_workspace':archive.relative_to(WORKSPACE).as_posix(),
 'bytes':archive.stat().st_size,'sha256':sha(archive),'status':'local archive; no public download',
 'first_attempt':'rtl_v1: sandbox WinError623 before Icarus launch; retained; rtl_v2 same source succeeded outside sandbox',
 'tcl_check':'four stub parser checks pass; no EDA semantic validation'})
print('Archive verified:',archive.stat().st_size,sha(archive))
