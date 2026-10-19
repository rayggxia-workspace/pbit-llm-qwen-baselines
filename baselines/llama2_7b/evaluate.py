"""Official Llama-2-7B BF16/SDPA full-WT2 reference; execute via Slurm."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

from protocol import CORPUS_SHA256, EXPECTED_SHAPE, sha256, verify_identity, windows, write_json


def source_identity() -> dict:
    source = Path(__file__).resolve().parent
    files = {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size}
             for p in sorted(source.iterdir()) if p.is_file()}
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True,
            stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(
            ["git", "-C", str(source), "status", "--porcelain"], text=True))
        if dirty:
            raise RuntimeError("Commit source before immutable baseline execution")
    except (FileNotFoundError, subprocess.CalledProcessError):
        commit, dirty = os.environ.get("SOURCE_COMMIT", ""), None
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("An immutable snapshot requires SOURCE_COMMIT=<40-hex Git SHA>")
    return {"repository": "rayggxia-workspace/pbit-llm-qwen-baselines",
            "commit": commit, "dirty": dirty, "files": files}


def evaluate_window(model, ids, item, torch, functional):
    """No model.loss mean: FP32 per-token CE followed by FP64 reduction."""
    batch = ids[:, item.begin:item.end].to("cuda")
    output = model(input_ids=batch, use_cache=False, return_dict=True)
    nll64 = torch.zeros((), device="cuda", dtype=torch.float64)
    counted = 0
    # Materialize FP32 only for newly scored logits, in bounded chunks.
    for start in range(item.logits_start, item.end - item.begin - 1, 256):
        stop = min(start + 256, item.end - item.begin - 1)
        logits = output.logits[:, start:stop, :].float().reshape(-1, output.logits.shape[-1])
        targets = batch[:, start + 1:stop + 1].reshape(-1)
        losses = functional.cross_entropy(logits, targets, reduction="none")
        if not bool(torch.isfinite(losses).all()):
            raise RuntimeError("Non-finite full-corpus token NLL")
        nll64 += losses.to(torch.float64).sum()
        counted += targets.numel()
    if counted != item.count:
        raise AssertionError("Shifted logits/labels token count mismatch")
    result = nll64.item()
    del output, batch
    return result, counted


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--identity-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--windows", nargs="+", type=int, default=[2048, 4096])
    parser.add_argument("--stride", type=int, default=512)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("GPU evaluation must be submitted through Slurm")
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite output: {args.output}")
    if len(set(args.windows)) != len(args.windows) or not args.windows:
        raise ValueError("Evaluation windows must be nonempty and unique")
    if any(w < 2 or w > 4096 or not 0 < args.stride < w for w in args.windows):
        raise ValueError("Require 0<stride<window<=4096; no context extrapolation")
    source = source_identity()
    identity = verify_identity(args.model, args.identity_manifest)
    data_sha = sha256(args.data)
    if data_sha != CORPUS_SHA256:
        raise RuntimeError(f"Full WT2 raw checksum mismatch: {data_sha}")
    text = args.data.read_text(encoding="utf-8")
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import torch
    import torch.nn.functional as functional
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from transformers.models.llama.modeling_llama import LlamaSdpaAttention
    if transformers.__version__ != "4.45.2":
        raise RuntimeError("Inspected reference requires Transformers 4.45.2")
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("Slurm job requires a BF16-capable CUDA device")
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    random.seed(args.seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    args.output.mkdir(parents=True, exist_ok=False)
    protocol = {
        "name": "full_wikitext2_raw_sliding_window_ppl", "windows": args.windows,
        "stride": args.stride, "seed": args.seed, "precision": "BF16 model; FP32 CE; FP64 NLL sum",
        "attention": "Transformers 4.45.2 SDPA", "batch_size": 1,
        "add_special_tokens": False, "target_positions": "1..N-1 exactly once",
        "first_window": "score targets 1..window-1", "following_windows": "score newly reached targets only",
        "position_ids": "reset to 0 inside each window, native RoPE; no global extrapolation",
        "raw_sha256": data_sha, "data_bytes": args.data.stat().st_size,
        "data_path": str(args.data.resolve()), "model_path": str(args.model.resolve()),
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
    }
    write_json(args.output / "protocol.json", protocol)
    write_json(args.output / "source.json", source)
    write_json(args.output / "identity.json", identity)
    command = {"argv": [sys.executable, *sys.argv], "shell_display": shlex.join([sys.executable, *sys.argv])}
    write_json(args.output / "command.json", command)
    environment = {
        "python": sys.version, "platform": platform.platform(), "torch": torch.__version__,
        "transformers": transformers.__version__, "cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(), "gpu": torch.cuda.get_device_name(0),
        "gpu_total_bytes": torch.cuda.get_device_properties(0).total_memory,
        "torch_threads": torch.get_num_threads(), "deterministic_algorithms": True,
        "tf32": False, "power_measurement": "not performed",
        "sdpa_backends": {"flash_enabled": torch.backends.cuda.flash_sdp_enabled(),
                          "mem_efficient_enabled": torch.backends.cuda.mem_efficient_sdp_enabled(),
                          "math_enabled": torch.backends.cuda.math_sdp_enabled()},
    }
    write_json(args.output / "environment.json", environment)
    tokenizer = AutoTokenizer.from_pretrained(str(args.model), local_files_only=True,
                                              trust_remote_code=False, use_fast=True)
    ids = tokenizer(text, add_special_tokens=False, return_tensors="pt").input_ids
    del text
    if ids.shape[1] < 2:
        raise RuntimeError("WT2 tokenized corpus is too short")
    token_sha = hashlib.sha256(ids.numpy().astype("<i8", copy=False).tobytes()).hexdigest()
    token_info = {"tokens": ids.shape[1], "expected_scored_tokens": ids.shape[1] - 1,
                  "token_ids_encoding": "little-endian signed int64", "token_ids_sha256": token_sha}
    write_json(args.output / "tokenization.json", token_info)
    torch.cuda.synchronize()
    load_start = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(
        str(args.model), torch_dtype=torch.bfloat16, attn_implementation="sdpa",
        local_files_only=True, trust_remote_code=False,
        use_safetensors=identity["use_safetensors"], low_cpu_mem_usage=True,
    ).eval().to("cuda")
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - load_start
    if len(model.model.layers) != 32 or any(
            not isinstance(layer.self_attn, LlamaSdpaAttention) for layer in model.model.layers):
        raise RuntimeError("Unexpected model/attention implementation")
    if model.config._attn_implementation != "sdpa" or model.dtype != torch.bfloat16:
        raise RuntimeError("Reference must use BF16 SDPA")
    for key, expected in EXPECTED_SHAPE.items():
        if getattr(model.config, key, None) != expected:
            raise RuntimeError(f"Loaded configuration mismatch: {key}")
    with torch.inference_mode():
        warmup = model(input_ids=ids[:, :16].to("cuda"), use_cache=False).logits
        if not bool(torch.isfinite(warmup).all()):
            raise RuntimeError("Warmup produced non-finite logits")
        del warmup
        torch.cuda.synchronize()
        results = []
        for length in args.windows:
            torch.cuda.reset_peak_memory_stats()
            start_time = time.perf_counter()
            total_nll, count, number = 0.0, 0, 0
            with (args.output / f"windows_{length}.jsonl").open("x", encoding="utf-8", newline="\n") as log:
                for number, item in enumerate(windows(ids.shape[1], length, args.stride), 1):
                    nll, targets = evaluate_window(model, ids, item, torch, functional)
                    total_nll = math.fsum((total_nll, nll))
                    count += targets
                    record = {"number": number, **item.record(), "nll": nll,
                              "scored_so_far": count, "elapsed_seconds": time.perf_counter() - start_time}
                    log.write(json.dumps(record, allow_nan=False, separators=(",", ":")) + "\n")
                    log.flush()
                    print(f"window_length={length} window={number} end={item.end}/{ids.shape[1]} "
                          f"scored={count}/{ids.shape[1]-1}", flush=True)
            torch.cuda.synchronize()
            seconds = time.perf_counter() - start_time
            if count != ids.shape[1] - 1:
                raise AssertionError("Full-corpus scoring must count every real next token exactly once")
            record = {"window": length, "stride": args.stride, "windows": number,
                      "corpus_tokens": ids.shape[1], "scored_tokens": count, "total_nll": total_nll,
                      "mean_nll": total_nll / count, "ppl": math.exp(total_nll / count),
                      "wall_seconds": seconds, "scored_tokens_per_second": count / seconds,
                      "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                      "peak_reserved_bytes": torch.cuda.max_memory_reserved()}
            write_json(args.output / f"ppl_{length}.json", record)
            results.append(record)
        prompts = ["The capital of France is", "The purpose of a computer is"]
        generations = []
        for prompt in prompts:
            prompt_ids = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).input_ids.to("cuda")
            generated = model.generate(prompt_ids, max_new_tokens=32, do_sample=False,
                                       use_cache=True, pad_token_id=tokenizer.eos_token_id,
                                       eos_token_id=tokenizer.eos_token_id)
            suffix = generated[0, prompt_ids.shape[1]:].tolist()
            if not suffix or not all(0 <= x < model.config.vocab_size for x in suffix):
                raise RuntimeError("Greedy smoke output has no valid token sequence")
            generations.append({"prompt": prompt, "new_token_ids": suffix,
                                "completion": tokenizer.decode(suffix, skip_special_tokens=True),
                                "note": "Smoke check only; not an accuracy benchmark"})
        write_json(args.output / "greedy_smoke.json", generations)
    summary = {"status": "completed", "model": identity["repository"], "revision": identity["revision"],
               "code_commit": source["commit"], "data_sha256": data_sha,
               "tokenization": token_info, "load_seconds": load_seconds, "ppl": results,
               "power_or_energy": "not measured; GPU time/memory are not ASIC energy estimates"}
    write_json(args.output / "summary.json", summary)
    artifacts = {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size}
                 for p in sorted(args.output.iterdir()) if p.is_file()}
    write_json(args.output / "ARTIFACT_MANIFEST.json", artifacts)
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
