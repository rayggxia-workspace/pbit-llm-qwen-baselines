"""Offline GPU smoke v2: consistent BF16 construction and exact state roundtrip."""

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import pwd
import sys
import tempfile
import time
import traceback


QWEN_SOURCE_SHA256 = "c0f712cc217640b9dd3d168ed000a5dc92079fc850385e5604a150c134d70fec"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assert_rope_fp32(model, torch):
    """Nonpersistent RoPE frequencies must retain their computed FP32 values."""
    frequencies = {name: buffer for name, buffer in model.named_buffers()
                   if name.endswith("inv_freq")}
    if not frequencies:
        raise RuntimeError("tiny Qwen has no registered RoPE inverse-frequency buffer")
    for name, buffer in frequencies.items():
        if buffer.dtype != torch.float32:
            raise RuntimeError(f"RoPE buffer {name} must be FP32, got {buffer.dtype}")
    return {name: {"dtype": str(buffer.dtype), "shape": list(buffer.shape),
                   "device": str(buffer.device)}
            for name, buffer in frequencies.items()}


def assert_same_model_state(original, reloaded, torch):
    """Check every parameter and registered buffer, including nonpersistent buffers."""
    counts = {}
    for category, left_tensors, right_tensors in (
        ("parameters", dict(original.named_parameters()), dict(reloaded.named_parameters())),
        ("buffers", dict(original.named_buffers()), dict(reloaded.named_buffers())),
    ):
        if left_tensors.keys() != right_tensors.keys():
            missing = sorted(left_tensors.keys() - right_tensors.keys())
            unexpected = sorted(right_tensors.keys() - left_tensors.keys())
            raise RuntimeError(f"roundtrip {category} keys differ: {missing=}, {unexpected=}")
        for name, left in left_tensors.items():
            right = right_tensors[name]
            if (left.shape, left.dtype, left.device) != (right.shape, right.dtype, right.device):
                raise RuntimeError(
                    f"roundtrip {category} metadata differs for {name}: "
                    f"{(left.shape, left.dtype, left.device)} vs "
                    f"{(right.shape, right.dtype, right.device)}")
            # Flatten before reinterpreting bytes so scalar buffers are supported.
            left_bytes = left.detach().contiguous().reshape(-1).view(torch.uint8)
            right_bytes = right.detach().contiguous().reshape(-1).view(torch.uint8)
            if not torch.equal(left_bytes, right_bytes):
                different_bytes = int(torch.count_nonzero(left_bytes != right_bytes).item())
                raise RuntimeError(
                    f"roundtrip {category} is not bitwise identical for {name}: "
                    f"{different_bytes=}")
        counts[category] = len(left_tensors)
    counts["rope_buffers"] = assert_rope_fp32(original, torch)
    if counts["rope_buffers"] != assert_rope_fp32(reloaded, torch):
        raise RuntimeError("roundtrip RoPE buffer metadata differs")
    counts["comparison"] = "bitwise uint8 equality with matching shape, dtype and device"
    return counts


