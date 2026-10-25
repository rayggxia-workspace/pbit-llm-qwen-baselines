"""Freeze exactly committed source bytes for the HBM extension."""
import hashlib,json,pathlib,subprocess,sys,tarfile
ROOT=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from architecture_tlm.unified_v6.run import source_record

record=source_record()
for rel in ['work/jieruiz/186/run_schedule_case.py','work/jieruiz/186/HBM_MATRIX.json','work/jieruiz/186/probe_hbm.py','architecture_tlm/unified_v6/probes/dramsys_bridge/bridge_sg_v6_audit.cpp','architecture_tlm/unified_v6/probes/dramsys_bridge/CMakeLists.txt']:
    b=(ROOT/rel).read_bytes()
    assert subprocess.check_output(['git','show',record['commit']+':'+rel],cwd=ROOT)==b
    record['files'][rel]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
work=ROOT/'work/jieruiz/186';manifest=work/('HBM_SOURCE_'+record['commit'][:8]+'.json')
manifest.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
package=work/('hbm_'+record['commit'][:8]+'.tar.gz')
with tarfile.open(package,'x:gz') as tar:
    for rel in record['files']:tar.add(ROOT/rel,arcname=rel,recursive=False)
    tar.add(manifest,arcname='work/jieruiz/186/SOURCE.json')
print(json.dumps(dict(commit=record['commit'],package=str(package),sha256=hashlib.sha256(package.read_bytes()).hexdigest(),bytes=package.stat().st_size)))
