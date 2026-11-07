"""Direct entry point when dependencies live in a separate immutable runtime."""
from pathlib import Path
import argparse
import importlib.util
import sys

p=argparse.ArgumentParser(add_help=False)
p.add_argument('--runtime',type=Path,required=True)
p.add_argument('--tests',action='store_true')
args,remaining=p.parse_known_args()
spec=importlib.util.spec_from_file_location('norm_runtime_boot',Path(__file__).with_name('bootstrap.py'))
boot=importlib.util.module_from_spec(spec);spec.loader.exec_module(boot)
boot.use_runtime(args.runtime)
if args.tests:
    import unittest
    suite=unittest.defaultTestLoader.loadTestsFromName('architecture_tlm.norm_stream_20261106.test_model')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
from architecture_tlm.norm_stream_20261106.run import main
sys.argv=[sys.argv[0],'--runtime',str(args.runtime),*remaining]
main()