def checked_paths(output_value, source_value):
    identity = pwd.getpwuid(os.getuid())
    if identity.pw_name != "pwmat":
        raise RuntimeError("expected the authorized pwmat account")
    home = Path(identity.pw_dir).resolve(strict=True)
    if home != Path("/home/pwmat") or Path.home().resolve(strict=True) != home:
        raise RuntimeError("canonical account home differs from /home/pwmat")
    task = (home / "projects/llm-env-bootstrap-20261022").resolve(strict=True)
    if not task.is_relative_to(home) or task.stat().st_uid != os.getuid():
        raise RuntimeError("task root is not inside the authorized owned home")
    output = Path(output_value).expanduser().resolve()
    if output.parent != task or output.suffix != ".json":
        raise RuntimeError("output must be a JSON file directly in the verified task root")
    if output.exists() and output.stat().st_uid != os.getuid():
        raise RuntimeError("existing output is not owned by this account")
    source = Path(source_value).expanduser().resolve(strict=True)
    if source != task / "smoke_source" or source.stat().st_uid != os.getuid():
        raise RuntimeError("source root must be the owned task-root smoke_source directory")
    return output, source, task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-root", required=True)
    args = parser.parse_args()
    output, source, task = checked_paths(args.output, args.source_root)
    report = {
        "smoke_version": 2,
        "purpose": "synthetic offline environment smoke; no downloaded model, training or quality benchmark",
        "status": "running", "started_unix": time.time(),
        "python": sys.version, "executable": sys.executable,
        "prefix": sys.prefix, "platform": platform.platform(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_job_nodelist": os.environ.get("SLURM_JOB_NODELIST"),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"), "checks": [],
    }

    def save():
        temporary = output.with_name(output.name + f".tmp-{os.getpid()}")
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
        temporary.replace(output)

    def begin(name):
        report["active_check"] = name
        save()

    def record(name, details):
        report["checks"].append({"name": name, "status": "passed", "details": details})
        report.pop("active_check", None)
        save()

    save()
    try:
        begin("single-GPU allocation gate")
        visible = os.environ.get("CUDA_VISIBLE_DEVICES", "").strip()
        if not os.environ.get("SLURM_JOB_ID") or not os.environ.get("SLURM_JOB_NODELIST"):
            raise RuntimeError("GPU smoke requires an allocated Slurm job and node list")
        if not visible or visible.lower() in {"none", "nodevfiles", "all", "-1"} or "," in visible:
            raise RuntimeError("GPU smoke requires exactly one visible allocated GPU")
        prefix = Path(sys.prefix).resolve(strict=True)
        if sys.prefix == sys.base_prefix or not prefix.is_relative_to(Path("/home/pwmat")):
            raise RuntimeError("an isolated environment under the verified personal home is required")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"
        import torch
        import transformers
        import transformers.models.qwen2.modeling_qwen2 as qwen_module
        from torch.nn import functional as functional
        from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedTokenizerFast, Qwen2Config, Qwen2ForCausalLM

        if torch.__version__ != "2.6.0+cu118" or torch.version.cuda != "11.8":
            raise RuntimeError("this smoke expects the fixed Torch 2.6.0+cu118 environment")
        if transformers.__version__ != "4.45.2":
            raise RuntimeError("Transformers version differs from the pinned Qwen implementation")
        if not Path(torch.__file__).resolve().is_relative_to(prefix):
            raise RuntimeError("Torch imports from outside this isolated environment")
        if torch.cuda.device_count() != 1 or not torch.cuda.is_available():
            raise RuntimeError("allocated process must expose exactly one usable CUDA device")
        if not torch.cuda.is_bf16_supported():
            raise RuntimeError("allocated GPU does not support BF16")
        if digest(qwen_module.__file__) != QWEN_SOURCE_SHA256:
            raise RuntimeError("installed Qwen source differs from the repository's pinned SHA-256")
        torch.set_num_threads(min(int(os.environ.get("SLURM_CPUS_PER_TASK", "2")), 4))
        torch.manual_seed(77)
        torch.backends.cuda.matmul.allow_tf32 = False
        device = torch.device("cuda:0")
        properties = torch.cuda.get_device_properties(0)
        record("single-GPU allocation gate", {
            "torch": torch.__version__, "transformers": transformers.__version__,
            "cuda_build": torch.version.cuda, "gpu_name": properties.name,
            "gpu_total_bytes": properties.total_memory,
            "gpu_capability": list(torch.cuda.get_device_capability(0)),
            "qwen_source_sha256": QWEN_SOURCE_SHA256,
        })

        begin("BF16 causal SDPA")
        with torch.inference_mode():
            query, key, value = [torch.randn((1, 2, 16, 64), device=device, dtype=torch.bfloat16) for _ in range(3)]
            actual = functional.scaled_dot_product_attention(query, key, value, dropout_p=0.0, is_causal=True)
            logits = query.float() @ key.float().transpose(-2, -1) / math.sqrt(64)
            forbidden = torch.ones((16, 16), device=device, dtype=torch.bool).triu(1)
            expected = logits.masked_fill(forbidden, -float("inf")).softmax(-1) @ value.float()
            difference = actual.float() - expected
            relative_rmse = (difference.square().mean() / expected.square().mean()).sqrt().item()
            max_error = difference.abs().max().item()
            if actual.dtype != torch.bfloat16 or not bool(torch.isfinite(actual).all()):
                raise RuntimeError("SDPA output is not finite BF16")
            if relative_rmse > 0.03 or max_error > 0.1:
                raise RuntimeError(f"BF16 SDPA exceeds smoke tolerance: {relative_rmse=}, {max_error=}")
        torch.cuda.synchronize()
        record("BF16 causal SDPA", {"shape": list(actual.shape), "relative_rmse": relative_rmse, "max_abs_error": max_error})

        begin("tiny Qwen forward, generation and local serialization")
        from tokenizers import Tokenizer, models, pre_tokenizers
        vocab = {"<pad>": 0, "<bos>": 1, "<eos>": 2, "<unk>": 3}
        vocab.update({f"t{index}": index for index in range(4, 128)})
        backend = Tokenizer(models.WordLevel(vocab=vocab, unk_token="<unk>"))
        backend.pre_tokenizer = pre_tokenizers.Whitespace()
        tokenizer = PreTrainedTokenizerFast(tokenizer_object=backend, pad_token="<pad>",
                                           bos_token="<bos>", eos_token="<eos>", unk_token="<unk>")
        config = Qwen2Config(vocab_size=128, hidden_size=128, intermediate_size=256,
                             num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=1,
                             max_position_embeddings=128, bos_token_id=1, eos_token_id=2,
                             pad_token_id=0, attention_dropout=0.0)
        config._attn_implementation = "sdpa"
        # Construct BF16 parameters directly while preserving explicitly FP32 RoPE buffers,
        # matching from_pretrained(torch_dtype=BF16). A blanket .to(dtype=BF16) would
        # also round nonpersistent inv_freq buffers that are recomputed on reload.
        model = AutoModelForCausalLM.from_config(
            config, torch_dtype=torch.bfloat16, trust_remote_code=False).to(device).eval()
        assert_rope_fp32(model, torch)
        if any(parameter.dtype != torch.bfloat16 for parameter in model.parameters()):
            raise RuntimeError("tiny Qwen parameters were not initialized as BF16")
        if type(model.model.layers[0].self_attn).__name__ != "Qwen2SdpaAttention":
            raise RuntimeError("tiny model did not select the pinned Qwen SDPA implementation")
        text = " ".join(f"t{index}" for index in range(4, 20))
        batch = tokenizer(text, return_tensors="pt", add_special_tokens=False)
        ids = batch["input_ids"].to(device)
        mask = batch["attention_mask"].to(device)
        if ids.cpu().tolist() != [list(range(4, 20))]:
            raise RuntimeError("local synthetic tokenizer produced unexpected IDs")
        with torch.inference_mode():
            forward = model(input_ids=ids, attention_mask=mask, labels=ids, use_cache=True)
            if not bool(torch.isfinite(forward.logits).all()) or not bool(torch.isfinite(forward.loss)):
                raise RuntimeError("tiny Qwen produced nonfinite logits/loss")
            generated = model.generate(input_ids=ids, attention_mask=mask, max_new_tokens=4,
                                       min_new_tokens=4, do_sample=False, use_cache=True)
            if list(generated.shape) != [1, 20]:
                raise RuntimeError("tiny cached greedy generation did not produce four new tokens")
        with tempfile.TemporaryDirectory(prefix="tiny-qwen-", dir=task) as directory:
            model_path = Path(directory)
            tokenizer.save_pretrained(model_path)
            model.save_pretrained(model_path, safe_serialization=True)
            saved_hash = digest(model_path / "model.safetensors")
            reloaded_tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
            if reloaded_tokenizer(text, add_special_tokens=False).input_ids != list(range(4, 20)):
                raise RuntimeError("saved synthetic tokenizer did not roundtrip")
            reloaded = AutoModelForCausalLM.from_pretrained(
                model_path, local_files_only=True, trust_remote_code=False,
                torch_dtype=torch.bfloat16, attn_implementation="sdpa").to(device).eval()
            state_roundtrip = assert_same_model_state(model, reloaded, torch)
            with torch.inference_mode():
                roundtrip = reloaded(input_ids=ids, attention_mask=mask).logits
                torch.testing.assert_close(roundtrip, forward.logits, rtol=0.001, atol=0.001)
                roundtrip_max_error = (roundtrip - forward.logits).abs().max().item()
            del reloaded
        torch.cuda.synchronize()
        record("tiny Qwen forward, generation and local serialization", {
            "layers": 2, "hidden_size": 128, "intermediate_size": 256,
            "parameters": sum(parameter.numel() for parameter in model.parameters()),
            "input_tokens": 16, "new_tokens": 4, "loss": forward.loss.item(),
            "logits_shape": list(forward.logits.shape),
            "attention_module": type(model.model.layers[0].self_attn).__name__,
            "saved_safetensors_sha256": saved_hash,
            "state_roundtrip": state_roundtrip,
            "roundtrip_logits_max_abs_error": roundtrip_max_error,
            "roundtrip_logits_tolerance": {"rtol": 0.001, "atol": 0.001},
            "tokenizer_scope": "synthetic local WordLevel; not the real Qwen vocabulary",
        })

        begin("current fixed-W8 stratified FFN source integrity")
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        for item in manifest["files"]:
            path = (source / item["path"]).resolve(strict=True)
            if not path.is_relative_to(source) or digest(path) != item["sha256"]:
                raise RuntimeError("FFN source snapshot SHA-256 mismatch: " + item["path"])
        sys.path.insert(0, str(source / "experiments/qwen_multiscale_stratified_20261019"))
        import stratified_core
        record("current fixed-W8 stratified FFN source integrity", {
            "source_commit": manifest["source_commit"], "files": manifest["files"],
            "runtime_module": str(Path(stratified_core.__file__).resolve()),
        })

        for strata in (32, 4):
            name = f"B4/T32/K{strata} single-batch FFN"
            begin(name)
            ffn = stratified_core.StratifiedFFN(model.model.layers[0].mlp, policy="pot4",
                                              mode="sampled", cycles=32, strata=strata, seed=77)
            inputs = torch.randn((1, 8, 128), device=device, dtype=torch.bfloat16)
            with torch.inference_mode():
                result = ffn(inputs)
            if result.shape != inputs.shape or result.dtype != inputs.dtype or not bool(torch.isfinite(result).all()):
                raise RuntimeError("FFN output shape, precision or finiteness failed")
            diagnostics = ffn.diagnostics()
            if diagnostics["scale_bin_count"] != 4 or diagnostics["weight_stochastic"]:
                raise RuntimeError("FFN policy changed from fixed W8 / B4")
            if diagnostics["x_clip_fraction"] != 0 or diagnostics["z_clip_fraction"] != 0:
                raise RuntimeError("synthetic FFN input unexpectedly clipped")
            torch.cuda.synchronize()
            record(name, {"shape": list(result.shape), "dtype": str(result.dtype),
                          "output_rms": result.float().square().mean().sqrt().item(),
                          "diagnostics": diagnostics})
            del ffn
        torch.cuda.synchronize()
        report["peak_allocated_bytes"] = torch.cuda.max_memory_allocated(0)
        report["status"] = "passed"
    except BaseException as error:
        report["status"] = "failed"
        report["error"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
        report["finished_unix"] = time.time()
        save()
        raise
    report["finished_unix"] = time.time()
    save()
    print(json.dumps({"status": report["status"], "report": str(output), "checks": len(report["checks"])}))


if __name__ == "__main__":
    main()
