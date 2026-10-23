"""Compare a real cropped FFN fixture to a separately written scalar oracle."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import struct
import time

from architecture_tlm.cycle_v1 import contracts, ffn, kernel, memory
from architecture_tlm.cycle_v1.audit import scalar_oracles


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("native", "replay"), default="replay")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("preserve prior audit evidence: choose a new output")
    frozen = json.loads(args.fixture.read_text(encoding="utf-8"))
    values = copy.deepcopy(frozen["ffn"])
    layer = frozen["provenance"]["layer"]
    threshold_seed = 88100+layer if args.backend == "replay" else None
    if args.backend == "replay":
        values["thresholds"] = scalar_oracles.frozen_thresholds(len(values["x"]), len(values["wg"]["codes"]), seed=threshold_seed)
    config = ffn.FFNConfig(random_backend=args.backend)
    engine = ffn.make_kernel(config)
    state = ffn.build_ffn(engine, values, config)
    started = time.perf_counter()
    result = engine.run(mode="event")
    elapsed = time.perf_counter()-started
    if args.backend == "native":
        values["thresholds"] = {phase:[state["thresholds"][phase, i] for i in range((size+63)//64)]
            for phase, size in (("x", len(values["x"])), ("z", len(values["wg"]["codes"])))}
    expected = scalar_oracles.scalar_ffn(values)
    checks = []
    for field in ("gate", "up", "z", "projected", "output"):
        actual = state[field]
        oracle = expected[field]
        actual_bytes = struct.pack("<"+"f"*len(actual), *actual)
        oracle_bytes = struct.pack("<"+"f"*len(oracle), *oracle)
        checks.append(dict(field=field, values=len(actual), bit_equal=actual_bytes == oracle_bytes,
                           max_absolute_difference=max(abs(a-b) for a, b in zip(actual, oracle)),
                           actual_sha256=hashlib.sha256(actual_bytes).hexdigest(),
                           oracle_sha256=hashlib.sha256(oracle_bytes).hexdigest()))
    report = dict(scope="Independent scalar FP32-boundary audit of one real cropped FFN; not full-layer/model/PPL or physical hardware evidence",
                  timestamp_utc=datetime.now(timezone.utc).isoformat(), python=platform.python_version(),
                  fixture_sha256=sha(args.fixture), source_fixture_name=args.fixture.name,
                  provenance=frozen["provenance"], threshold_seed=threshold_seed, random_backend=args.backend,
                  native_random=state.get("native_random"),
                  thresholds_sha256=hashlib.sha256(json.dumps(values["thresholds"], sort_keys=True).encode()).hexdigest(),
                  config={key:getattr(config,key) for key in config.__dataclass_fields__},
                  execution_source_sha256={"contracts.py":sha(contracts.__file__), "ffn.py":sha(ffn.__file__),
                      "kernel.py":sha(kernel.__file__), "memory.py":sha(memory.__file__),
                      "audit/scalar_oracles.py":sha(scalar_oracles.__file__), "audit/verify_real_fixture.py":sha(__file__)},
                  checks=checks, passed=all(row["bit_equal"] for row in checks),
                  operations=len(result.completion_ps), finish_ps=result.finish_ps, wall_seconds=elapsed)
    architecture_root = Path(ffn.__file__).resolve().parents[1]
    for relative in ("cycle_v1/rng_protocol.py", "random_service/__init__.py", "random_service/model.py",
                     "random_service/backends.py", "random_service/service.py", "random_service/shared64_mapping.json",
                     "unified_v6/rng_integrated.py"):
        report["execution_source_sha256"]["architecture_tlm/"+relative] = sha(architecture_root/relative)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"passed":report["passed"], "layer":layer, "operations":report["operations"],
                      "wall_seconds":elapsed, "output":str(args.output)}))
    if not report["passed"]:
        raise AssertionError("independent scalar reference differs")


if __name__ == "__main__":
    main()
