"""Persist production and unchanged legacy regression evidence for a release."""
import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline',default='46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[2]
    suites={
        'production':unittest.defaultTestLoader.discover(str(root/'architecture_tlm/cycle_v1'),top_level_dir=str(root)),
        'legacy':unittest.defaultTestLoader.loadTestsFromNames([
            'architecture_tlm.unified_v6.test_model',
            'architecture_tlm.unified_v6.test_rng_interface',
            'architecture_tlm.unified_v6.test_rng_integrated'])}
    results={}
    for name,suite in suites.items():
        log=io.StringIO()
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
        (args.output/(name+'.txt')).write_text(log.getvalue(),encoding='utf-8')
        results[name]={'tests':result.testsRun,'passed':result.wasSuccessful(),
            'failures':len(result.failures),'errors':len(result.errors)}
    unchanged_paths=['architecture_tlm/unified_v6','architecture_tlm/random_service','architecture_tlm/results']
    changed=subprocess.check_output(['git','diff','--name-only',args.baseline,'--',*unchanged_paths],cwd=root,text=True).splitlines()
    paths=sorted((root/'architecture_tlm/cycle_v1').glob('*.py'))
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'tests':results,
        'baseline':args.baseline,'legacy_changed_paths':changed,'legacy_scope':unchanged_paths,
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'source_sha256':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'independent_review':'separate audit/REVIEW_ZH.md; these production tests are not counted as independent'}
    (args.output/'RESULT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'tests':results,'legacy_changed_paths':changed}))
    if changed or not all(result['passed'] for result in results.values()): raise SystemExit(1)


if __name__=='__main__': main()
