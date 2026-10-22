"""Strong max4 controls: colder sigmoid and a TRAIN-only scalar threshold.

No neural-network training or blind loading. A threshold is shared by a layer,
not a per-query top-k; ties use a TRAIN-fitted probability and counts may vary.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np
import torch

try:
    from .optimize import (DEFAULTS, SCOPE, evaluate_payload, load_trainval_dataset,
                           predict_payload, probability_summary, subset)
    from .train import calibrate_scalar, max4_logits, sha256, write_json
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from optimize import (DEFAULTS, SCOPE, evaluate_payload, load_trainval_dataset,
                          predict_payload, probability_summary, subset)
    from train import calibrate_scalar, max4_logits, sha256, write_json


TEMPERATURES = [0.015625, 0.03125, 0.0625, 1.0]


def fit_threshold(data, target_blocks=8.0):
    """Fit only split 0, including an exact fractional allocation of cutoff ties."""
    train = subset(data, data["split"] == 0)
    groups = len(train["split"])
    if not groups:
        raise ValueError("threshold calibration requires training groups")
    score = max4_logits(train["x"], train["valid"], train["forced"])
    free = train["valid"] & ~train["forced"]
    values = score[free]
    desired = target_blocks * groups - int(train["forced"].sum())
    if not 0 <= desired <= len(values):
        raise ValueError("infeasible threshold budget")
    if desired == 0:
        threshold, probability = float(values.max()) + 1.0, 0.0
    elif desired == len(values):
        threshold, probability = float(values.min()) - 1.0, 0.0
    else:
        # Global ordering is calibration only. Deployment uses one scalar compare.
        unique, counts = np.unique(values, return_counts=True)
        unique, counts = unique[::-1], counts[::-1]
        cumulative = np.cumsum(counts)
        cut = int(np.searchsorted(cumulative, desired, side="left"))
        above = 0 if cut == 0 else int(cumulative[cut - 1])
        threshold = float(unique[cut])
        probability = float((desired - above) / counts[cut])
    return {"format": "gate_phase2_v1", "kind": "max4_train_threshold",
            "threshold": threshold, "tie_probability": probability,
            "threshold_fit_split": "train_only", "target_blocks": target_blocks,
            "normalization": {"mode": "max4_query_free", "std_floor": 0.01},
            "deployment": "independent scalar comparison per block, randomized only at cutoff ties; no per-query top-k",
            "scope": SCOPE}


def run(config_path, dataset_path, output_path):
    started = time.time()
    config = dict(DEFAULTS)
    config.update(json.loads(Path(config_path).read_text(encoding="utf-8")))
    config.update(kinds=[], max4_temperatures=TEMPERATURES)
    data = load_trainval_dataset(dataset_path)
    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=False)
    runtime_config = output / "runtime_config.json"
    write_json(runtime_config, config)
    try:
        source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent,
                                         text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        source = config.get("code_commit", os.environ.get("GATE_SOURCE_COMMIT", "unavailable"))
    binding = {"scope": SCOPE, "code_commit": source, "config_sha256": sha256(config_path),
               "runtime_config_sha256": sha256(runtime_config), "resolved_config": config,
               "dataset_path": str(Path(dataset_path).resolve()), "dataset_sha256": sha256(dataset_path),
               "source_sha256": {name: sha256(Path(__file__).with_name(name)) for name in
                                 ("baseline_extension.py", "optimize.py", "network.py", "train.py")},
               "split_ids": [0, 1], "blind_dataset_loaded": False,
               "torch": torch.__version__, "numpy": np.__version__}
    write_json(output / "DATA_BINDING.json", binding)
    summary = {"scope": SCOPE, "candidates": [], "baselines": [], "selected_by_layer": {},
               "selected_by_family": {}, "binding": "DATA_BINDING.json", "blind_dataset_loaded": False,
               "dataset_splits": {str(i): {"groups": int(np.sum(data["split"] == i)),
                   "documents": int(len(np.unique(data["document"][data["split"] == i])))} for i in (0, 1)},
               "control_protocol": "Four max4 sigmoid temperatures plus one global TRAIN-only threshold per layer; no neural optimization or per-query count repair"}
    for layer in config["layers"]:
        part = subset(data, data["layer"] == layer)
        if not all(np.any(part["split"] == split) for split in (0, 1)):
            raise ValueError(f"layer {layer} lacks train or val")
        train = part["split"] == 0
        score = max4_logits(part["x"], part["valid"], part["forced"])
        controls = []
        for temperature in TEMPERATURES:
            bias = calibrate_scalar(score[train] / temperature, part["valid"][train],
                                    part["forced"][train], config["target_blocks"])
            # Exact legacy payload/order, including float 1.0, preserves temp1 bytes.
            payload = {"format": "gate_phase2_v1", "kind": "max4_standardized_sigmoid", "temperature": temperature,
                       "bias": bias, "bias_fit_split": "train_only", "layer": layer,
                       "normalization": {"mode": "max4_query_free", "std_floor": 0.01}, "scope": SCOPE}
            controls.append((f"layer{layer}_max4_temp{temperature:g}", payload))
        hard = fit_threshold(part, config["target_blocks"])
        hard["layer"] = layer
        controls.append((f"layer{layer}_max4_train_threshold", hard))
        records = []
        for identity, payload in controls:
            model_file = identity + "_model.json"
            write_json(output / model_file, payload)
            train_data = subset(part, train)
            train_stats = probability_summary(predict_payload(payload, train_data, config["device"]), train_data)
            train_stats["sampling_status"] = "not_run: train uses exact metrics; sampled PV is evaluated on val only"
            if abs(train_stats["expected_selected_blocks"] - config["target_blocks"]) > config["budget_tolerance"]:
                raise RuntimeError("TRAIN budget calibration failed")
            val_stats = evaluate_payload(payload, part, 1, config)
            if payload["kind"] == "max4_train_threshold":
                val_stats["sampling_contract"] = "Deterministic scalar comparison except independent Bernoulli tie decisions at the fixed TRAIN cutoff; no validation calibration"
            record = {"id": identity, "kind": payload["kind"], "temperature": payload.get("temperature"),
                      "layer": layer, "model_file": model_file, "model_sha256": sha256(output / model_file),
                      "train": train_stats, "val": val_stats}
            records.append(record)
            summary["baselines"].append(record)
        reference = next(r for r in records if r["temperature"] == 1.0)
        eligible = [r for r in records if r["val"]["expected_selected_blocks"] <=
                    reference["val"]["expected_selected_blocks"] * config["val_budget_ratio_max"]]
        selected = min(eligible, key=lambda r: r["val"]["expected_missed_mass"])
        summary["selected_by_layer"][str(layer)] = {
            "id": selected["id"], "layer": layer, "kind": selected["kind"],
            "preprocess": None, "seed": None, "model_file": selected["model_file"],
            "model_sha256": selected["model_sha256"],
            "criterion": "val missed mass under configured upper mean-budget ratio to max4 temperature=1",
            "pv_is_a_separate_reported_diagnostic": True,
            "val_pv_nmse_not_worse": selected["val"]["sampled_subset_pv_nmse_mean"] <= reference["val"]["sampled_subset_pv_nmse_mean"]}
        summary["elapsed_seconds"] = time.time() - started
        write_json(output / "PARTIAL_SCAN_SUMMARY.json", summary)
    write_json(output / "SCAN_SUMMARY.json", summary)
    files = sorted(p for p in output.iterdir() if p.is_file())
    write_json(output / "RESULT_MANIFEST.json", {"files": [{"path": p.name, "bytes": p.stat().st_size,
                                                             "sha256": sha256(p)} for p in files]})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--dataset", required=True, help="TRAIN/VAL-only NPZ")
    parser.add_argument("--output", required=True, help="new output directory")
    args = parser.parse_args()
    run(args.config, args.dataset, args.output)


if __name__ == "__main__":
    main()
