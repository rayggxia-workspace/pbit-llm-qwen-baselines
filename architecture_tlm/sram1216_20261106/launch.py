from pathlib import Path
import argparse, importlib, sys
from bootstrap import use_runtime
p=argparse.ArgumentParser(add_help=False)
p.add_argument('--runtime',type=Path,required=True)
p.add_argument('--dependencies',type=Path,required=True)
p.add_argument('--tests',action='store_true')
a,remaining=p.parse_known_args()
identity=use_runtime(a.runtime,a.dependencies)
if a.tests:
    import unittest
    suite=unittest.defaultTestLoader.loadTestsFromName('architecture_tlm.sram1216_20261106.test_model')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
from architecture_tlm.sram1216_20261106.run import main
main(remaining,a.runtime,identity)
