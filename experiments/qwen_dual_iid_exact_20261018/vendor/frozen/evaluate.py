import argparse
import hashlib
import json
import math
from pathlib import Path
import time
import torch
from torch.nn import functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from core import StochasticMatrixFFN


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["baseline", "fixed_exact", "dual_exact", "or_plane"], required=True)
    p.add_argument("--cycles", type=int, default=4096)
    p.add_argument("--bits", type=int, default=12)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--split", choices=["validation", "test"], default="validation")
    p.add_argument("--max-tokens", type=int, default=8192)
    p.add_argument("--shard-index", type=int, default=0)
    p.add_argument("--num-shards", type=int, default=1)
    p.add_argument("--or-chunk", type=int, default=64)
    p.add_argument("--or-group", type=int, choices=[1,2,4,64], default=64)
    p.add_argument("--allow-tf32", action="store_true")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    if not 0 <= args.shard_index < args.num_shards:
        raise ValueError("invalid shard")
    out = Path(args.output)
    if out.exists():
        raise FileExistsError(out)
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = args.allow_tf32
    if args.allow_tf32:
        torch.set_float32_matmul_precision("high")
    torch.manual_seed(args.seed)
    tokenizer = AutoTokenizer.from_pretrained("models/Qwen2.5-0.5B", local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained("models/Qwen2.5-0.5B", local_files_only=True,
            torch_dtype=torch.bfloat16, attn_implementation="sdpa").cuda().eval()
    model.requires_grad_(False)
    attention = [layer.self_attn for layer in model.model.layers]
    calibration_path = Path("results/calibration.json")
    calibration = json.loads(calibration_path.read_text())
    installed = []
    if args.mode != "baseline":
        for index, layer in enumerate(model.model.layers):
            factory=StochasticMatrixFFN;extra={}
            if args.mode=='or_plane' and args.or_group!=64:
                from grouped_or import GroupedORFFN
                factory=GroupedORFFN;extra={'or_group':args.or_group}
            layer.mlp = factory(layer.mlp, calibration["policies"]["group_max"][str(index)],
                    args.mode, args.bits, args.cycles, args.seed, index, args.or_chunk,**extra)
            installed.append(index)
    assert all(layer.self_attn is attention[i] for i, layer in enumerate(model.model.layers))

    text = Path(f'data/wikitext-2/wiki.{"train" if args.split == "validation" else "test"}.raw')
    ids = tokenizer(text.read_text(), add_special_tokens=False, return_tensors="pt").input_ids
    source_tokens = ids.shape[-1]
    if args.split == "validation":
        ids = ids[:, -65536:]
    if args.max_tokens > 0:
        ids = ids[:, :args.max_tokens]
    length = ids.shape[-1]
    starts = []
    for begin in range(0, length, 1024):
        starts.append(begin)
        if min(begin + 2048, length) == length:
            break
    assigned = [(i, begin) for i, begin in enumerate(starts) if i % args.num_shards == args.shard_index]
    nll_sum = 0.0
    scored = 0
    start_time = time.perf_counter()
    torch.cuda.reset_peak_memory_stats()
    for local_index, (window_index, begin) in enumerate(assigned):
        end = min(begin + 2048, length)
        window = ids[:, begin:end].cuda()
        with torch.inference_mode():
            logits = model(input_ids=window, use_cache=False).logits[:, :-1].float()
        if not torch.isfinite(logits).all():
            raise FloatingPointError("nonfinite logits")
        labels = window[:, 1:]
        threshold = begin + 1 if window_index == 0 else begin + 1024
        mask = torch.arange(begin + 1, end, device="cuda") >= threshold
        loss = F.cross_entropy(logits[:, mask].reshape(-1, logits.shape[-1]),
                               labels[:, mask].reshape(-1), reduction="sum")
        nll_sum += loss.item()
        scored += labels[:, mask].numel()
        if local_index == 0 or (local_index + 1) % 5 == 0 or local_index + 1 == len(assigned):
            print(json.dumps({"event": "progress", "shard": args.shard_index,
                "windows": local_index + 1, "total_windows": len(assigned),
                "running_ppl": math.exp(nll_sum / scored),
                "seconds": time.perf_counter() - start_time}), flush=True)
    diagnostics = {str(i): model.model.layers[i].mlp.diagnostics() for i in installed}
    result = {
        "args": vars(args), "layers": installed, "replacement_count": len(installed),
        "source_tokens": source_tokens, "corpus_tokens": length,
        "assigned_windows": len(assigned), "all_windows": len(starts),
        "nll_sum": nll_sum, "scored_tokens": scored, "nll": nll_sum / scored,
        "perplexity": math.exp(nll_sum / scored), "seconds": time.perf_counter() - start_time,
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "attention_unchanged": True, "attention_implementation": "original SDPA",
        "ffn_scope": "all 24 layers; gate/up and down projections use selected matrix mode",
        "ffn_activation": "fixed-scale g/u encoders plus Bernoulli triple product P=|g|/Sg*sigmoid(gq)*|u|/Su",
        "weight_format": "symmetric INT8 per 64x64 tile",
        "probability_format": f"unsigned {args.bits}-bit magnitude plus separate sign; fixed group_max scales",
        "stages": "T samples for gate/up, then T samples for stochastic SwiGLU product/down",
        "dual_note": "conditional Gaussian compression of independent weight Bernoulli counts; exact conditional mean/variance; shared input counts",
        "or_note": ("exact IID per-group multinomial active-mask counts; shared across outputs/planes; exact sum across groups; no OR correction"
                    if args.or_group!=64 else "exact per-tile marginal OR probability and binomial count; planes/signs/outputs sampled independently; no correction"),
        "source_sha256": {f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in ['core.py','evaluate.py','grouped_or.py']},
        "ids_sha256": hashlib.sha256(ids.numpy().tobytes()).hexdigest(),
        "calibration_sha256": hashlib.sha256(calibration_path.read_bytes()).hexdigest(),
        "diagnostics": diagnostics,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    temp=out.with_suffix('.tmp');temp.write_text(json.dumps(result, indent=2) + "\n");temp.replace(out)
    print(json.dumps({k: result[k] for k in ("perplexity", "nll", "nll_sum", "scored_tokens", "seconds")}), flush=True)


if __name__ == "__main__":
    main()
