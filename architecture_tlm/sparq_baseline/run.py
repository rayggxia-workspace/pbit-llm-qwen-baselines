"""Generate replayable analytic ledgers without PyTorch, GPU or EDA."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .ledger import Config, Rates, build_ledger, synthetic_indices


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokens", type=int, nargs="+", default=[128, 512, 2048, 8192, 32768])
    parser.add_argument("--layouts", nargs="+", choices=["dual_k", "token_major"], default=["dual_k", "token_major"])
    parser.add_argument("--channels", type=int, default=32)
    parser.add_argument("--selected-tokens", type=int, default=128)
    parser.add_argument("--local-tokens", type=int, default=32)
    parser.add_argument("--query-heads", type=int, default=32)
    parser.add_argument("--kv-heads", type=int, default=8)
    parser.add_argument("--head-dim", type=int, default=128)
    parser.add_argument("--burst-bytes", type=int, default=64)
    parser.add_argument("--capacity-tokens", type=int)
    parser.add_argument("--patterns", nargs="+", choices=["contiguous", "spread"], default=["contiguous", "spread"])
    parser.add_argument("--indices-json", type=Path, help="Actual per-KV channel_ids/token_ids; requires one --tokens value")
    parser.add_argument("--rates-json", type=Path, help="Explicit aggregate hypothetical resource rates, never PPA prices")
    parser.add_argument("--illustrative-rates", action="store_true", help="Use labeled uncharacterized Rates defaults")
    parser.add_argument("--out", type=Path, required=True, help="New JSON path; existing files are never overwritten")
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error("output exists; choose a new path")
    if args.indices_json and len(args.tokens) != 1:
        parser.error("--indices-json requires exactly one --tokens value")
    if args.rates_json and args.illustrative_rates:
        parser.error("choose either --rates-json or --illustrative-rates")
    rates = Rates(**json.loads(args.rates_json.read_text(encoding="utf-8"))) if args.rates_json else Rates() if args.illustrative_rates else None
    supplied = json.loads(args.indices_json.read_text(encoding="utf-8")) if args.indices_json else None
    cases = []
    for n in args.tokens:
        for layout in args.layouts:
            for pattern in (["supplied"] if supplied else args.patterns):
                c = Config(n, query_heads=args.query_heads, kv_heads=args.kv_heads, head_dim=args.head_dim,
                           channels=args.channels, selected_tokens=args.selected_tokens, local_tokens=args.local_tokens,
                           layout=layout, burst_bytes=args.burst_bytes, capacity_tokens=args.capacity_tokens)
                indices = supplied or synthetic_indices(c, pattern)
                provenance = dict(indices.get("provenance", {}))
                if args.indices_json:
                    provenance.update(kind="caller_supplied_selection_trace", input_sha256=hashlib.sha256(args.indices_json.read_bytes()).hexdigest())
                case = build_ledger(c, indices["channel_ids"], indices["token_ids"], rates, provenance=provenance,
                                    dense_fallback_kv_heads=indices.get("dense_fallback_kv_heads", []))
                cases.append(case)
    root = Path(__file__).resolve().parent
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob("*.py"))}
    result = {"schema_version": 1, "status": "analytic_counts_completed_no_hardware_measurement",
              "source_sha256": source_hashes,
              "model_target": {"repository": "Qwen/Qwen3-4B", "revision": "1cfa9a7208912126459214e8b04321603b3df60c",
                               "weights_loaded": False, "applies_only_if_geometry_matches_config": True},
              "rates": asdict(rates) if rates else None,
              "cases": cases}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"cases": len(cases), "status": result["status"], "output": str(args.out),
                      "sha256": hashlib.sha256(args.out.read_bytes()).hexdigest()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
