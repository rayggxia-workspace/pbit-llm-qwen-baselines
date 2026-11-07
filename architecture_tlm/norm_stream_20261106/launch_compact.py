"""New compact entry; original submitted norm sources stay immutable."""
from pathlib import Path
import argparse
import importlib.util
import sys

p=argparse.ArgumentParser(add_help=False)
p.add_argument('--runtime',type=Path,required=True)
p.add_argument('--tests',action='store_true')
args,remaining=p.parse_known_args()
spec=importlib.util.spec_from_file_location('compact_boot',Path(__file__).with_name('bootstrap.py'))
boot=importlib.util.module_from_spec(spec);spec.loader.exec_module(boot)
boot.use_runtime(args.runtime)
if args.tests:
    import unittest
    suite=unittest.defaultTestLoader.loadTestsFromNames([
        'architecture_tlm.norm_stream_20261106.test_model',
        'architecture_tlm.norm_stream_20261106.test_compact'])
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if r.wasSuccessful() else 1)
from architecture_tlm.norm_stream_20261106 import compact,model
model.make_model=compact.make_model
from architecture_tlm.norm_stream_20261106.run import main
sys.argv=[sys.argv[0],'--runtime',str(args.runtime),'--profile','stream_2m',*remaining]
main()
