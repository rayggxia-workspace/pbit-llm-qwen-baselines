"""Unmodified Qwen3 BF16 SDPA, exact-coverage full WT2 next-token NLL."""
import argparse
import hashlib
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer

from support import check_config, check_data, save, sha256, verify_files, verify_source, windows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--index", type=int, required=True)
    args = parser.parse_args()
    root = Path(args.project).resolve()
    source = Path(__file__).parent
    execution = verify_source(source)
    config = json.loads((source / "config.json").read_text())
    specification = config["models"][args.index]
    name = specification["id"].split("/")[-1]
    prepared_file = root / "prepared" / f"{name}.json"
    prepared = json.loads(prepared_file.read_text())
    assert prepared["cpu_prepare_ok"] and prepared["model"] == specification
    assert prepared["config_sha256"] == sha256(source / "config.json")
    assert (root / "prepared" / "cpu_tests_passed.json").exists()
    verify_files(prepared)
    data = check_data(config)
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    assert transformers.__version__ == "4.51.3"
    random.seed(config["seed"])
    torch.manual_seed(config["seed"])
    torch.cuda.manual_seed_all(config["seed"])
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    tokenizer = AutoTokenizer.from_pretrained(prepared["local_path"], local_files_only=True, trust_remote_code=False)
    # Read raw bytes as UTF-8; no universal-newline/text reconstruction changes.
    text = Path(data["wiki.test.raw"]["path"]).read_bytes().decode("utf-8")
    ids = tokenizer(text, return_tensors="pt", add_special_tokens=False).input_ids
    length = ids.shape[-1]
    token_hash = hashlib.sha256(ids.numpy().astype("<i8").tobytes()).hexdigest()
    model = AutoModelForCausalLM.from_pretrained(prepared["local_path"], local_files_only=True,
        trust_remote_code=False, torch_dtype=torch.bfloat16, attn_implementation="sdpa").to("cuda").eval()
    check_config(model.config, specification)
    assert all(p.dtype == torch.bfloat16 for p in model.parameters())
    assert model.model.rotary_emb.inv_freq.dtype == torch.float32
    assert model.config._attn_implementation == "sdpa"
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    start = time.monotonic()
    total_nll, count, history = 0.0, 0, []
    with torch.inference_mode():
        for number, (begin, end, first) in enumerate(windows(length, config["window"], config["stride"]), 1):
            batch = ids[:, begin:end].to("cuda")
            output = model(input_ids=batch, use_cache=False)
            # Explicit next-token shift. Previous windows already scored positions < first.
            logits = output.logits[:, first - begin - 1 : end - begin - 1].float()
            labels = batch[:, first - begin :]
            nll = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), labels.reshape(-1), reduction="sum")
            value = nll.item()
            assert math.isfinite(value)
            total_nll += value
            count += labels.numel()
            history.append({"window": number, "begin": begin, "end": end, "first_target": first,
                            "targets": labels.numel(), "nll_sum": value})
            del output, logits, labels, batch, nll
            print(f"{name} window={number} end={end}/{length} scored={count} ppl={math.exp(total_nll/count):.6f}", flush=True)
    torch.cuda.synchronize()
    elapsed = time.monotonic() - start
    assert count == length - 1
    result = {
        "protocol": "full-WT2-sliding-window-next-token", "model": specification,
        "precision": "BF16 parameters/activations; native FP32 norms/RoPE; FP32 cross-entropy",
        "unmodified_model": True, "attention": "sdpa", "ffn": "native SwiGLU",
        "seed": config["seed"], "use_cache": False, "add_special_tokens": False,
        "window": config["window"], "stride": config["stride"], "corpus_tokens": length,
        "scored_tokens": count, "token_ids_int64_le_sha256": token_hash,
        "nll_sum": total_nll, "mean_nll": total_nll / count, "perplexity": math.exp(total_nll / count),
        "evaluation_seconds": elapsed, "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "peak_reserved_bytes": torch.cuda.max_memory_reserved(), "windows": history,
        "data": data, "config_sha256": sha256(source / "config.json"),
        "prepared_sha256": sha256(prepared_file),
        "source": execution,
        "environment": {"python": platform.python_version(), "torch": torch.__version__,
            "transformers": transformers.__version__, "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(), "device_memory": torch.cuda.get_device_properties(0).total_memory,
            "slurm_job_id": os.environ.get("SLURM_JOB_ID"), "slurm_array_job_id": os.environ.get("SLURM_ARRAY_JOB_ID"),
            "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"), "hostname": platform.node(),
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "pip_freeze": subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True).splitlines()},
        "command": [sys.executable, *sys.argv],
    }
    output_path = root / "results" / f"{name}.json"
    save(output_path, result)
    save(output_path.with_suffix(".sha256.json"), {"name": output_path.name, "sha256": sha256(output_path)})
    print(f"COMPLETE {name} PPL={result['perplexity']:.8f} targets={count} seconds={elapsed:.1f}", flush=True)


if __name__ == "__main__":
    main()
