"""Capture actual post-RoPE QK/V rows without changing the BF16 model forward.

Only runs inside an allocated Slurm GPU job. Use the unchanged
``baselines/perplexity.py`` separately for the BF16 sliding-window PPL rerun;
this limited-window trace is not a full-corpus or sampled-attention PPL test.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

try:
    from .verify_inputs import DEFAULT_PERSONAL_ROOT, owned_path, recheck_report, sha256_file, validate_config
except ImportError:
    from verify_inputs import DEFAULT_PERSONAL_ROOT, owned_path, recheck_report, sha256_file, validate_config


TRANSFORMERS_VERSION = "4.45.2"
QWEN_SOURCE_SHA256 = "c0f712cc217640b9dd3d168ed000a5dc92079fc850385e5604a150c134d70fec"
DEFAULT_ROWS = "0:0,0:13,12:0,12:13,23:0,23:13"
TEST_IDS_TOKENS = 299078
TEST_IDS_SHA256 = "8d41d21825bb0e103dc63337727daf4b51c631cacec5937f014b119ae209081e"


def require_gpu_allocation(environment=None):
    environment = os.environ if environment is None else environment
    if not environment.get("SLURM_JOB_ID") or not environment.get("SLURM_JOB_NODELIST"):
        raise RuntimeError("capture requires an allocated Slurm job and node list")
    visible = environment.get("CUDA_VISIBLE_DEVICES", "").strip()
    if not visible or visible in {"-1", "NoDevFiles", "none", "None"}:
        raise RuntimeError("capture requires a nonempty allocated CUDA_VISIBLE_DEVICES")


def parse_rows(value):
    result = []
    for item in value.split(","):
        try:
            layer, head = (int(x) for x in item.split(":"))
        except ValueError as exc:
            raise ValueError("rows must be comma-separated layer:head pairs") from exc
        if not 0 <= layer < 24 or not 0 <= head < 14:
            raise ValueError("row layer/head outside Qwen2.5-0.5B dimensions")
        if (layer, head) in result:
            raise ValueError("duplicate selected trace row")
        result.append((layer, head))
    return result


@contextmanager
def intercept_sdpa(model, torch, selected_rows, tokens):
    """Scoped hook of the verified 4.45.2 Qwen SDPA interface; no forward rewrite."""
    functional = torch.nn.functional
    original = functional.scaled_dot_product_attention
    active = {"layer": None}
    calls = []
    rows = {}
    handles = []

    def before(layer_index):
        def hook(module, inputs):
            if active["layer"] is not None:
                raise RuntimeError("nested attention module during SDPA capture")
            active["layer"] = layer_index
        return hook

    def after(module, inputs, output):
        active["layer"] = None

    def intercepted(query, key, value, *args, **kwargs):
        layer = active["layer"]
        if layer is None:
            raise RuntimeError("SDPA called outside a registered Qwen attention module")
        # Qwen 4.45.2 repeats its 2 KV heads to the 14 query heads before SDPA.
        shape = (1, 14, tokens, 64)
        if tuple(query.shape) != shape or tuple(key.shape) != shape or tuple(value.shape) != shape:
            raise RuntimeError(f"unexpected actual SDPA Q/K/V shapes at layer {layer}")
        if args or kwargs.get("attn_mask") is not None or kwargs.get("dropout_p", 0) != 0:
            raise RuntimeError("capture expects unpadded, zero-dropout, keyword-only causal SDPA")
        if kwargs.get("is_causal") is not True:
            raise RuntimeError("capture requires full causal self-attention")
        if query.dtype != torch.bfloat16 or key.dtype != torch.bfloat16 or value.dtype != torch.bfloat16:
            raise RuntimeError("actual Q/K/V tensors are not BF16")
        if layer in [call["layer"] for call in calls]:
            raise RuntimeError(f"more than one SDPA call for layer {layer}")
        # Prove GQA mapping instead of silently treating duplicated KV as unique heads.
        for group in range(2):
            first = group * 7
            for other in range(first + 1, first + 7):
                if not torch.equal(key[:, first], key[:, other]) or not torch.equal(value[:, first], value[:, other]):
                    raise RuntimeError("actual repeated GQA K/V mapping differs from 7-query groups")
        calls.append({"layer": layer, "query_shape": list(query.shape), "key_shape": list(key.shape),
                      "value_shape": list(value.shape), "kv_layout": "2 heads repeated in groups of 7"})
        for selected_layer, head in selected_rows:
            if selected_layer == layer:
                q_last = query[0, head, -1].float()
                k_head = key[0, head].float()
                logits = torch.mv(k_head, q_last) / math.sqrt(64)
                rows[(layer, head)] = {
                    "logits": logits.cpu().numpy(),
                    "values": value[0, head].float().cpu().numpy(),
                }
        # The exact original tensors and SDPA arguments still determine model output.
        return original(query, key, value, *args, **kwargs)

    try:
        for layer_index, layer in enumerate(model.model.layers):
            attention = layer.self_attn
            if type(attention).__name__ != "Qwen2SdpaAttention":
                raise RuntimeError("actual attention module is not the pinned Qwen2SdpaAttention")
            handles.append(attention.register_forward_pre_hook(before(layer_index)))
            handles.append(attention.register_forward_hook(after))
        functional.scaled_dot_product_attention = intercepted
        yield rows, calls
    finally:
        functional.scaled_dot_product_attention = original
        for handle in handles:
            handle.remove()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--verification", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--personal-root", default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--start-token", type=int, default=0)
    parser.add_argument("--tokens", type=int, default=2048)
    parser.add_argument("--rows", default=DEFAULT_ROWS)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    require_gpu_allocation()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_commit):
        raise ValueError("source-commit must be the exact 40-character source Git SHA")
    if args.start_token < 0 or not 2 <= args.tokens <= 2048:
        raise ValueError("start-token must be nonnegative and tokens must be in [2,2048]")
    selected = parse_rows(args.rows)
    output = owned_path(args.output_dir, args.personal_root, exists=False)
    if output.exists():
        raise FileExistsError("capture output directory must be new; no result overwrites")
    verification = recheck_report(args.verification, args.model, args.text, args.personal_root)

    # Import heavyweight packages only after scope/allocation/input checks pass.
    import numpy as np
    import torch
    import transformers
    import transformers.models.qwen2.modeling_qwen2 as qwen_module

    if transformers.__version__ != TRANSFORMERS_VERSION:
        raise RuntimeError(f"expected Transformers {TRANSFORMERS_VERSION}, got {transformers.__version__}")
    installed_qwen_sha = sha256_file(qwen_module.__file__)
    if installed_qwen_sha != QWEN_SOURCE_SHA256:
        raise RuntimeError("installed Qwen module bytes differ from pinned upstream implementation")
    if not torch.cuda.is_available():
        raise RuntimeError("allocated job has no usable CUDA device")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("allocated GPU does not support BF16")
    repository = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repository / "baselines"))
    from common import device_metadata, load_local_model, set_deterministic

    set_deterministic(args.seed)
    tokenizer, model = load_local_model(verification["model"], "cuda")
    validate_config(model.config.to_dict())
    if len(model.model.layers) != 24 or model.training:
        raise RuntimeError("expected 24-layer evaluation model")
    if any(parameter.dtype != torch.bfloat16 for parameter in model.parameters()):
        raise RuntimeError("model contains non-BF16 parameters")
    text = Path(verification["text"]).read_text(encoding="utf-8")
    all_ids = tokenizer(text, return_tensors="pt", add_special_tokens=False).input_ids
    all_ids_sha = hashlib.sha256(all_ids.numpy().astype("<i8", copy=False).tobytes()).hexdigest()
    if all_ids.shape[-1] != TEST_IDS_TOKENS or all_ids_sha != TEST_IDS_SHA256:
        raise ValueError("full-corpus token IDs differ from the recorded original Qwen WT2 identity")
    end = args.start_token + args.tokens
    if all_ids.shape[-1] < end:
        raise ValueError("verified corpus has fewer tokens than the declared window")
    token_ids = all_ids[:, args.start_token:end].contiguous()
    token_id_sha = hashlib.sha256(token_ids.numpy().astype("<i8", copy=False).tobytes()).hexdigest()
    window = token_ids.to("cuda")
    with torch.inference_mode():
        baseline = model(input_ids=window, use_cache=False).logits.cpu()
        with intercept_sdpa(model, torch, selected, args.tokens) as (rows, calls):
            observed = model(input_ids=window, use_cache=False).logits.cpu()
    if [call["layer"] for call in calls] != list(range(24)) or set(rows) != set(selected):
        raise RuntimeError("did not capture exactly 24 ordered layers and all selected rows")
    if not torch.equal(baseline, observed):
        raise RuntimeError("could not verify bitwise equality of baseline/captured logits; reject this trace")
    model_logits_sha = hashlib.sha256(memoryview(baseline.contiguous().view(torch.int16).numpy())).hexdigest()
    del baseline, observed
    metadata = [{"row_id": f"l{layer:02d}_h{head:02d}", "layer": layer, "head": head,
                 "kv_head": head // 7, "start_token": args.start_token,
                 "query_token": end - 1, "candidate_start": args.start_token,
                 "candidate_end_exclusive": end, "candidate_order": "ascending original prefix",
                 "head_dim": 64} for layer, head in selected]
    output.mkdir(parents=True, exist_ok=False)
    trace_path = output / "attention_rows.npz"
    np.savez_compressed(trace_path, logits=np.stack([rows[row]["logits"] for row in selected]),
                        values=np.stack([rows[row]["values"] for row in selected]),
                        row_metadata=np.array([json.dumps(row, sort_keys=True) for row in metadata]))
    with np.load(trace_path, allow_pickle=False) as stored:
        if stored["logits"].shape != (len(selected), args.tokens):
            raise RuntimeError("saved trace logits failed shape readback")
        if stored["values"].shape != (len(selected), args.tokens, 64):
            raise RuntimeError("saved trace V failed shape readback")
        if not np.isfinite(stored["logits"]).all() or not np.isfinite(stored["values"]).all():
            raise RuntimeError("trace contains non-finite QK or V")
    provenance = {
        "schema": "attention-e01-capture-v1", "passed": True,
        "source_commit": args.source_commit, "source_files": {
            str(path.relative_to(repository)): sha256_file(path) for path in (
                Path(__file__).resolve(), Path(__file__).with_name("verify_inputs.py"),
                repository / "baselines" / "common.py", repository / "baselines" / "perplexity.py")},
        "verification": verification, "verification_sha256": sha256_file(args.verification),
        "transformers_version": transformers.__version__, "installed_qwen_source_sha256": installed_qwen_sha,
        "numpy_version": np.__version__, "environment": device_metadata("cuda"),
        "slurm": {key: os.environ.get(key) for key in (
            "SLURM_JOB_ID", "SLURM_JOB_NODELIST", "SLURM_JOB_GPUS", "CUDA_VISIBLE_DEVICES")},
        "seed": args.seed, "dtype": "BF16 unchanged model; captured last-query QK FP32 and V BF16->FP32",
        "window": {"start_token": args.start_token, "tokens": args.tokens, "add_special_tokens": False,
                   "use_cache": False, "token_id_sha256_le_int64": token_id_sha,
                   "query_source": "last query of unchanged BF16 prefill; not a timed KV-cache decode"},
        "full_corpus_token_identity": {"tokens": int(all_ids.shape[-1]), "sha256_le_int64": all_ids_sha},
        "full_model_logits_bitwise_equal": True, "full_model_logits_sha256_bf16": model_logits_sha,
        "sdpa_calls": calls, "rows": metadata, "trace": {
            "path": str(trace_path), "bytes": trace_path.stat().st_size, "sha256": sha256_file(trace_path),
            "keys": {"logits": [len(selected), args.tokens], "values": [len(selected), args.tokens, 64],
                     "row_metadata": "Unicode JSON per selected row"}},
        "scope": "single-window unchanged BF16 trace; not full WT2 PPL, sampled-attention PPL, or chip PPA",
    }
    with (output / "capture.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(provenance, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"passed": True, "rows": len(rows), "tokens": args.tokens, "output": str(output)}))


if __name__ == "__main__":
    main()
