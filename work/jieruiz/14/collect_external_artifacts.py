"""Read-only index of completed DRAM request traces/logs and the reused bridge runtime."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*2**20),b''):h.update(block)
    return h.hexdigest()


def artifact(path):
    p=Path(path)
    return {'path':str(p.resolve()),'bytes':p.stat().st_size,'sha256':sha(p)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,required=True)
    p.add_argument('--source-sha256',required=True)
    a=p.parse_args()
    assert re.fullmatch('[0-9a-f]{64}',a.source_sha256)
    snapshot=a.project/'tlm_b5964b165dfe'
    expected=json.loads((snapshot/'architecture_tlm/llama7b/dram/BRIDGE_PROVENANCE.json').read_text())
    records=[]
    for backend,count in [('dramsys_Staggered',36),('dramsys_NoPowerDown',8)]:
        results=[f for f in (a.project/'outputs'/backend).glob('*.json') if '_dram' not in f.name]
        assert len(results)==count,('Incomplete original DRAM artifacts',backend)
        for result in sorted(results):
            for suffix in ['.bridge.log','.requests.jsonl.gz']:
                file=result.with_name(result.stem+'_dram'+suffix)
                assert file.is_file() and file.stat().st_size>0,file
                records.append({'case':result.stem,'backend':backend,**artifact(file)})
    binary=Path(expected['runtime_location'])
    bridge=artifact(binary);assert bridge['sha256']==expected['binary_sha256']
    links=subprocess.check_output(['ldd',str(binary)],text=True)
    libraries={}
    for name,field in [('libdramsys.so','libdramsys_so_sha256'),('libDRAMPower.so','libDRAMPower_so_sha256')]:
        matches=[re.search(r'=>\s+(/\S+)',line) for line in links.splitlines() if name in line]
        assert len(matches)==1 and matches[0],name
        record=artifact(Path(matches[0].group(1)))
        assert record['sha256']==expected[field],name
        libraries[name]=record
    print(json.dumps({'project':str(a.project),'scope':'Completed 44 DRAM cases: original gzip request streams and bridge logs, no rewritten bytes; live binary/library hashes match prior verified runtime.',
        'collector_declared_source_sha256':a.source_sha256,'DRAM_cases':44,'original_artifacts':records,
        'bridge':bridge,'linked_libraries':libraries},indent=2))


if __name__=='__main__':main()
