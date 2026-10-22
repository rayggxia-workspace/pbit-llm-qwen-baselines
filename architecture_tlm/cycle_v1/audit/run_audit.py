"""Persist independent test outcomes and exact implementation/test source hashes."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import unittest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new audit output directory")
    here = Path(__file__).resolve().parent
    root = here.parents[2]
    modules = ["architecture_tlm.cycle_v1.audit.test_"+name+"_adversarial" for name in ("core", "ffn", "attention", "native", "layer", "gqa")]
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    paths = sorted((here.parent).glob("*.py")) + sorted(here.glob("*.py"))
    paths += [root/"architecture_tlm"/name for name in ("random_service/service.py", "random_service/model.py",
              "random_service/backends.py", "random_service/__init__.py", "random_service/shared64_mapping.json",
              "unified_v6/rng_integrated.py")]
    source_hashes = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True)
    report = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), python=platform.python_version(),
                  git_head=proc.stdout.strip(), source_sha256=source_hashes,
                  tests_run=result.testsRun, successful=result.wasSuccessful(),
                  failures=[dict(test=str(test), detail=detail) for test, detail in result.failures],
                  errors=[dict(test=str(test), detail=detail) for test, detail in result.errors],
                  deterministic_subcases=dict(random_dag_seeds=32, random_byte_memory_seeds=32,
                                             synthetic_scalar_ffn_profiles=4),
                  scope="Independent hand-derived timing, byte memory and numeric/trajectory oracles; not RTL/STA/PPA/PPL",
                  modules=modules)
    args.output.mkdir(parents=True)
    (args.output/"TEST_LOG.txt").write_text(log.getvalue(), encoding="utf-8")
    (args.output/"RESULT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"successful":report["successful"], "tests":report["tests_run"], "output":str(args.output)}))
    if not report["successful"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
