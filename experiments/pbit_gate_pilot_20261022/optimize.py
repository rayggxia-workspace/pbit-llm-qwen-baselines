"""Phase two: exact-budget gate optimization on TRAIN/VAL only.

The CLI rejects split 2 before loading feature arrays. Public payload prediction
helpers also support a separately authorized final-evaluation wrapper; this
module never opens a blind dataset itself.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

try:
    from .network import LinearPBit, PBitNetwork, effective_probability
    from .train import (calibrate_scalar, evaluate, fit_normalization, max4_logits,
                        model_probability, probability_from_scores, sha256,
                        validate_dataset, write_json)
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from network import LinearPBit, PBitNetwork, effective_probability
    from train import (calibrate_scalar, evaluate, fit_normalization, max4_logits,
                       model_probability, probability_from_scores, sha256,
                       validate_dataset, write_json)


SCOPE = ("TRAIN/VAL-only local gate optimization with frozen teacher data; no blind access, "
         "full-model PPL, physical device training, or hardware PPA. Hidden-randomness "
         "benefit requires comparison with the deterministic-hidden control.")
DEFAULTS = {
    "layers": [0, 12, 23], "train_seeds": [0, 1, 2],
    "kinds": ["pbit_4_8_1", "linear_pbit", "deterministic_4_8_1"],
    "preprocess_modes": ["query_relative", "global"],
    "max4_temperatures": [0.125, 0.25, 0.5, 1.0, 2.0],
    "warmup_epochs": 150, "direct_epochs": 300, "lr": 0.01,
    "root_steps": 30, "record_every": 25, "target_blocks": 8.0,
    "val_budget_ratio_max": 1.02,
    "fb_min": 1e-7, "budget_tolerance": 2e-5, "query_relative_clip": 12.0,
    "initialization": "axis_jitter", "eval_seeds": [101, 202, 303],
    "eval_draws": 16, "epsilon": 1e-12, "device": "cuda", "reset_adam_for_direct": True,
}


class DeterministicNetwork(PBitNetwork):
    """Same 49 parameters; deterministic tanh hidden units, Bernoulli output."""
    kind = "deterministic_4_8_1"

    def forward(self, x):
        hidden = torch.tanh(x @ self.hidden_weight + self.hidden_bias)
        return torch.sigmoid(hidden @ self.output_weight + self.bias)

    def sample(self, x, *, draws=1, generator=None):
        q = self(x)
        return torch.bernoulli(q.expand((draws,) + q.shape), generator=generator)


def load_trainval_dataset(path):
    """Inspect split first; do not load x/mass if any blind/unknown row exists."""
    with np.load(path, allow_pickle=False) as archive:
        split = archive["split"]
        if not np.isin(split, [0, 1]).all() or set(split.tolist()) != {0, 1}:
            raise ValueError("optimization accepts TRAIN/VAL ONLY, split IDs 0/1")
        data = {key: archive[key] for key in archive.files}
    validate_dataset(data)
    return data


def subset(data, mask):
    return {key: value[mask] for key, value in data.items()
            if value.ndim and value.shape[0] == len(mask)}


def fit_preprocess(data, mode, clip=12.0):
    if mode == "query_relative":
        return {"mode": mode, "score": "max4", "statistics": "per_query_free_blocks",
                "std_floor": 0.01, "clip": clip, "train_feature_standardization": False}
    if mode == "global":
        mean, std = fit_normalization(data["x"], data["valid"], data["forced"], data["split"] == 0)
        return {"mode": mode, "mean": mean.tolist(), "std": std.tolist(),
                "fit_split": "train_free_blocks", "clip": None}
    raise ValueError(f"unknown preprocessing: {mode}")


def apply_preprocess(x, valid, forced, normalization):
    clean = np.where(valid[..., None], x, 0).astype(np.float64)
    if normalization["mode"] == "global":
        values = (clean - normalization["mean"]) / normalization["std"]
    elif normalization["mode"] == "query_relative":
        free = valid & ~forced
        count = free.sum(1, keepdims=True)
        if np.any(count == 0):
            raise ValueError("query-relative normalization needs free blocks")
        score = np.max(clean, axis=-1)
        mean = np.where(free, score, 0).sum(1, keepdims=True) / count
        var = np.where(free, (score - mean) ** 2, 0).sum(1, keepdims=True) / count
        scale = np.maximum(np.sqrt(var), normalization["std_floor"])
        values = (clean - mean[..., None]) / scale[..., None]
    else:
        raise ValueError("unsupported normalization")
    if normalization.get("clip") is not None:
        values = np.clip(values, -normalization["clip"], normalization["clip"])
    return np.where(valid[..., None], values, 0).astype(np.float32)


def make_model(kind, seed=0, initialization="axis_jitter", device="cpu"):
    torch.manual_seed(seed)
    classes = {PBitNetwork.kind: PBitNetwork, LinearPBit.kind: LinearPBit,
               DeterministicNetwork.kind: DeterministicNetwork}
    model = classes[kind]().to(device)
    if kind != LinearPBit.kind and initialization == "axis_jitter":
        with torch.no_grad():
            model.hidden_weight.zero_()
            for axis in range(4):
                model.hidden_weight[axis, 2 * axis:2 * axis + 2] = 2.0
            model.hidden_bias.copy_(torch.tensor([0.0, -2.0] * 4, device=device))
            model.output_weight.fill_(0.5)
            for p in (model.hidden_weight, model.hidden_bias, model.output_weight):
                p.add_(torch.randn_like(p) * 0.03)
    elif initialization not in ("axis_jitter", "random"):
        raise ValueError("initialization must be axis_jitter or random")
    return model


def model_payload(model, normalization, **metadata):
    return {"format": "gate_phase2_v1", "kind": model.kind,
            "parameter_count": sum(p.numel() for p in model.parameters()),
            "parameters": {name: p.detach().cpu().tolist() for name, p in model.named_parameters()},
            "normalization": normalization, "scope": SCOPE, **metadata}


def load_model(payload, device="cpu"):
    model = make_model(payload["kind"], initialization="random", device=device)
    with torch.no_grad():
        for name, parameter in model.named_parameters():
            value = torch.as_tensor(payload["parameters"][name], dtype=parameter.dtype, device=device)
            if value.shape != parameter.shape:
                raise ValueError(f"invalid parameter shape: {name}")
            parameter.copy_(value)
    return model


def predict_payload(payload, data, device="cpu"):
    if payload["kind"] == "max4_standardized_sigmoid":
        score = max4_logits(data["x"], data["valid"], data["forced"]) / payload["temperature"]
        return probability_from_scores(score, data["valid"], data["forced"], payload["bias"])
    model = load_model(payload, device)
    x = torch.as_tensor(apply_preprocess(data["x"], data["valid"], data["forced"], payload["normalization"]), device=device)
    valid = torch.as_tensor(data["valid"], device=device)
    forced = torch.as_tensor(data["forced"], device=device)
    return model_probability(model, x, valid, forced).cpu().numpy()


def sample_payload(payload, data, seed, draws, device="cpu"):
    if payload["kind"] == "max4_standardized_sigmoid":
        return np.random.default_rng(seed).random((draws, len(data["split"]), 32)) < predict_payload(payload, data)
    model = load_model(payload, device)
    x = torch.as_tensor(apply_preprocess(data["x"], data["valid"], data["forced"], payload["normalization"]), device=device)
    valid = torch.as_tensor(data["valid"], device=device)
    forced = torch.as_tensor(data["forced"], device=device)
    generator = torch.Generator(device=device).manual_seed(seed)
    with torch.no_grad():
        bits = model.sample(x, draws=draws, generator=generator)
        bits = torch.where(forced[None], torch.ones_like(bits), bits) * valid[None]
    return bits.cpu().numpy()


def probability_summary(q, data):
    def one(mask):
        return {"groups": int(mask.sum()), "documents": int(len(np.unique(data["document"][mask]))),
                "expected_missed_mass": float((1 - (q[mask] * data["mass"][mask]).sum(1)).mean()),
                "expected_selected_blocks": float(q[mask].sum(1).mean()),
                "expected_selected_tokens": float((q[mask] * data["counts"][mask]).sum(1).mean())}
    result = one(np.ones(len(q), dtype=bool))
    result["by_position"] = {str(p): one(data["position"] == p) for p in np.unique(data["position"])}
    return result


def evaluate_payload(payload, data, split_id, config):
    """Evaluate an explicitly supplied split; no filesystem/dataset access here."""
    selected = subset(data, data["split"] == split_id)
    if not len(selected["split"]):
        raise ValueError("requested split is empty")
    q = predict_payload(payload, selected, config["device"])
    def sample(indices, seed, draws):
        mask = np.zeros(len(q), dtype=bool)
        mask[indices] = True
        return sample_payload(payload, subset(selected, mask), seed, draws, config["device"])
    result = evaluate(q, sample, selected, split_id, config)
    result["by_position"] = {}
    for position in np.unique(selected["position"]):
        part = subset(selected, selected["position"] == position)
        pq = predict_payload(payload, part, config["device"])
        def part_sample(indices, seed, draws):
            mask = np.zeros(len(pq), dtype=bool)
            mask[indices] = True
            return sample_payload(payload, subset(part, mask), seed, draws, config["device"])
        result["by_position"][str(position)] = evaluate(pq, part_sample, part, split_id, config)
    result["sampling_contract"] = "True two-stage hidden/output draws for pbit49; output-only draws for linear/tanh. Context-bucket draws are independent reruns, not a shared prefix."
    return result


def gate_basis(model, free_x, free_mass, groups):
    """Preaggregate the 256 p-bit states; all terms retain parameter gradients."""
    if model.kind == PBitNetwork.kind:
        p = model.hidden_distribution(free_x)
        return {"u": model.states @ model.output_weight,
                "a": p.sum(0) / groups, "m": (p * free_mass[:, None]).sum(0) / groups,
                "individual_p": p, "individual_mass": free_mass}
    if model.kind == DeterministicNetwork.kind:
        u = torch.tanh(free_x @ model.hidden_weight + model.hidden_bias) @ model.output_weight
    else:
        u = free_x @ model.weight
    return {"u": u, "a": torch.ones_like(u) / groups, "m": free_mass / groups,
            "individual_p": None, "individual_mass": free_mass}


def solve_bias(model, basis, forced_mean, target=8.0, steps=30):
    """Root is over 256 terms for pbit49, rather than all blocks each iteration."""
    with torch.no_grad():
        u, a = basis["u"].detach(), basis["a"].detach()
        free_target = target - forced_mean
        if not 0 < free_target < float(a.sum().cpu()):
            raise ValueError("infeasible exact mean budget")
        lo = -64.0 - float(u.max().cpu())
        hi = 64.0 - float(u.min().cpu())
        for _ in range(steps):
            middle = (lo + hi) / 2
            if float((a * torch.sigmoid(u + middle)).sum().cpu()) < free_target:
                lo = middle
            else:
                hi = middle
        model.output_bias().fill_((lo + hi) / 2)


def constrained_objective(model, basis, forced_mean, forced_mass_mean,
                          target=8.0, warmup_targets=None, fb_min=1e-7):
    """Implicit derivative of the actual output-bias root, not detached calibration."""
    s = torch.sigmoid(basis["u"] + model.output_bias())
    derivative = s * (1 - s)
    constraint = (basis["a"] * s).sum() + forced_mean - target
    fb = (basis["a"] * derivative).sum()
    missed = 1 - forced_mass_mean - (basis["m"] * s).sum()
    if warmup_targets is None:
        loss = missed
        lb = -(basis["m"] * derivative).sum()
    else:
        if basis["individual_p"] is None:
            q, qb = s, derivative
        else:
            q = basis["individual_p"] @ s
            qb = basis["individual_p"] @ derivative
        clipped = q.clamp(1e-7, 1 - 1e-7)
        loss = F.binary_cross_entropy(clipped, warmup_targets)
        gradient_q = (clipped - warmup_targets) / (clipped * (1 - clipped))
        gradient_q = torch.where((q > 1e-7) & (q < 1 - 1e-7), gradient_q, 0)
        lb = (gradient_q * qb).mean()
    if not bool(torch.isfinite(fb)) or float(fb.detach().cpu()) < fb_min:
        return None, {"rejected": True, "reason": "root_derivative_below_threshold", "Fb": float(fb.detach().cpu())}
    shadow = loss - (lb / fb).detach() * constraint
    return shadow, {"rejected": False, "loss": float(loss.detach().cpu()),
                    "expected_missed_mass": float(missed.detach().cpu()),
                    "F": float(constraint.detach().cpu()), "Fb": float(fb.detach().cpu()),
                    "Lb": float(lb.detach().cpu()), "bias": float(model.output_bias().detach().cpu())}


def expected_split(model, x, data, split_id):
    mask = data["split"] == split_id
    valid = torch.as_tensor(data["valid"][mask], device=x.device)
    forced = torch.as_tensor(data["forced"][mask], device=x.device)
    q = model_probability(model, x[mask], valid, forced).cpu().numpy()
    return probability_summary(q, subset(data, mask))


def train_candidate(kind, mode, seed, layer, data, warmup_q, baseline_val, config, output):
    started = time.time()
    normalization = fit_preprocess(data, mode, config["query_relative_clip"])
    x = torch.as_tensor(apply_preprocess(data["x"], data["valid"], data["forced"], normalization), device=config["device"])
    train_mask = data["split"] == 0
    free = data["valid"][train_mask] & ~data["forced"][train_mask]
    free_x = x[train_mask][torch.as_tensor(free, device=x.device)]
    free_mass = torch.as_tensor(data["mass"][train_mask][free], device=x.device)
    warmup_targets = torch.as_tensor(warmup_q[train_mask][free], dtype=x.dtype, device=x.device)
    groups = int(train_mask.sum())
    forced_mean = float(data["forced"][train_mask].sum() / groups)
    forced_mass_mean = float((data["mass"][train_mask] * data["forced"][train_mask]).sum(dtype=np.float64) / groups)
    model = make_model(kind, seed, config["initialization"], config["device"])
    optimizer = torch.optim.Adam([p for name, p in model.named_parameters() if name != "bias"], lr=config["lr"])
    identity = f"layer{layer}_{kind}_{mode}_seed{seed}"
    logs, checkpoints = [], []
    best, best_any, best_value, best_any_value = None, None, float("inf"), float("inf")

    def check(stage, epoch):
        nonlocal best, best_any, best_value, best_any_value
        with torch.no_grad():
            basis = gate_basis(model, free_x, free_mass, groups)
            solve_bias(model, basis, forced_mean, config["target_blocks"], config["root_steps"])
        train_metrics = expected_split(model, x, data, 0)
        val_metrics = expected_split(model, x, data, 1)
        budget_pass = val_metrics["expected_selected_blocks"] <= baseline_val["expected_selected_blocks"] * config["val_budget_ratio_max"]
        filename = f"{identity}_{stage}{epoch}_model.json"
        payload = model_payload(model, normalization, layer=layer, seed=seed, preprocess=mode,
                                checkpoint={"stage": stage, "epoch": epoch})
        write_json(output / filename, payload)
        record = {"stage": stage, "epoch": epoch, "model_file": filename, "train": train_metrics,
                  "val": val_metrics, "val_budget_pass": bool(budget_pass)}
        checkpoints.append(record)
        write_json(output / f"{identity}_partial_training.json",
                   {"status": "running", "config": config, "steps": logs, "checkpoints": checkpoints})
        value = val_metrics["expected_missed_mass"]
        if value < best_any_value:
            best_any_value, best_any = value, copy.deepcopy(record)
        if budget_pass and value < best_value:
            best_value, best = value, copy.deepcopy(record)

    for stage, epochs in (("warmup", config["warmup_epochs"]), ("direct", config["direct_epochs"])):
        if stage == "direct" and config["reset_adam_for_direct"]:
            optimizer = torch.optim.Adam([p for name, p in model.named_parameters() if name != "bias"], lr=config["lr"])
        for epoch in range(1, epochs + 1):
            model.zero_grad(set_to_none=True)
            basis = gate_basis(model, free_x, free_mass, groups)
            solve_bias(model, basis, forced_mean, config["target_blocks"], config["root_steps"])
            loss, record = constrained_objective(model, basis, forced_mean, forced_mass_mean,
                config["target_blocks"], warmup_targets if stage == "warmup" else None, config["fb_min"])
            record.update(stage=stage, epoch=epoch)
            if loss is not None and abs(record["F"]) > config["budget_tolerance"]:
                record.update(rejected=True, reason="budget_root_tolerance")
                loss = None
            if loss is not None:
                loss.backward()
                gradients_finite = all(p.grad is None or bool(torch.isfinite(p.grad).all()) for p in model.parameters())
                if gradients_finite:
                    optimizer.step()
                else:
                    record.update(rejected=True, reason="nonfinite_gradient")
            logs.append(record)
            if epoch % config["record_every"] == 0 or epoch == epochs:
                check(stage, epoch)
    if not checkpoints:
        check("initial", 0)
    chosen = best or best_any
    payload = json.loads((output / chosen["model_file"]).read_text(encoding="utf-8"))
    train_q = predict_payload(payload, subset(data, data["split"] == 0), config["device"])
    train_sampled = probability_summary(train_q, subset(data, data["split"] == 0))
    train_sampled["sampling_status"] = "not_run: training split uses exact probability metrics; sampled PV is evaluated on validation only"
    val_sampled = evaluate_payload(payload, data, 1, config)
    log_file = f"{identity}_training.json"
    selection = {"criterion": "minimum val expected missed mass subject to the configured mean-block budget ratio against max4-temp1",
                 "val_budget_ratio_max": config["val_budget_ratio_max"],
                 "budget_eligible": best is not None, "fallback_if_no_budget_eligible_checkpoint": best is None,
                 "pv_is_reported_separately": True, "no_train_or_val_recalibration_at_evaluation": True,
                 "selected_checkpoint": {"stage": chosen["stage"], "epoch": chosen["epoch"]}}
    write_json(output / log_file, {"config": config, "steps": logs, "checkpoints": checkpoints, "selection": selection})
    restored = load_model(payload, config["device"])
    # The selected artifact, rather than the final optimizer state, is evaluated.
    qp = predict_payload(payload, data, config["device"])
    valid_t = torch.as_tensor(data["valid"], device=x.device)
    forced_t = torch.as_tensor(data["forced"], device=x.device)
    qr = model_probability(restored, x, valid_t, forced_t).cpu().numpy()
    if not np.array_equal(qp, qr):
        raise AssertionError("selected payload reload changed q")
    return {"id": identity, "kind": kind, "preprocess": mode, "seed": seed, "layer": layer,
            "parameter_count": payload["parameter_count"], "model_file": chosen["model_file"],
            "model_sha256": sha256(output / chosen["model_file"]),
            "log_file": log_file, "selection": selection, "checkpoints": checkpoints,
            "train": train_sampled, "val": val_sampled, "seconds": time.time() - started,
            "rejected_steps": sum(bool(record["rejected"]) for record in logs), "reload_equal": True}


def run(config_path, dataset_path, output_path):
    started = time.time()
    config = dict(DEFAULTS)
    config.update(json.loads(Path(config_path).read_text(encoding="utf-8")))
    if 1.0 not in config["max4_temperatures"]:
        raise ValueError("max4 temperature=1 baseline must be retained")
    if min(config["root_steps"], config["record_every"], config["eval_draws"]) < 1:
        raise ValueError("root_steps/record_every/eval_draws must be positive")
    if min(config["warmup_epochs"], config["direct_epochs"]) < 0:
        raise ValueError("epoch counts cannot be negative")
    if config["device"].startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    data = load_trainval_dataset(dataset_path)
    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=False)
    if config.get("threads"):
        torch.set_num_threads(int(config["threads"]))
    try:
        code_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        code_commit = config.get("code_commit", os.environ.get("GATE_SOURCE_COMMIT", "unavailable"))
    binding = {"scope": SCOPE, "code_commit": code_commit, "config_sha256": sha256(config_path),
               "dataset_sha256": sha256(dataset_path), "dataset_path": str(Path(dataset_path).resolve()),
               "source_sha256": {name: sha256(Path(__file__).with_name(name)) for name in ("optimize.py", "network.py", "train.py")},
               "resolved_config": config, "torch": torch.__version__, "numpy": np.__version__,
               "split_ids": [0, 1], "blind_dataset_loaded": False}
    write_json(output / "DATA_BINDING.json", binding)
    summary = {"scope": SCOPE, "candidates": [], "baselines": [], "selected_by_layer": {}, "selected_by_family": {},
               "dataset_splits": {str(i): {"groups": int(np.sum(data["split"] == i)),
                                           "documents": int(len(np.unique(data["document"][data["split"] == i])))} for i in (0, 1)},
               "binding": "DATA_BINDING.json", "blind_dataset_loaded": False}
    for layer in config["layers"]:
        part = subset(data, data["layer"] == layer)
        if not all(np.any(part["split"] == s) for s in (0, 1)):
            raise ValueError(f"layer {layer} lacks train or val")
        train = part["split"] == 0
        score = max4_logits(part["x"], part["valid"], part["forced"])
        warmup_q = None
        baseline_one = None
        for temperature in config["max4_temperatures"]:
            if temperature <= 0:
                raise ValueError("temperature must be positive")
            bias = calibrate_scalar(score[train] / temperature, part["valid"][train],
                                    part["forced"][train], config["target_blocks"])
            payload = {"format": "gate_phase2_v1", "kind": "max4_standardized_sigmoid", "temperature": temperature,
                       "bias": bias, "bias_fit_split": "train_only", "layer": layer,
                       "normalization": {"mode": "max4_query_free", "std_floor": 0.01}, "scope": SCOPE}
            name = f"layer{layer}_max4_temp{temperature:g}_model.json"
            write_json(output / name, payload)
            train_q = predict_payload(payload, subset(part, train), config["device"])
            train_stats = probability_summary(train_q, subset(part, train))
            train_stats["sampling_status"] = "not_run: training split uses exact probability metrics; sampled PV is evaluated on validation only"
            record = {"id": f"layer{layer}_max4_temp{temperature:g}", "kind": payload["kind"],
                      "temperature": temperature, "layer": layer, "model_file": name,
                      "model_sha256": sha256(output / name),
                      "train": train_stats,
                      "val": evaluate_payload(payload, part, 1, config)}
            summary["baselines"].append(record)
            if temperature == 1.0:
                baseline_one = record
                warmup_q = predict_payload(payload, part, config["device"])
        for mode in config["preprocess_modes"]:
            for kind in config["kinds"]:
                for seed in config["train_seeds"]:
                    record = train_candidate(kind, mode, seed, layer, part, warmup_q,
                                             baseline_one["val"], config, output)
                    record["val_budget_pass"] = record["val"]["expected_selected_blocks"] <= baseline_one["val"]["expected_selected_blocks"] * config["val_budget_ratio_max"]
                    record["val_mass_improved"] = record["val"]["expected_missed_mass"] < baseline_one["val"]["expected_missed_mass"]
                    record["val_pv_nmse_not_worse"] = record["val"]["sampled_subset_pv_nmse_mean"] <= baseline_one["val"]["sampled_subset_pv_nmse_mean"]
                    record["comparison_reference"] = "max4 temperature=1 only; these flags do not establish superiority over the full temperature sweep"
                    summary["candidates"].append(record)
                    summary["elapsed_seconds"] = time.time() - started
                    write_json(output / "PARTIAL_SCAN_SUMMARY.json", summary)
                    print(json.dumps({"completed_candidate": record["id"], "seconds": record["seconds"],
                                      "val_missed_mass": record["val"]["expected_missed_mass"],
                                      "val_budget": record["val"]["expected_selected_blocks"]}), flush=True)
        entries = [r for r in summary["candidates"] + summary["baselines"] if r["layer"] == layer]
        eligible = [r for r in entries if r["val"]["expected_selected_blocks"] <= baseline_one["val"]["expected_selected_blocks"] * config["val_budget_ratio_max"]]
        selected = min(eligible, key=lambda r: r["val"]["expected_missed_mass"])
        summary["selected_by_layer"][str(layer)] = {"id": selected["id"], "layer": layer,
            "kind": selected["kind"], "preprocess": selected.get("preprocess"), "seed": selected.get("seed"),
            "model_file": selected["model_file"], "model_sha256": selected["model_sha256"],
            "criterion": "val missed mass with upper budget gate; includes max4 temperature sweep",
            "pv_is_a_separate_reported_diagnostic": True,
            "val_pv_nmse_not_worse": selected["val"]["sampled_subset_pv_nmse_mean"] <= baseline_one["val"]["sampled_subset_pv_nmse_mean"]}
        families = {}
        for kind in config["kinds"]:
            for mode in config["preprocess_modes"]:
                family = [r for r in entries if r["kind"] == kind and r.get("preprocess") == mode]
                allowed = [r for r in family if r.get("val_budget_pass", False)]
                best_family = min(allowed or family, key=lambda r: r["val"]["expected_missed_mass"])
                families[f"{kind}/{mode}"] = {"id": best_family["id"], "layer": layer,
                    "model_file": best_family["model_file"], "model_sha256": best_family["model_sha256"],
                    "val_budget_pass": bool(allowed), "seed": best_family["seed"]}
        summary["selected_by_family"][str(layer)] = families
    summary["elapsed_seconds"] = time.time() - started
    write_json(output / "SCAN_SUMMARY.json", summary)
    files = sorted(p for p in output.iterdir() if p.is_file())
    write_json(output / "RESULT_MANIFEST.json", {"files": [{"path": p.name, "bytes": p.stat().st_size,
                                                             "sha256": sha256(p)} for p in files]})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--dataset", required=True, help="NPZ containing only splits 0 and 1")
    parser.add_argument("--output", required=True, help="new output directory")
    args = parser.parse_args()
    run(args.config, args.dataset, args.output)


if __name__ == "__main__":
    main()
