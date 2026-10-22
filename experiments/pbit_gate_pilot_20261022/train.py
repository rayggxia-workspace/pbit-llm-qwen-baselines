"""Issue92 complete-query gate pilot. No LLM weights are trained by this program."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

import numpy as np
import torch
from torch.nn import functional as F

try:
    from .network import (
        LinearPBit, PBitNetwork, budget_penalty, effective_probability,
        export_model, import_model,
    )
except ImportError:
    # Explicit path for direct execution also works with Python's -P option.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from network import (
        LinearPBit, PBitNetwork, budget_penalty, effective_probability,
        export_model, import_model,
    )


SCOPE = (
    "Trainable probability-mapping pilot on frozen teacher query/head groups; "
    "not evidence of hidden-randomness advantage, full-model PPL, physical p-bit training, "
    "physical KV bytes, latency, energy, or area. Selected-subset PV uses accurate teacher scores."
)
DEFAULTS = {
    "layers": [0, 12, 23], "train_seeds": [0, 1, 2], "epochs": 100,
    "lr": 0.003, "group_batch": 32, "budget_lambda": 0.1,
    "target_blocks": 8.0, "label_temperature": 1.0,
    "eval_seeds": [101, 202, 303], "eval_draws": 16,
    "device": "cuda", "epsilon": 1e-12,
}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def validate_dataset(data):
    required = ("x", "mass", "block_v", "teacher_output", "valid", "forced", "counts",
                "layer", "head", "document", "split", "position")
    missing = set(required) - set(data)
    if missing:
        raise ValueError(f"missing dataset fields: {sorted(missing)}")
    groups = data["x"].shape[0]
    expected = {"x": (groups, 32, 4), "mass": (groups, 32), "block_v": (groups, 32, 64),
                "teacher_output": (groups, 64), "valid": (groups, 32),
                "forced": (groups, 32), "counts": (groups, 32)}
    expected.update({name: (groups,) for name in ("layer", "head", "document", "split", "position")})
    for name, shape in expected.items():
        if data[name].shape != shape:
            raise ValueError(f"{name} has {data[name].shape}, expected {shape}")
    valid, forced = data["valid"], data["forced"]
    if valid.dtype != np.bool_ or forced.dtype != np.bool_:
        raise ValueError("valid/forced must have boolean dtype")
    if np.any(forced & ~valid) or np.any(data["counts"] < 0):
        raise ValueError("invalid forced mask or negative token count")
    if np.any(data["counts"][~valid] != 0):
        raise ValueError("invalid blocks must contain zero tokens")
    if np.any(data["mass"] < 0) or not np.isfinite(data["mass"]).all():
        raise ValueError("mass must be finite and nonnegative")
    if np.any(data["mass"][~valid] != 0):
        raise ValueError("invalid blocks must have zero teacher mass")
    if not np.allclose(data["mass"].sum(1), 1, atol=2e-5, rtol=0):
        raise ValueError("teacher mass must sum to one within each complete query/head")
    if not np.isfinite(data["x"][valid]).all():
        raise ValueError("valid block features must be finite")
    if not np.isfinite(data["block_v"]).all() or not np.isfinite(data["teacher_output"]).all():
        raise ValueError("nonfinite teacher V data")
    if not np.allclose(data["block_v"].sum(1), data["teacher_output"], atol=1e-4, rtol=1e-4):
        raise ValueError("sum of block pV differs from teacher output")
    split = data["split"]
    if not np.isin(split, [0, 1, 2]).all():
        raise ValueError("split IDs must be train=0/val=1/holdout=2")
    docsets = [set(data["document"][split == i].tolist()) for i in range(3)]
    if any(docsets[a] & docsets[b] for a, b in ((0, 1), (0, 2), (1, 2))):
        raise ValueError("a document is present in more than one split")
    # The capture contract always keeps the first valid block and last two.
    for group in range(groups):
        indices = np.flatnonzero(valid[group])
        mandatory = np.unique(np.r_[indices[:1], indices[-2:]])
        if not forced[group, mandatory].all():
            raise ValueError("first/last-two valid blocks must be forced")
    return {name: {"groups": int(np.sum(split == i)), "documents": len(docsets[i])}
            for i, name in enumerate(("train", "val", "holdout"))}


def max4_logits(x, valid, forced):
    """Per-query standardization of the existing max-of-four score, temperature 1."""
    score = np.max(x, axis=-1)
    free = valid & ~forced
    count = free.sum(1, keepdims=True)
    if np.any(count == 0):
        raise ValueError("max4 reference requires at least one free block per query")
    mean = np.where(free, score, 0).sum(1, keepdims=True) / count
    var = np.where(free, (score - mean) ** 2, 0).sum(1, keepdims=True) / count
    return np.where(free, (score - mean) / np.maximum(np.sqrt(var), 0.01), 0).astype(np.float32)


def probability_from_scores(scores, valid, forced, bias):
    q = 1 / (1 + np.exp(-np.clip(scores + bias, -80, 80)))
    return np.where(forced, 1.0, q) * valid


def calibrate_scalar(scores, valid, forced, target):
    if not (forced.sum(1).mean() < target < valid.sum(1).mean()):
        raise ValueError("target average budget must lie strictly between forced and valid counts")
    lo, hi = -128.0, 128.0
    for _ in range(70):
        middle = (lo + hi) / 2
        if probability_from_scores(scores, valid, forced, middle).sum(1).mean() < target:
            lo = middle
        else:
            hi = middle
    return (lo + hi) / 2


def fit_normalization(x, valid, forced, train):
    free = valid & ~forced & train[:, None]
    values = x[free].astype(np.float64)
    if not len(values):
        raise ValueError("no free training blocks")
    return values.mean(0), np.maximum(values.std(0), 1e-6)


def model_probability(model, x, valid, forced, chunk=128):
    values = []
    with torch.no_grad():
        for start in range(0, len(x), chunk):
            q = model(x[start:start + chunk])
            values.append(effective_probability(q, valid[start:start + chunk], forced[start:start + chunk]))
    return torch.cat(values)


def calibrate_model(model, x, valid, forced, target):
    """Adjust the actual output-node bias, recomputing the hidden marginal each time."""
    if not (forced.sum(1).float().mean() < target < valid.sum(1).float().mean()):
        raise ValueError("unattainable target budget")
    parameter = model.output_bias()
    before = float(parameter.detach().cpu())
    lo, hi = -128.0, 128.0
    with torch.no_grad():
        for _ in range(50):
            middle = (lo + hi) / 2
            parameter.fill_(middle)
            average = float(model_probability(model, x, valid, forced).sum(1).mean().cpu())
            if average < target:
                lo = middle
            else:
                hi = middle
        parameter.fill_((lo + hi) / 2)
    return {"before": before, "after": float(parameter.detach().cpu()), "split": "train_only",
            "train_mean_blocks": float(model_probability(model, x, valid, forced).sum(1).mean().cpu())}


def loss_parts(q, labels, valid, forced, target, coefficient):
    free = valid & ~forced
    bce = F.binary_cross_entropy(q[free].clamp(1e-7, 1 - 1e-7), labels[free])
    budget = budget_penalty(effective_probability(q, valid, forced), target)
    return bce + coefficient * budget, bce, budget


def train_one(model_class, x, labels, valid, forced, split, config, seed):
    torch.manual_seed(seed)
    if x.device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    model = model_class().to(x.device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["lr"])
    train_indices = torch.where(split == 0)[0]
    val_indices = torch.where(split == 1)[0]
    logs, best_loss, best_epoch, best_state = [], float("inf"), None, None
    for epoch in range(config["epochs"]):
        order = train_indices[torch.randperm(len(train_indices), device=x.device)]
        running, total = np.zeros(3), 0
        for indices in order.split(config["group_batch"]):
            optimizer.zero_grad(set_to_none=True)
            parts = loss_parts(model(x[indices]), labels[indices], valid[indices], forced[indices],
                               config["target_blocks"], config["budget_lambda"])
            parts[0].backward()
            optimizer.step()
            running += np.array([float(part.detach().cpu()) for part in parts]) * len(indices)
            total += len(indices)
        with torch.no_grad():
            # One complete validation set gives the explicitly defined mean-budget loss.
            parts = loss_parts(model(x[val_indices]), labels[val_indices], valid[val_indices], forced[val_indices],
                               config["target_blocks"], config["budget_lambda"])
            val_numbers = [float(part.cpu()) for part in parts]
        logs.append({"epoch": epoch + 1, "train_loss": float(running[0] / total),
                     "train_bce": float(running[1] / total), "train_budget_penalty": float(running[2] / total),
                     "val_loss": val_numbers[0], "val_bce": val_numbers[1], "val_budget_penalty": val_numbers[2]})
        if val_numbers[0] < best_loss:
            best_loss, best_epoch = val_numbers[0], epoch + 1
            best_state = copy.deepcopy(model.state_dict())
    model.load_state_dict(best_state)
    calibration = calibrate_model(model, x[train_indices], valid[train_indices], forced[train_indices], config["target_blocks"])
    return model, logs, {"criterion": "minimum validation BCE + lambda * squared mean-query budget error",
                         "best_epoch": best_epoch, "best_val_loss_before_train_only_calibration": best_loss,
                         "output_bias_calibration": calibration}


def evaluate(q, sample_function, layer_data, split_id, config):
    indices = np.flatnonzero(layer_data["split"] == split_id)
    probability = q[indices].astype(np.float64)
    mass = layer_data["mass"][indices].astype(np.float64)
    counts = layer_data["counts"][indices]
    block_v = layer_data["block_v"][indices].astype(np.float64)
    teacher = layer_data["teacher_output"][indices].astype(np.float64)
    docs = layer_data["document"][indices]
    expected_miss = 1 - np.sum(probability * mass, axis=1)
    expected_blocks = probability.sum(1)
    expected_tokens = (probability * counts).sum(1)
    sampled, per_seed, document_rows = [], [], []
    for seed in config["eval_seeds"]:
        mask = sample_function(indices, seed, config["eval_draws"]).astype(np.float64)
        selected_mass = np.einsum("rgb,gb->rg", mask, mass)
        output = np.einsum("rgb,gbv->rgv", mask, block_v) / np.maximum(selected_mass[..., None], config["epsilon"])
        nmse = ((output - teacher[None]) ** 2).sum(-1) / np.maximum((teacher ** 2).sum(-1)[None], config["epsilon"])
        record = {"miss": 1 - selected_mass, "selected_mass": selected_mass, "blocks": mask.sum(-1),
                  "tokens": np.einsum("rgb,gb->rg", mask, counts), "nmse": nmse}
        sampled.append(record)
        per_seed.append({"seed": seed, "mean_missed_mass": float(record["miss"].mean()),
                         "mean_selected_blocks": float(record["blocks"].mean()),
                         "mean_selected_tokens": float(record["tokens"].mean()), "mean_subset_pv_nmse": float(nmse.mean())})
        for document in np.unique(docs):
            keep = docs == document
            document_rows.append({"document": document.item() if hasattr(document, "item") else document,
                                  "eval_seed": seed, "groups": int(keep.sum()),
                                  "expected_missed_mass": float(expected_miss[keep].mean()),
                                  "expected_selected_blocks": float(expected_blocks[keep].mean()),
                                  "expected_selected_tokens": float(expected_tokens[keep].mean()),
                                  "sampled_missed_mass": float(record["miss"][:, keep].mean()),
                                  "sampled_selected_blocks": float(record["blocks"][:, keep].mean()),
                                  "sampled_selected_tokens": float(record["tokens"][:, keep].mean()),
                                  "sampled_over_512_tokens_fraction": float(np.mean(record["tokens"][:, keep] > 512)),
                                  "sampled_subset_pv_nmse": float(nmse[:, keep].mean())})
    pooled = {key: np.concatenate([r[key].reshape(-1) for r in sampled]) for key in sampled[0]}
    return {"groups": len(indices), "documents": int(len(np.unique(docs))),
            "expected_missed_mass": float(expected_miss.mean()), "expected_selected_blocks": float(expected_blocks.mean()),
            "expected_selected_tokens": float(expected_tokens.mean()),
            "sampled_missed_mass_mean": float(pooled["miss"].mean()),
            "sampled_selected_mass_min": float(pooled["selected_mass"].min()),
            "sampled_mass_at_or_below_epsilon_count": int(np.sum(pooled["selected_mass"] <= config["epsilon"])),
            "subset_pv_clamped_denominator_count": int(np.sum(pooled["selected_mass"] < config["epsilon"])),
            "sampled_selected_blocks_mean": float(pooled["blocks"].mean()),
            "sampled_selected_blocks_p95": float(np.percentile(pooled["blocks"], 95)),
            "sampled_selected_blocks_max": int(pooled["blocks"].max()),
            "sampled_selected_tokens_mean": float(pooled["tokens"].mean()),
            "sampled_selected_tokens_p95": float(np.percentile(pooled["tokens"], 95)),
            "sampled_selected_tokens_max": int(pooled["tokens"].max()),
            "sampled_over_512_tokens_fraction": float(np.mean(pooled["tokens"] > 512)),
            "sampled_subset_pv_nmse_mean": float(pooled["nmse"].mean()),
            "per_eval_seed": per_seed,
            "uncertainty_contract": "Per-document paired values supplied; no query-independence confidence interval asserted.",
            "per_document": document_rows}


def run(config_path, dataset_path, output_path):
    started = time.time()
    config = dict(DEFAULTS)
    config.update(json.loads(Path(config_path).read_text(encoding="utf-8")))
    if config["label_temperature"] != 1.0:
        raise ValueError("Issue92 pilot fixes label temperature to 1")
    if config["epochs"] < 1 or config["eval_draws"] < 1 or config["group_batch"] < 1:
        raise ValueError("epochs/draws/group_batch must be positive")
    if config["device"].startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable; choose device=cpu explicitly for CPU preflight")
    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=False)
    with np.load(dataset_path, allow_pickle=False) as archive:
        data = {key: archive[key] for key in archive.files}
    split_info = validate_dataset(data)
    device = torch.device(config["device"])
    if device.type == "cpu" and config.get("torch_threads"):
        torch.set_num_threads(int(config["torch_threads"]))
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        git_sha = config.get("code_commit", os.environ.get("PBIT_SOURCE_SHA", "unavailable_frozen_snapshot"))
    binding = {"dataset_path": str(Path(dataset_path).resolve()), "dataset_sha256": sha256(dataset_path),
               "config_path": str(Path(config_path).resolve()), "config_sha256": sha256(config_path),
               "resolved_config": config, "git_commit": git_sha,
               "source_sha256": {name: sha256(Path(__file__).with_name(name)) for name in ("network.py", "train.py")},
               "torch": torch.__version__, "numpy": np.__version__, "python": platform.python_version(),
               "device": str(device), "scope": SCOPE}
    write_json(output / "DATA_BINDING.json", binding)
    summary = {"scope": SCOPE, "split_protocol": "document-disjoint 0=train/1=val/2=holdout; no holdout calibration",
               "random_stream_contract": "Seeded software PRNG; hidden and output use distinct draws; independent Bernoulli blocks conditional on input. Shared seed across model kinds is not a shared hidden-draw pairing.",
               "budget_contract": "Variable block count; only train-average budget is calibrated; no top-k repair or validation/holdout recalibration.",
               "dataset_splits": split_info, "models": [], "layers": {}, "data_binding": "DATA_BINDING.json"}
    for layer in config["layers"]:
        keep = data["layer"] == layer
        layer_data = {key: value[keep] for key, value in data.items() if value.shape and value.shape[0] == len(keep)}
        split = layer_data["split"]
        if any(not np.any(split == part) for part in range(3)):
            raise ValueError(f"layer {layer} requires nonempty train/val/holdout groups")
        train = split == 0
        valid_np, forced_np = layer_data["valid"], layer_data["forced"]
        mean, std = fit_normalization(layer_data["x"], valid_np, forced_np, train)
        clean_x = np.where(valid_np[..., None], layer_data["x"], 0)
        normalized = np.where(valid_np[..., None], (clean_x - mean) / std, 0).astype(np.float32)
        x = torch.as_tensor(normalized, device=device)
        valid = torch.as_tensor(valid_np, device=device)
        forced = torch.as_tensor(forced_np, device=device)
        split_tensor = torch.as_tensor(split, device=device)
        label_score = np.log(layer_data["mass"].astype(np.float64) + config["epsilon"])
        label_bias = calibrate_scalar(label_score[train], valid_np[train], forced_np[train], config["target_blocks"])
        label_np = probability_from_scores(label_score, valid_np, forced_np, label_bias)
        labels = torch.as_tensor(label_np, dtype=torch.float32, device=device)
        summary["layers"][str(layer)] = {"split_groups": {name: int(np.sum(split == i)) for i, name in enumerate(("train", "val", "holdout"))},
                                          "normalization": {"mean": mean.tolist(), "std": std.tolist()},
                                          "label_tau": -label_bias, "label_temperature": 1.0,
                                          "label_train_mean_effective_blocks": float(label_np[train].sum(1).mean())}
        # Fixed max4 baseline: only one train-fitted bias; no learned feature weights.
        score = max4_logits(clean_x, valid_np, forced_np)
        bias = calibrate_scalar(score[train], valid_np[train], forced_np[train], config["target_blocks"])
        q = probability_from_scores(score, valid_np, forced_np, bias)
        def baseline_sample(indices, seed, draws):
            random = np.random.default_rng(seed).random((draws, len(indices), 32))
            return random < q[indices]
        baseline = {"kind": "max4_standardized_sigmoid", "layer": layer, "train_seed": None,
                    "bias": bias, "temperature": 1.0, "bias_fit_split": "train_only", "splits": {}}
        for i, name in enumerate(("train", "val", "holdout")):
            baseline["splits"][name] = evaluate(q, baseline_sample, layer_data, i, config)
        summary["models"].append(baseline)
        for model_class in (LinearPBit, PBitNetwork):
            for seed in config["train_seeds"]:
                model, logs, selection = train_one(model_class, x, labels, valid, forced, split_tensor, config, seed)
                artifact = export_model(model, mean.tolist(), std.tolist())
                artifact.update({"layer": layer, "train_seed": seed, "scope": SCOPE})
                stem = f"layer{layer}_{model.kind}_seed{seed}"
                write_json(output / f"{stem}_model.json", artifact)
                write_json(output / f"{stem}_training.json", {"selection": selection, "epochs": logs})
                restored = import_model(artifact, device=device)
                q_torch = model_probability(model, x, valid, forced)
                restored_q = model_probability(restored, x, valid, forced)
                if not torch.equal(q_torch, restored_q):
                    raise AssertionError("export/reload exact marginal changed")
                q_np = q_torch.cpu().numpy()
                def sampled(indices, eval_seed, draws):
                    generator = torch.Generator(device=device).manual_seed(eval_seed)
                    with torch.no_grad():
                        bits = restored.sample(x[indices], draws=draws, generator=generator)
                        bits = torch.where(forced[indices][None], torch.ones_like(bits), bits)
                        bits = bits * valid[indices][None]
                    return bits.cpu().numpy()
                record = {"kind": model.kind, "layer": layer, "train_seed": seed,
                          "parameter_count": artifact["parameter_count"], "model_file": f"{stem}_model.json",
                          "training_file": f"{stem}_training.json", "checkpoint_selection": selection,
                          "export_reload_equal": True, "splits": {}}
                for i, name in enumerate(("train", "val", "holdout")):
                    record["splits"][name] = evaluate(q_np, sampled, layer_data, i, config)
                summary["models"].append(record)
                # Save partial progress after every completed model, without calling it final.
                write_json(output / "PARTIAL_SUMMARY.json", summary)
    summary["elapsed_seconds"] = time.time() - started
    write_json(output / "SUMMARY.json", summary)
    files = sorted(path for path in output.iterdir() if path.is_file())
    write_json(output / "RESULT_MANIFEST.json", {"files": [{"path": path.name, "bytes": path.stat().st_size,
                                                             "sha256": sha256(path)} for path in files]})
    print(json.dumps({"status": "completed", "models": len(summary["models"]), "output": str(output), "scope": SCOPE}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.config, args.dataset, args.output)


if __name__ == "__main__":
    main()
