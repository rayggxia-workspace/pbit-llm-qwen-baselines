"""Audit disabled timing arcs and minimum paths without repeating synthesis."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    root=Path(os.environ['AC_RUN_ROOT']);src=Path(__file__).parent
    work=root/'timing_audit_v1';work.mkdir(exist_ok=False)
    for name,x in json.loads((src/'SOURCE.json').read_text())['files'].items():assert sha(src/name)==x['sha256']
    cases=json.loads((root/'snapshots/v3/CASES.json').read_text())['tops'];records=[]
    for spec in cases:
        top=spec['top'];dc=[p.parent for p in (root/'results').glob('*_dc_'+top+'/SYNTHESIS_COMPLETE.txt')]
        assert len(dc)==1;dc=dc[0];out=work/top;out.mkdir()
        os.environ.update(AC_TOP=top,AC_NETLIST=str(dc/'mapped.v'),AC_SDC=str(dc/'mapped.sdc'))
        with (out/'pt.log').open('wb') as f:p=subprocess.run(['pt_shell','-f',str(src/'timing_audit.tcl')],cwd=str(out),stdout=f,stderr=subprocess.STDOUT)
        assert p.returncode==0 and (out/'AUDIT_COMPLETE.txt').exists(),top
        records.append(dict(top=top,netlist_sha256=sha(dc/'mapped.v'),sdc_sha256=sha(dc/'mapped.sdc')))
    index={str(p.relative_to(root)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in work.rglob('*') if p.is_file()}
    (work/'INDEX.json').write_text(json.dumps(dict(records=records,files=index),indent=2)+'\n')
    archive=root/'timing_audit_v1.tar.gz'
    with tarfile.open(str(archive),'w:gz') as t:t.add(str(work),arcname='timing_audit_v1')
    receipt=dict(path=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),job=os.environ['SLURM_JOB_ID'])
    (root/'TIMING_AUDIT_COLLECTION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))

if __name__=='__main__':main()
