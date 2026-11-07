from pathlib import Path
import importlib.util
import unittest
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
p=ROOT/'architecture_tlm/norm_stream_20261106/bootstrap.py'
spec=importlib.util.spec_from_file_location('norm_boot',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.use_runtime(HERE/'runtime')
suite=unittest.defaultTestLoader.loadTestsFromName('architecture_tlm.norm_stream_20261106.test_model')
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
