"""Local source-package audit. Does not run licensed EDA or publish anything."""
import hashlib,json,subprocess,sys,zipfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[3]
BASE=REPO.parents[1]
ROOT=REPO/'architecture_tlm/sc_cim_frontend_20261023'
OUT=Path(__file__).resolve().parent
PREFIX='sc_cim_frontend_ppa_20261023_v2'

def sha(b):return hashlib.sha256(b).hexdigest()

def main():
    archive=BASE/(PREFIX+'.zip')
    with zipfile.ZipFile(archive) as z:
        manifest=json.loads(z.read(PREFIX+'/SOURCE_MANIFEST.json'))
        for name,h in manifest.items():
            raw=z.read(PREFIX+'/'+name)
            assert sha(raw)==h and raw==(ROOT/name).read_bytes(),name
            assert b'\r\n' not in raw,name
    old=BASE/'sc_cim_frontend_ppa_20261023_v1.zip'
    unchanged=[]
    with zipfile.ZipFile(old) as z:
        for name in manifest:
            if name.startswith('rtl/') or name=='sim/tb.sv':
                assert z.read('sc_cim_frontend_20261023/'+name)==(ROOT/name).read_bytes(),name
                unchanged.append(name)
    commands=[]
    for folder,pattern in [('flow','test_delivery.py'),('sim','test_flow.py')]:
        cmd=[sys.executable,'-m','unittest','discover','-s',folder,'-p',pattern,'-v']
        p=subprocess.run(cmd,cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (OUT/('V2_'+folder+'_tests.log')).write_bytes(p.stdout)
        commands.append(dict(command=cmd,exit_code=p.returncode))
        if p.returncode:raise RuntimeError(p.stdout.decode('utf-8',errors='replace'))
    raw=BASE/'project_archives/cim_frontend_20261023/v2_local_check2/VALIDATION.json'
    v=json.loads(raw.read_text())
    assert len(v['cases'])==4 and sum(len(c['windows']) for c in v['cases'])==48
    result=dict(package=dict(path=str(archive),bytes=archive.stat().st_size,sha256=sha(archive.read_bytes())),
                source_manifest_sha256=sha((ROOT/'SOURCE_MANIFEST.json').read_bytes()),files=len(manifest),
                rtl_and_tb_unchanged=unchanged,tests=commands,rtl_validation=dict(path=str(raw),sha256=sha(raw.read_bytes())),
                status='LOCAL_CHECKS_PASS_EDA_PENDING')
    (OUT/'V2_VALIDATION.json').write_bytes((json.dumps(result,indent=2)+'\n').encode('utf-8'))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
