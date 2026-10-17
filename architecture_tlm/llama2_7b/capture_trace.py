"""Read-only Llama-2 7B BF16 decode QK trace capture (Transformers 4.45.2).

Run GPU work through capture.sbatch.  No attention probabilities are inverted:
the original q_proj output is rotated with the original cache.update RoPE
arguments, then dotted with the actual post-RoPE cached K in FP32.  Original
SDPA forward code and all of its outputs are untouched.  Each context gets an
unchanged baseline forward and a separate instrumented forward, checked before
the trace is marked usable.  This is a routing oracle, NOT a PPL evaluation.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import inspect
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
from pathlib import Path


EXPECTED_SHAPE = dict(model_type="llama", hidden_size=4096, intermediate_size=11008,
                      num_hidden_layers=32, num_attention_heads=32,
                      num_key_value_heads=32, max_position_embeddings=4096,
                      vocab_size=32000, rms_norm_eps=1e-5, rope_theta=10000.0,
                      tie_word_embeddings=False, hidden_act="silu", attention_bias=False)
EXPECTED_FILES = None  # Frozen identity is supplied explicitly, never inherited from Llama-1.
EXPECTED_CORPUS = "173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_json(path, data):
    """Exclusive creation, exact UTF-8/LF bytes, no silent overwrite."""
    with Path(path).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        handle.write("\n")


def verify_inputs(model_path, corpus_path, identity):
    if identity.get("repository") != "meta-llama/Llama-2-7b-hf" or identity.get("revision") != "01c7f73d771dfac7d292323805ebc428287df4f9":
        raise RuntimeError("Unexpected Llama2 official checkpoint identity")
    expected_files = identity["files"]
    if not {"config.json", "tokenizer.json", "tokenizer.model", "tokenizer_config.json", "model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors"}.issubset(expected_files):
        raise RuntimeError("Incomplete model/tokenizer identity manifest")
    for name, expected in expected_files.items():
        path = model_path / name
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Unsafe identity filename")
        actual = sha256(path)
        if actual != expected["sha256"] or path.stat().st_size != expected["bytes"]:
            raise RuntimeError(f"Model identity mismatch: {name}")
    if sha256(corpus_path) != EXPECTED_CORPUS:
        raise RuntimeError("Corpus identity mismatch")
    return expected_files


def git_identity(source):
    try:
        root = subprocess.check_output(["git", "-C", str(source.parent), "rev-parse", "--show-toplevel"],
                                       text=True, stderr=subprocess.DEVNULL).strip()
        commit = subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD"], text=True).strip()
        status = subprocess.check_output(["git", "-C", root, "status", "--porcelain"], text=True)
        return dict(commit=commit, dirty=bool(status), source="git checkout")
    except (FileNotFoundError, subprocess.CalledProcessError):
        # Immutable execution snapshots normally omit .git. The caller records
        # its exact committed source revision, still supplemented by file SHA.
        commit = os.environ.get("SOURCE_COMMIT")
        if not commit or len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit.lower()):
            raise RuntimeError("Snapshot requires SOURCE_COMMIT=<40-character committed SHA>")
        return dict(commit=commit.lower(), dirty=None, source="immutable snapshot declaration")


def select_window(ids, contexts, seed, decode_tokens):
    """Same deterministic public WT2 segment for all context lengths."""
    span = max(contexts) + decode_tokens - 1
    if ids.shape[1] < span:
        raise ValueError("Tokenized corpus is shorter than required context")
    start = random.Random(seed).randrange(ids.shape[1] - span + 1)
    return start, ids[:, start:start + span]


def make_capture_classes(torch, DynamicCache, apply_rotary_pos_emb):
    class Collector:
        def __init__(self, layers, heads):
            self.layers, self.heads = layers, heads
            self.queries, self.rows = {}, []
            self.token = None
            self.seen = set()

        def projection_hook(self, layer, attention):
            def hook(module, inputs, output):
                if output.shape[:2] == (1, 1):
                    self.queries[layer] = output.detach().view(
                        1, 1, attention.num_heads, attention.head_dim).transpose(1, 2)
                else:
                    self.queries.pop(layer, None)
            return hook

        def capture(self, layer, key, kwargs):
            if self.token is None:
                return
            if layer not in self.queries or kwargs is None or "cos" not in kwargs or "sin" not in kwargs:
                raise RuntimeError("Missing verified original Q/RoPE inputs")
            query = self.queries.pop(layer)
            # The returned K is deliberately ignored. It must not be rotated a
            # second time; `key` below came from the ORIGINAL cache.update.
            query, _ = apply_rotary_pos_emb(query, query, kwargs["cos"], kwargs["sin"])
            if query.dtype != torch.bfloat16 or key.dtype != torch.bfloat16:
                raise RuntimeError("Expected original BF16 Q/K")
            if query.shape[1] != key.shape[1] or query.shape[1] != self.heads:
                raise RuntimeError("This capture contract requires MHA")
            logits = (query.float() @ key.float().transpose(-1, -2)) / math.sqrt(query.shape[-1])
            if not bool(torch.isfinite(logits).all()):
                raise RuntimeError("Non-finite captured logits")
            for head, row in enumerate(logits[0, :, 0].cpu().tolist()):
                identity = (self.token, layer, head)
                if identity in self.seen:
                    raise RuntimeError(f"Duplicate trace row: {identity}")
                self.seen.add(identity)
                self.rows.append(dict(token=self.token, layer=layer, head=head, logits=row))

        @contextlib.contextmanager
        def installed(self, model):
            handles = []
            try:
                for layer, block in enumerate(model.model.layers):
                    handles.append(block.self_attn.q_proj.register_forward_hook(
                        self.projection_hook(layer, block.self_attn)))
                yield
            finally:
                for handle in handles:
                    handle.remove()
                self.queries.clear()

    class CaptureCache(DynamicCache):
        def __init__(self, collector):
            super().__init__()
            self.collector = collector

        def update(self, key_states, value_states, layer_idx, cache_kwargs=None):
            key, value = super().update(key_states, value_states, layer_idx, cache_kwargs)
            self.collector.capture(layer_idx, key, cache_kwargs)
            return key, value

    return Collector, CaptureCache


def run_forward(model, ids, context, decode_tokens, cache, torch, collector=None):
    """Prefill=context-1; token0 cache length=context (TLM convention)."""
    prefix = ids[:, :context - 1].to("cuda")
    if collector is not None:
        collector.token = None
    prefill = model.model(input_ids=prefix, past_key_values=cache, use_cache=True, return_dict=True)
    cache = prefill.past_key_values
    del prefill, prefix
    outputs = []
    for token in range(decode_tokens):
        if collector is not None:
            collector.token = token
        step = model.model(input_ids=ids[:, context - 1 + token:context + token].to("cuda"),
                           past_key_values=cache, use_cache=True, return_dict=True)
        cache = step.past_key_values
        outputs.append(model.lm_head(step.last_hidden_state[:, -1]).float().cpu())
        del step
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--identity-manifest", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contexts", nargs="+", type=int, default=[512, 1024, 2048, 4096])
    parser.add_argument("--decode-tokens", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--atol", type=float, default=0.0)
    parser.add_argument("--rtol", type=float, default=0.0)
    args = parser.parse_args(argv)
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("GPU capture must be submitted through Slurm")
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite execution output: {args.output}")
    if args.decode_tokens < 1 or min(args.contexts) < 2 or len(set(args.contexts)) != len(args.contexts):
        raise ValueError("Invalid contexts/decode tokens")
    if max(args.contexts) + args.decode_tokens - 1 > EXPECTED_SHAPE["max_position_embeddings"]:
        raise ValueError("Capture must stay inside native Llama-2 4096-token context")
    if min(args.atol, args.rtol) < 0 or not all(math.isfinite(x) for x in (args.atol, args.rtol)):
        raise ValueError("Invalid verification tolerances")
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    import torch
    import transformers
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
    from transformers.cache_utils import DynamicCache
    from transformers.models.llama.modeling_llama import LlamaSdpaAttention, apply_rotary_pos_emb
    if transformers.__version__ != "4.45.2":
        raise RuntimeError("Only the inspected Transformers 4.45.2 implementation is supported")
    if not torch.cuda.is_available():
        raise RuntimeError("Slurm allocation has no CUDA device")
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    identity = json.loads(args.identity_manifest.read_text(encoding="utf-8"))
    model_files = verify_inputs(args.model, args.data, identity)
    config = AutoConfig.from_pretrained(args.model, local_files_only=True)
    shape = {key: getattr(config, key, None) for key in EXPECTED_SHAPE}
    if shape != EXPECTED_SHAPE or bool(config.tie_word_embeddings) or config.pretraining_tp != 1:
        raise RuntimeError(f"Not the verified original Llama-2 7B: {shape}")
    source = Path(__file__).resolve()
    provenance = dict(
        kind="REAL_LLAMA2_7B_POST_ROPE_QK_LOGITS", model_ppl_validated=False,
        protocol="BF16 unchanged original SDPA baseline and identical instrumented forward; no PPL scoring",
        repository="rayggxia-workspace/pbit-llm-qwen-baselines", code=git_identity(source),
        source_sha256=sha256(source), model_files=model_files, model_shape=shape,
        model_revision=identity["revision"], model_identity=identity,
        identity_manifest_sha256=sha256(args.identity_manifest),
        data=dict(name="WikiText-2 raw test", sha256=EXPECTED_CORPUS, add_special_tokens=False,
                  train_data="not used; no calibration/training in capture"),
        precision="Original BF16 Q/K and SDPA; extra post-RoPE QK dot product accumulated in FP32",
        token_convention="token0 has cache length=context; context-1 prefill then single-token cached decode",
        privacy="No input text, input token IDs, KV vectors or model weights are serialized",
        seed=args.seed, versions=dict(torch=torch.__version__, transformers=transformers.__version__,
                                     python=platform.python_version()),
        gpu=torch.cuda.get_device_name(), slurm_job_id=os.environ["SLURM_JOB_ID"],
        attention_forward_sha256=hashlib.sha256(inspect.getsource(LlamaSdpaAttention.forward).encode()).hexdigest(),
        rotary_source_sha256=hashlib.sha256(inspect.getsource(apply_rotary_pos_emb).encode()).hexdigest(),
        cache_update_source_sha256=hashlib.sha256(inspect.getsource(DynamicCache.update).encode()).hexdigest(),
        command=[sys.executable, *sys.argv], limitations=[
            "Single deterministic public-corpus segment, not a representative workload or full WT2 PPL",
            "Capture runs original BF16 FFN; it is a routing oracle, not SC-FFN quality validation",
            "Extra dense FP32 QK capture work is offline overhead, never simulated as sparse hardware work",
            "PV sample counts, screening calibration, and Ising dynamics are downstream TLM choices"],
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    ids = tokenizer(args.data.read_text(encoding="utf-8"), add_special_tokens=False,
                    return_tensors="pt").input_ids
    start, window = select_window(ids, args.contexts, args.seed, args.decode_tokens)
    provenance["data"].update(source_tokens=ids.shape[1], segment_start_token=start,
                              segment_tokens=window.shape[1],
                              segment_ids_sha256=hashlib.sha256(window.numpy().tobytes()).hexdigest())
    model = AutoModelForCausalLM.from_pretrained(args.model, local_files_only=True,
        torch_dtype=torch.bfloat16, attn_implementation="sdpa", use_safetensors=True,
        low_cpu_mem_usage=True).cuda().eval()
    model.requires_grad_(False)
    if any(type(block.self_attn) is not LlamaSdpaAttention for block in model.model.layers):
        raise RuntimeError("Unexpected attention class")
    provenance["parameter_count"] = sum(parameter.numel() for parameter in model.parameters())
    if provenance["parameter_count"] != 6738415616:
        raise RuntimeError("Unexpected parameter count")
    Collector, CaptureCache = make_capture_classes(torch, DynamicCache, apply_rotary_pos_emb)
    args.output.mkdir(parents=True, exist_ok=False)
    save_json(args.output / "run_started.json", provenance)
    outputs = []
    with torch.inference_mode():
        for context in args.contexts:
            started = time.perf_counter()
            baseline = run_forward(model, window, context, args.decode_tokens, DynamicCache(), torch)
            collector = Collector(shape["num_hidden_layers"], shape["num_attention_heads"])
            with collector.installed(model):
                captured = run_forward(model, window, context, args.decode_tokens, CaptureCache(collector), torch, collector)
            checks = []
            for token, (left, right) in enumerate(zip(baseline, captured)):
                equal = torch.equal(left, right)
                close = torch.allclose(left, right, atol=args.atol, rtol=args.rtol)
                greedy_equal = bool(torch.equal(left.argmax(-1), right.argmax(-1)))
                checks.append(dict(token=token, bitwise_equal=equal, allclose=close,
                                   greedy_equal=greedy_equal, max_abs_difference=float((left-right).abs().max())))
                if not close or not greedy_equal:
                    raise RuntimeError(f"Capture changed original model output: {checks[-1]}")
            expected_rows = args.decode_tokens * shape["num_hidden_layers"] * shape["num_attention_heads"]
            if len(collector.rows) != expected_rows:
                raise RuntimeError(f"Missing rows: {len(collector.rows)} != {expected_rows}")
            if any(len(row["logits"]) != context + row["token"] for row in collector.rows):
                raise RuntimeError("Captured cache length violates TLM convention")
            detail = dict(provenance, context=context, decode_tokens=args.decode_tokens,
                          validation=checks, atol=args.atol, rtol=args.rtol)
            trace = args.output / f"c{context}.trace.json"
            save_json(trace, dict(provenance=detail, rows=collector.rows))
            summary = dict(context=context, decode_tokens=args.decode_tokens, rows=expected_rows,
                           path=str(trace.relative_to(args.output)), bytes=trace.stat().st_size,
                           sha256=sha256(trace), elapsed_seconds=time.perf_counter()-started,
                           validation=checks)
            save_json(args.output / f"c{context}.validation.json", summary)
            outputs.append(summary)
            print(json.dumps(summary, ensure_ascii=False), flush=True)
            del collector, baseline, captured
    save_json(args.output / "manifest.json", dict(status="complete", provenance=provenance, artifacts=outputs))


if __name__ == "__main__":
    main()
