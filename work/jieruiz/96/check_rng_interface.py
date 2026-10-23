"""Record actual new interface tests and existing regressions, no PPL/EDA."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
OUT=Path(__file__).resolve().parent
tempfile.tempdir=str(OUT/'test_tmp')
Path(tempfile.tempdir).mkdir(exist_ok=True)


def main():
    suites={
        'new_connection':unittest.defaultTestLoader.loadTestsFromName(
            'architecture_tlm.unified_v6.test_rng_interface'),
        'existing_whole_model':unittest.defaultTestLoader.loadTestsFromName(
            'architecture_tlm.unified_v6.test_model'),
        'existing_random_service':unittest.defaultTestLoader.discover(
            str(ROOT/'architecture_tlm/random_service/tests')),
    }
    groups={}
    for name,suite in suites.items():
        log=io.StringIO();r=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
        (OUT/('RNG_'+name+'.log')).write_text(log.getvalue(),encoding='utf-8',newline='\n')
        groups[name]=dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skips=len(r.skipped))
        if not r.wasSuccessful():
            print(log.getvalue());raise SystemExit(1)
    from architecture_tlm.unified_v6.test_rng_interface import sampler_probe
    from winner_hold_tlm_v5 import WinnerHoldSampler
    from corrected_rejection_tlm_v5 import CorrectedRejectionSampler
    probes=[]
    for cls in (WinnerHoldSampler,CorrectedRejectionSampler):
        for seed in range(3):
            net,src,_,out,r=sampler_probe(cls,seed)
            probes.append(dict(sampler=r['sampler'],seed=seed,samples=len(out),
                elapsed_cycles=r['elapsed_cycles'],end_ns=r['end_ns'],
                proposal_frames=r['actions']['proposal_frames'],source=src.report()))
    paths=['architecture_tlm/unified_v6/rng_frontend.py',
           'architecture_tlm/unified_v6/test_rng_interface.py',
           'work/jieruiz/96/check_rng_interface.py',
           'architecture_tlm/random_service/model.py',
           'architecture_tlm/random_service/backends.py',
           'architecture_tlm/random_service/service.py',
           'architecture_tlm/random_service/sampler_adapter.py',
           'architecture_tlm/parallel_sampler_v5.py']
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    checks=[]
    for p in paths:
        raw=(ROOT/p).read_bytes()
        archived=subprocess.check_output(['git','show',head+':'+p],cwd=ROOT)
        if raw!=archived:raise RuntimeError('commit execution sources before archiving '+p)
        checks.append(dict(path=p,sha256=hashlib.sha256(raw).hexdigest()))
    record=dict(execution_commit=head,groups=groups,probes=probes,source_files=checks,
        passed=True,seed_mode='fixture; three deterministic tests, not physical entropy',
        boundary='small connection proof; FullDecode default unchanged; no new PPL/PT/GPU/DRAMSys')
    target=OUT/'RNG_INTERFACE_VALIDATION.json'
    if target.exists():raise FileExistsError('preserve original validation: '+str(target))
    target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(execution_commit=head,passed=True,groups=groups,
        probes=[{k:v for k,v in p.items() if k!='source'} for p in probes])))


if __name__=='__main__':main()
