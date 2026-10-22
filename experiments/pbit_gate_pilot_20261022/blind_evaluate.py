"""Freeze the entire TRAIN/VAL search, then evaluate its untouched blind split.

``freeze`` reads JSON only and never opens an NPZ. ``evaluate`` requires the
verified Weican_Chen home and an explicit Slurm CUDA allocation. It has no fit,
calibration or selection operation: every frozen configuration is reported.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib
import itertools
import json
import os
from pathlib import Path
import platform
import re
import sys
import time


FORMAT = "gate_phase2_blind_freeze_v1"
SCOPE = "Frozen local QK gate blind evaluation; no refit, calibration, new selection, full-model PPL or hardware PPA."


def now():
    return datetime.now(timezone.utc).isoformat()


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def read_json(path):
    raw = Path(path).read_bytes()
    return json.loads(raw.decode("utf-8")), raw


def write_json(path, value, *, replace=False):
    with Path(path).open("w" if replace else "x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def inside(path, root, *, strict=False):
    resolved = Path(path).resolve(strict=strict)
    if not resolved.is_relative_to(root):
        raise ValueError("path escapes approved root: " + str(resolved))
    return resolved


def require_sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("invalid SHA-256 binding")
    return value


def _expected_ids(config):
    layers = config["layers"]
    if (set(layers) != {0, 12, 23} or set(config["train_seeds"]) != {0, 1, 2}
            or set(config["kinds"]) != {"pbit_4_8_1", "linear_pbit", "deterministic_4_8_1"}
            or set(config["preprocess_modes"]) != {"query_relative", "global"}
            or set(config["max4_temperatures"]) != {0.125, 0.25, 0.5, 1.0, 2.0}):
        raise ValueError("freeze requires the complete registered 54-candidate/15-control grid")
    candidates = {f"layer{layer}_{kind}_{mode}_seed{seed}" for layer, kind, mode, seed in itertools.product(
        layers, config["kinds"], config["preprocess_modes"], config["train_seeds"])}
    controls = {f"layer{layer}_max4_temp{temperature:g}" for layer, temperature in itertools.product(
        layers, config["max4_temperatures"])}
    return candidates, controls


def _prepare_primary(search_root, output):
    """Freeze all 69 JSON payloads without reading trainval or blind NPZ bytes."""
    root = Path(search_root).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    paths = {"summary": root / "search/SCAN_SUMMARY.json", "binding": root / "search/DATA_BINDING.json",
             "capture": root / "capture/capture.json", "runtime": root / "runtime_config.json"}
    objects, raw_inputs = {}, {}
    for label, path in paths.items():
        inside(path, root, strict=True)
        objects[label], raw_inputs[label] = read_json(path)
    summary, binding, capture, runtime = (objects[key] for key in ("summary", "binding", "capture", "runtime"))
    config = binding["resolved_config"]
    if binding.get("blind_dataset_loaded") is not False or summary.get("blind_dataset_loaded") is not False:
        raise ValueError("search did not attest TRAIN/VAL-only execution")
    if binding.get("split_ids") != [0, 1] or capture.get("status") != "completed":
        raise ValueError("incomplete capture or unknown search splits")
    if digest_bytes(raw_inputs["runtime"]) != binding["config_sha256"]:
        raise ValueError("runtime config hash differs from search binding")
    if capture["config_sha256"] != binding["config_sha256"]:
        raise ValueError("capture and search configurations differ")
    if any(config.get(key) != value for key, value in runtime.items()):
        raise ValueError("resolved search parameters differ from runtime config")
    datasets = capture["datasets"]
    trainval = datasets["training_dataset"]
    blind = datasets["blind_holdout"]
    if trainval["split_values"] != [0, 1] or blind["split_values"] != [2]:
        raise ValueError("capture did not physically isolate the blind split")
    if binding["dataset_sha256"] != require_sha(trainval["sha256"]):
        raise ValueError("search trainval SHA differs from capture")
    require_sha(blind["sha256"])
    # Resolve paths only: in particular, do not stat/hash/load the blind NPZ.
    trainval_path = inside(root / "capture/training_dataset.npz", root)
    blind_path = inside(root / "capture/blind_holdout.npz", root)
    if Path(binding["dataset_path"]).resolve() != trainval_path:
        raise ValueError("search dataset path differs from the trainval capture")
    if Path(blind["path"]).resolve() != blind_path or Path(trainval["path"]).resolve() != trainval_path:
        raise ValueError("capture dataset path binding differs")
    expected_candidates, expected_controls = _expected_ids(config)
    candidates, controls = summary["candidates"], summary["baselines"]
    if (len(candidates) != 54 or {row["id"] for row in candidates} != expected_candidates
            or len(controls) != 15 or {row["id"] for row in controls} != expected_controls):
        raise ValueError("incomplete or duplicated search grid; freeze refuses selective reporting")
    chosen_layer, chosen_family = summary["selected_by_layer"], summary["selected_by_family"]
    if set(chosen_layer) != {str(layer) for layer in config["layers"]} or set(chosen_family) != set(chosen_layer):
        raise ValueError("incomplete frozen validation selections")
    references = []
    for layer, selected in chosen_layer.items():
        references.append((selected, int(layer)))
    for layer, families in chosen_family.items():
        expected_families = {kind + "/" + mode for kind, mode in itertools.product(config["kinds"], config["preprocess_modes"])}
        if set(families) != expected_families:
            raise ValueError("incomplete frozen family selections")
        references.extend((selected, int(layer)) for selected in families.values())
    by_id = {row["id"]: row for row in candidates + controls}
    for selected, layer in references:
        row = by_id.get(selected["id"])
        if (row is None or row["layer"] != layer or selected["model_file"] != row["model_file"]
                or selected["model_sha256"] != row["model_sha256"]):
            raise ValueError("validation selection does not reference its frozen checkpoint")
    frozen, raw_models = [], {}
    for row in candidates + controls:
        identity = row["id"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", identity):
            raise ValueError("unsafe record identity")
        model_path = inside(root / "search" / row["model_file"], root / "search", strict=True)
        payload, raw = read_json(model_path)
        if digest_bytes(raw) != require_sha(row["model_sha256"]):
            raise ValueError("model SHA mismatch: " + identity)
        if payload.get("format") != "gate_phase2_v1" or payload["kind"] != row["kind"] or payload["layer"] != row["layer"]:
            raise ValueError("model identity differs from summary: " + identity)
        is_candidate = identity in expected_candidates
        for key in (("preprocess", "seed") if is_candidate else ("temperature",)):
            if payload[key] != row[key]:
                raise ValueError("model parameters differ from registered identity: " + identity)
        if is_candidate and payload["normalization"]["mode"] != row["preprocess"]:
            raise ValueError("model preprocessing identity mismatch")
        reference = by_id[f"layer{row['layer']}_max4_temp1"]["val"]
        val = row["val"]
        budget_pass = val["expected_selected_blocks"] <= reference["expected_selected_blocks"] * config["val_budget_ratio_max"]
        if "val_budget_pass" in row and bool(row["val_budget_pass"]) != bool(budget_pass):
            raise ValueError("recorded validation eligibility differs: " + identity)
        family_memberships = [f"{layer}/{family}" for layer, families in chosen_family.items()
                              for family, selected in families.items() if selected["id"] == identity]
        record = {key: copy.deepcopy(row.get(key)) for key in (
            "id", "kind", "preprocess", "seed", "temperature", "layer", "parameter_count", "selection", "val")}
        record.update(model_file=str(model_path), model_sha256=row["model_sha256"],
                      source="primary", source_id=identity,
                      frozen_model_file=str(output / "models" / (identity + ".json")),
                      role="candidate" if is_candidate else "temperature_control",
                      selected_by_layer=any(selected["id"] == identity for selected in chosen_layer.values()),
                      selected_by_family=family_memberships,
                      qualification=dict(val_budget_pass=bool(budget_pass),
                          checkpoint_budget_eligible=row.get("selection", {}).get("budget_eligible"),
                          val_mass_improved=val["expected_missed_mass"] < reference["expected_missed_mass"],
                          val_pv_nmse_not_worse=val["sampled_subset_pv_nmse_mean"] <= reference["sampled_subset_pv_nmse_mean"]))
        frozen.append(record)
        raw_models[identity] = raw
    record = dict(format=FORMAT, status="frozen", created_utc=now(), search_root=str(root), scope=SCOPE,
                  candidate_count=54, temperature_control_count=15, record_count=69,
                  code_commit=binding["code_commit"], config_sha256=binding["config_sha256"],
                  source_sha256=binding["source_sha256"], config=config,
                  trainval_dataset_sha256=trainval["sha256"], blind_dataset_sha256=blind["sha256"],
                  blind_dataset=dict(blind, path=str(blind_path)),
                  selected_by_layer=copy.deepcopy(chosen_layer), selected_by_family=copy.deepcopy(chosen_family),
                  records=frozen, blind_dataset_opened=False,
                  policy=dict(all_registered_configurations=True, selection_split="validation only",
                              no_new_selection=True, no_refit=True, no_recalibration=True),
                  inputs={label: dict(path=str(path), sha256=digest_bytes(raw_inputs[label]))
                          for label, path in paths.items()})
    record["search_sources"] = {"primary": dict(root=str(root), config=config,
        code_commit=binding["code_commit"], source_sha256=binding["source_sha256"],
        config_sha256=binding["config_sha256"], capture_config_sha256=capture["config_sha256"],
        trainval_dataset_sha256=trainval["sha256"], blind_dataset_sha256=blind["sha256"],
        selected_by_layer=copy.deepcopy(chosen_layer), selected_by_family=copy.deepcopy(chosen_family))}
    return record, raw_inputs, raw_models


def _prepare_additional(search_root, frozen, output):
    root = Path(search_root).resolve(strict=True)
    objects, raw_inputs = {}, {}
    for label, relative in (("summary", "search/SCAN_SUMMARY.json"), ("binding", "search/DATA_BINDING.json"),
                             ("capture", "capture/capture.json"), ("runtime", "runtime_config.json")):
        objects[label], raw_inputs[label] = read_json(inside(root / relative, root, strict=True))
    summary, binding, capture, runtime = (objects[key] for key in ("summary", "binding", "capture", "runtime"))
    config = binding["resolved_config"]
    if (binding.get("blind_dataset_loaded") is not False or summary.get("blind_dataset_loaded") is not False
            or binding.get("split_ids") != [0, 1] or capture.get("status") != "completed"):
        raise ValueError("refinement did not attest completed TRAIN/VAL-only execution")
    if (binding["config_sha256"] != digest_bytes(raw_inputs["runtime"])
            or any(config.get(key) != value for key, value in runtime.items())):
        raise ValueError("refinement config binding mismatch")
    trainval, blind = capture["datasets"]["training_dataset"], capture["datasets"]["blind_holdout"]
    if (binding["dataset_sha256"] != frozen["trainval_dataset_sha256"]
            or trainval["sha256"] != frozen["trainval_dataset_sha256"]
            or blind["sha256"] != frozen["blind_dataset_sha256"]
            or Path(blind["path"]).resolve() != Path(frozen["blind_dataset"]["path"]).resolve()
            or Path(binding["dataset_path"]).resolve() != Path(trainval["path"]).resolve()
            or trainval["split_values"] != [0, 1] or blind["split_values"] != [2]):
        raise ValueError("refinement used different teacher datasets")
    if (set(config["layers"]) != {0, 12, 23} or set(config["train_seeds"]) != {0, 1, 2}
            or config["kinds"] != ["pbit_4_8_1"] or config["preprocess_modes"] != ["query_relative"]
            or set(config["max4_temperatures"]) != {0.125, 0.25, 0.5, 1.0, 2.0}):
        raise ValueError("refinement must contain the registered nine pbit/query-relative candidates")
    if any(config[key] != frozen["config"][key] for key in ("device", "eval_seeds", "eval_draws", "epsilon")):
        raise ValueError("refinement evaluation protocol differs from primary")
    expected = {f"layer{layer}_pbit_4_8_1_query_relative_seed{seed}"
                for layer, seed in itertools.product(config["layers"], config["train_seeds"])}
    if len(summary["candidates"]) != 9 or {r["id"] for r in summary["candidates"]} != expected:
        raise ValueError("incomplete or duplicated refinement candidate grid")
    controls = {row["source_id"]: row for row in frozen["records"] if row["role"] == "temperature_control"}
    if len(summary["baselines"]) != 15 or {r["id"] for r in summary["baselines"]} != set(controls):
        raise ValueError("refinement temperature controls are incomplete")
    local_entries = {row["id"]: row for row in summary["candidates"] + summary["baselines"]}
    if (set(summary["selected_by_layer"]) != {str(layer) for layer in config["layers"]}
            or set(summary["selected_by_family"]) != set(summary["selected_by_layer"])):
        raise ValueError("refinement validation selections are incomplete")
    for layer in config["layers"]:
        families = summary["selected_by_family"][str(layer)]
        if set(families) != {"pbit_4_8_1/query_relative"}:
            raise ValueError("refinement family audit is incomplete")
        for selected in [summary["selected_by_layer"][str(layer)], *families.values()]:
            row = local_entries.get(selected["id"])
            if (row is None or row["layer"] != layer or selected["model_file"] != row["model_file"]
                    or selected["model_sha256"] != row["model_sha256"]):
                raise ValueError("refinement validation audit references a different checkpoint")
    for row in summary["baselines"]:
        path = inside(root / "search" / row["model_file"], root / "search", strict=True)
        if row["model_sha256"] != controls[row["id"]]["model_sha256"] or digest(path) != row["model_sha256"]:
            raise ValueError("refinement duplicate baseline differs from primary: " + row["id"])
    rows, models = [], {}
    for row in summary["candidates"]:
        identity = "refine1__" + row["id"]
        path = inside(root / "search" / row["model_file"], root / "search", strict=True)
        payload, raw = read_json(path)
        if digest_bytes(raw) != require_sha(row["model_sha256"]):
            raise ValueError("refinement model SHA mismatch")
        if payload.get("format") != "gate_phase2_v1" or any(payload[key] != row[key] for key in ("kind", "layer", "seed", "preprocess")):
            raise ValueError("refinement payload identity mismatch")
        reference = controls[f"layer{row['layer']}_max4_temp1"]["val"]
        val = row["val"]
        budget_pass = val["expected_selected_blocks"] <= reference["expected_selected_blocks"] * config["val_budget_ratio_max"]
        if bool(row["val_budget_pass"]) != bool(budget_pass):
            raise ValueError("refinement eligibility mismatch")
        record = {key: copy.deepcopy(row.get(key)) for key in (
            "kind", "preprocess", "seed", "temperature", "layer", "parameter_count", "selection", "val")}
        record.update(id=identity, source="refine1", source_id=row["id"], role="candidate",
            model_file=str(path), model_sha256=row["model_sha256"],
            frozen_model_file=str(output / "models" / (identity + ".json")),
            qualification=dict(val_budget_pass=bool(budget_pass),
                checkpoint_budget_eligible=row.get("selection", {}).get("budget_eligible"),
                val_mass_improved=val["expected_missed_mass"] < reference["expected_missed_mass"],
                val_pv_nmse_not_worse=val["sampled_subset_pv_nmse_mean"] <= reference["sampled_subset_pv_nmse_mean"]))
        rows.append(record)
        models[identity] = raw
    source = dict(root=str(root), config=config, code_commit=binding["code_commit"],
        source_sha256=binding["source_sha256"], config_sha256=binding["config_sha256"],
        capture_config_sha256=capture["config_sha256"],
        capture_training_config_differ=capture["config_sha256"] != binding["config_sha256"],
        trainval_dataset_sha256=trainval["sha256"], blind_dataset_sha256=blind["sha256"],
        selected_by_layer=copy.deepcopy(summary["selected_by_layer"]),
        selected_by_family=copy.deepcopy(summary["selected_by_family"]))
    return rows, models, source, raw_inputs


def _select_validation_only(frozen):
    """Pre-blind argmin over all frozen entries, retaining each source's budget gate."""
    layer_selections, family_selections = {}, {}
    for layer in frozen["config"]["layers"]:
        entries = [row for row in frozen["records"] if row["layer"] == layer]
        eligible = [row for row in entries if row["qualification"]["val_budget_pass"]]
        selected = min(eligible, key=lambda row: row["val"]["expected_missed_mass"])
        def describe(row):
            return dict(id=row["id"], source=row["source"], source_id=row["source_id"], layer=layer,
                        model_file=row["model_file"], model_sha256=row["model_sha256"],
                        val_budget_pass=row["qualification"]["val_budget_pass"],
                        criterion="minimum validation missed mass among per-source-budget-eligible entries; no blind metrics")
        layer_selections[str(layer)] = describe(selected)
        families = {}
        for kind, mode in itertools.product(frozen["config"]["kinds"], frozen["config"]["preprocess_modes"]):
            family = [row for row in entries if row["kind"] == kind and row["preprocess"] == mode]
            allowed = [row for row in family if row["qualification"]["val_budget_pass"]]
            chosen = min(allowed or family, key=lambda row: row["val"]["expected_missed_mass"])
            families[kind + "/" + mode] = dict(describe(chosen), fallback_if_no_eligible=not bool(allowed))
        family_selections[str(layer)] = families
    frozen["selected_by_layer"], frozen["selected_by_family"] = layer_selections, family_selections
    for row in frozen["records"]:
        row["selected_by_layer"] = any(s["id"] == row["id"] for s in layer_selections.values())
        row["selected_by_family"] = [layer + "/" + family for layer, families in family_selections.items()
                                     for family, selected in families.items() if selected["id"] == row["id"]]


def _prepare_baselines(search_root, frozen, output):
    """Freeze nine low-temperature and three TRAIN-threshold controls."""
    root = Path(search_root).resolve(strict=True)
    objects, raw_inputs = {}, {}
    for label, relative in (("summary", "search/SCAN_SUMMARY.json"), ("binding", "search/DATA_BINDING.json"),
                             ("capture", "capture/capture.json"), ("runtime", "runtime_config.json")):
        objects[label], raw_inputs[label] = read_json(inside(root / relative, root, strict=True))
    summary, binding, capture, runtime = (objects[key] for key in ("summary", "binding", "capture", "runtime"))
    config = binding["resolved_config"]
    if (binding.get("blind_dataset_loaded") is not False or summary.get("blind_dataset_loaded") is not False
            or binding.get("split_ids") != [0, 1] or capture.get("status") != "completed"
            or binding["config_sha256"] != digest_bytes(raw_inputs["runtime"])
            or any(config.get(key) != value for key, value in runtime.items())):
        raise ValueError("baseline extension is not a bound TRAIN/VAL-only run")
    trainval, held = capture["datasets"]["training_dataset"], capture["datasets"]["blind_holdout"]
    if (binding["dataset_sha256"] != frozen["trainval_dataset_sha256"]
            or trainval["sha256"] != frozen["trainval_dataset_sha256"]
            or held["sha256"] != frozen["blind_dataset_sha256"]
            or Path(held["path"]).resolve() != Path(frozen["blind_dataset"]["path"]).resolve()
            or Path(binding["dataset_path"]).resolve() != Path(trainval["path"]).resolve()
            or trainval["split_values"] != [0, 1] or held["split_values"] != [2]):
        raise ValueError("baseline extension teacher differs from primary")
    if any(config[key] != frozen["config"][key] for key in ("device", "eval_seeds", "eval_draws", "epsilon")):
        raise ValueError("baseline extension evaluation protocol differs")
    entries = summary["baselines"]
    if summary["candidates"] or len(entries) != 15 or len({r["id"] for r in entries}) != 15:
        raise ValueError("baseline extension must contain zero candidates and fifteen controls")
    temperature = [row for row in entries if row["kind"] == "max4_standardized_sigmoid"]
    hard = [row for row in entries if row["kind"] == "max4_train_threshold"]
    if (len(temperature) != 12 or len(hard) != 3
            or {(row["layer"], row["temperature"]) for row in temperature}
            != set(itertools.product((0, 12, 23), (.015625, .03125, .0625, 1.0)))
            or {row["layer"] for row in hard} != {0, 12, 23}):
        raise ValueError("baseline extension low-temperature/threshold grid is incomplete")
    primary_controls = {row["source_id"]: row for row in frozen["records"] if row["role"] == "temperature_control"}
    rows, models = [], {}
    for row in entries:
        source_id = row["id"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", source_id):
            raise ValueError("unsafe extension control identity")
        path = inside(root / "search" / row["model_file"], root / "search", strict=True)
        payload, raw = read_json(path)
        if digest_bytes(raw) != require_sha(row["model_sha256"]):
            raise ValueError("extension control SHA mismatch")
        if payload.get("format") != "gate_phase2_v1" or any(payload[key] != row[key] for key in ("kind", "layer")):
            raise ValueError("extension control identity mismatch")
        if row["kind"] == "max4_standardized_sigmoid":
            if payload["temperature"] != row["temperature"]:
                raise ValueError("extension temperature differs from payload")
            if row["temperature"] == 1.0:
                original = primary_controls[f"layer{row['layer']}_max4_temp1"]
                if row["model_sha256"] != original["model_sha256"]:
                    raise ValueError("extension duplicate temperature1 SHA differs")
                continue
        reference = primary_controls[f"layer{row['layer']}_max4_temp1"]["val"]
        val, identity = row["val"], "baseline1__" + source_id
        budget_pass = val["expected_selected_blocks"] <= reference["expected_selected_blocks"] * config["val_budget_ratio_max"]
        record = {key: copy.deepcopy(row.get(key)) for key in (
            "kind", "preprocess", "seed", "temperature", "layer", "parameter_count", "selection", "val")}
        record.update(id=identity, source="baseline1", source_id=source_id,
            role="threshold_control" if row["kind"] == "max4_train_threshold" else "temperature_control",
            model_file=str(path), model_sha256=row["model_sha256"],
            frozen_model_file=str(output / "models" / (identity + ".json")),
            qualification=dict(val_budget_pass=bool(budget_pass), checkpoint_budget_eligible=None,
                val_mass_improved=val["expected_missed_mass"] < reference["expected_missed_mass"],
                val_pv_nmse_not_worse=val["sampled_subset_pv_nmse_mean"] <= reference["sampled_subset_pv_nmse_mean"]))
        rows.append(record)
        models[identity] = raw
    source = dict(root=str(root), config=config, code_commit=binding["code_commit"],
        source_sha256=binding["source_sha256"], config_sha256=binding["config_sha256"],
        capture_config_sha256=capture["config_sha256"],
        capture_training_config_differ=capture["config_sha256"] != binding["config_sha256"],
        trainval_dataset_sha256=trainval["sha256"], blind_dataset_sha256=held["sha256"],
        selected_by_layer=copy.deepcopy(summary["selected_by_layer"]),
        selected_by_family=copy.deepcopy(summary["selected_by_family"]))
    return rows, models, source, raw_inputs


def freeze(search_root, output, additional_search_root=None, baseline_search_root=None):
    output = Path(output).resolve()
    record, raw_inputs, raw_models = _prepare_primary(search_root, output)
    if additional_search_root is not None:
        rows, models, source, extra_inputs = _prepare_additional(additional_search_root, record, output)
        record["records"].extend(rows)
        raw_models.update(models)
        record["search_sources"]["refine1"] = source
        record["record_count"], record["candidate_count"] = 78, 63
        raw_inputs.update({"refine1_" + key: value for key, value in extra_inputs.items()})
    if baseline_search_root is not None:
        rows, models, source, extra_inputs = _prepare_baselines(baseline_search_root, record, output)
        record["records"].extend(rows)
        raw_models.update(models)
        record["search_sources"]["baseline1"] = source
        record["record_count"] += 12
        record["temperature_control_count"], record["hard_threshold_control_count"] = 24, 3
        raw_inputs.update({"baseline1_" + key: value for key, value in extra_inputs.items()})
    source_names = set().union(*(source["source_sha256"] for source in record["search_sources"].values()))
    if any(Path(name).name != name for name in source_names):
        raise ValueError("unsafe operator source binding")
    evaluation_sources = {name: digest(Path(__file__).with_name(name)) for name in source_names}
    differences = {}
    for label, source in record["search_sources"].items():
        training_sources = source["source_sha256"]
        required = {"optimize.py", "network.py", "train.py"}
        allowed = required | ({"baseline_extension.py"} if label == "baseline1" else set())
        if not required <= set(training_sources) or not set(training_sources) <= allowed:
            raise ValueError("searches must bind all three core operators; only the extension may add its driver")
        changed = sorted(name for name in training_sources if training_sources[name] != evaluation_sources[name])
        if any(name != "optimize.py" for name in changed):
            raise ValueError("only the authorized optimize.py hard-threshold dispatch may differ from training")
        source["training_source_sha256"] = copy.deepcopy(training_sources)
        differences[label] = changed
    record["evaluation_source_sha256"] = evaluation_sources
    record["operator_compatibility"] = dict(
        training_sources_preserved=True, permitted_changed_file="optimize.py", changed_by_source=differences,
        reason="authorized addition of max4_train_threshold predict/sample dispatch; legacy-kind paths retained",
        unchanged_network_and_train_required=True,
        legacy_kind_regression="separate orchestrator verification; freeze does not run model code")
    _select_validation_only(record)
    output.mkdir(parents=True, exist_ok=False)
    (output / "models").mkdir()
    (output / "inputs").mkdir()
    for identity, raw in raw_models.items():
        with (output / "models" / (identity + ".json")).open("xb") as stream:
            stream.write(raw)
    for label, raw in raw_inputs.items():
        with (output / "inputs" / (label + ".json")).open("xb") as stream:
            stream.write(raw)
    write_json(output / "FREEZE.json", record)
    manifest(output, "FREEZE_MANIFEST.json")
    return record


def manifest(root, name="RESULT_MANIFEST.json"):
    files = [dict(path=path.relative_to(root).as_posix(), bytes=path.stat().st_size, sha256=digest(path))
             for path in sorted(root.rglob("*")) if path.is_file() and path.name != name]
    write_json(root / name, dict(created_utc=now(), files=files))


def load_frozen(path):
    """Verify the freeze and all model snapshots before opening the blind data."""
    path = Path(path).resolve(strict=True)
    root = path.parent
    saved, _ = read_json(root / "FREEZE_MANIFEST.json")
    listed = {}
    for item in saved["files"]:
        target = inside(root / item["path"], root, strict=True)
        if target.stat().st_size != item["bytes"] or digest(target) != require_sha(item["sha256"]):
            raise ValueError("frozen artifact changed: " + item["path"])
        listed[item["path"]] = item
    if "FREEZE.json" not in listed or path.name != "FREEZE.json":
        raise ValueError("freeze manifest does not bind FREEZE.json")
    frozen, _ = read_json(path)
    sources = frozen.get("search_sources", {})
    if "primary" not in sources or not set(sources) <= {"primary", "refine1", "baseline1"}:
        raise ValueError("unknown frozen search sources")
    count = 69 + (9 if "refine1" in sources else 0) + (12 if "baseline1" in sources else 0)
    if frozen.get("format") != FORMAT or frozen.get("record_count") != count or len(frozen["records"]) != count:
        raise ValueError("invalid freeze format or incomplete records")
    candidates, controls = _expected_ids(frozen["config"])
    expected = candidates | controls
    if "refine1" in sources:
        expected |= {f"refine1__layer{layer}_pbit_4_8_1_query_relative_seed{seed}"
                     for layer, seed in itertools.product((0, 12, 23), (0, 1, 2))}
    if "baseline1" in sources:
        controls = [row for row in frozen["records"] if row["source"] == "baseline1"]
        if (len(controls) != 12 or sum(row["kind"] == "max4_train_threshold" for row in controls) != 3
                or sum(row["kind"] == "max4_standardized_sigmoid" for row in controls) != 9):
            raise ValueError("frozen extension controls are incomplete")
        expected |= {row["id"] for row in controls}
    if {r["id"] for r in frozen["records"]} != expected:
        raise ValueError("frozen records do not cover registered grid")
    for source, metadata in sources.items():
        prefix = "" if source == "primary" else source + "_"
        runtime_path, binding_path = root / f"inputs/{prefix}runtime.json", root / f"inputs/{prefix}binding.json"
        if runtime_path.relative_to(root).as_posix() not in listed or binding_path.relative_to(root).as_posix() not in listed:
            raise ValueError("freeze manifest omits input bindings")
        runtime, _ = read_json(runtime_path)
        binding, _ = read_json(binding_path)
        if (binding["resolved_config"] != metadata["config"]
                or digest(runtime_path) != metadata["config_sha256"]
                or any(metadata["config"].get(key) != value for key, value in runtime.items())
                or binding["source_sha256"] != metadata["source_sha256"]
                or binding["source_sha256"] != metadata["training_source_sha256"]
                or binding["code_commit"] != metadata["code_commit"]):
            raise ValueError("frozen evaluation parameters differ from the search binding")
    payloads = {}
    for row in frozen["records"]:
        target = inside(row["frozen_model_file"], root, strict=True)
        if target.relative_to(root).as_posix() not in listed or digest(target) != row["model_sha256"]:
            raise ValueError("frozen model binding mismatch")
        payloads[row["id"]], _ = read_json(target)
    return frozen, payloads


def load_blind_dataset(path, expected_sha256, *, expected_arrays=None):
    """Read split labels first and reject train/val before reading feature rows."""
    import numpy as np
    if digest(path) != require_sha(expected_sha256):
        raise ValueError("blind dataset SHA mismatch")
    with np.load(path, allow_pickle=False) as archive:
        split = archive["split"]
        if split.ndim != 1 or not len(split) or not (split == 2).all() or split.dtype != np.int8:
            raise ValueError("blind evaluation accepts only nonempty split2 int8 rows")
        data = {key: archive[key] for key in archive.files}
    expected_dtypes = {key: "float32" for key in ("x", "mass", "block_v", "teacher_output")}
    expected_dtypes.update(valid="bool", forced="bool", counts="int16", split="int8")
    expected_dtypes.update({key: "int64" for key in ("layer", "head", "document", "position")})
    if set(data) != set(expected_dtypes):
        raise ValueError("unknown or missing blind array schema")
    for key, array in data.items():
        if str(array.dtype) != expected_dtypes[key] or array.dtype.hasobject:
            raise ValueError("blind array dtype mismatch: " + key)
        if expected_arrays and (list(array.shape) != expected_arrays[key]["shape"]
                                or str(array.dtype) != expected_arrays[key]["dtype"]):
            raise ValueError("blind capture manifest schema mismatch: " + key)
    return data


def allocation_context(paths):
    """Require the actual account/home and a personal canonical target path."""
    if not os.environ.get("SLURM_JOB_ID") or os.environ.get("CUDA_VISIBLE_DEVICES") in (None, ""):
        raise RuntimeError("blind evaluation requires an explicit Slurm GPU allocation")
    import pwd
    account = pwd.getpwuid(os.getuid())
    home = Path(account.pw_dir).resolve(strict=True)
    if (account.pw_name != "Weican_Chen" or home != Path("/home/Weican_Chen").resolve()
            or home.stat().st_uid != os.getuid() or Path.home().resolve() != home):
        raise RuntimeError("logged-in account or canonical personal home mismatch")
    for path in paths:
        inside(path, home)
    return dict(username=account.pw_name, uid=os.getuid(), home=str(home),
                job=os.environ["SLURM_JOB_ID"], node=platform.node(),
                cuda_visible_devices=os.environ["CUDA_VISIBLE_DEVICES"])


def verify_evaluation_sources(frozen):
    for name, expected in frozen["evaluation_source_sha256"].items():
        if Path(name).name != name or digest(Path(__file__).with_name(name)) != expected:
            raise ValueError("evaluation operator differs from frozen evaluation source: " + name)


def evaluate(freeze_path, output):
    freeze_path, output = Path(freeze_path).resolve(strict=True), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    context = allocation_context([freeze_path, output])
    frozen, payloads = load_frozen(freeze_path)
    allocation_context([frozen["blind_dataset"]["path"]] + [r["frozen_model_file"] for r in frozen["records"]])
    config = copy.deepcopy(frozen["config"])
    if not str(config["device"]).startswith("cuda"):
        raise ValueError("frozen runtime device must be CUDA")
    output.mkdir(parents=True, exist_ok=False)
    started = time.time()
    start_record = dict(started_utc=now(), status="started", freeze_path=str(freeze_path),
        freeze_sha256=digest(freeze_path), training_code_commit=frozen["code_commit"],
        evaluation_code_commit=os.environ.get("GATE_SOURCE_COMMIT", "unavailable"),
        config_sha256=frozen["config_sha256"], trainval_dataset_sha256=frozen["trainval_dataset_sha256"],
        blind_dataset_sha256=frozen["blind_dataset_sha256"], allocation=context,
        record_ids=[r["id"] for r in frozen["records"]], source_sha256=digest(__file__),
        evaluation_source_sha256=frozen["evaluation_source_sha256"],
        training_sources={name: dict(code_commit=source["code_commit"], training_source_sha256=source["training_source_sha256"])
                          for name, source in frozen["search_sources"].items()},
        operator_compatibility=frozen["operator_compatibility"], scope=SCOPE)
    # This is fsync'd before importing GPU code or opening the blind NPZ.
    write_json(output / "EVAL_STARTED.json", start_record)
    summary = dict(status="running", scope=SCOPE, binding=start_record,
                   selected_by_layer=copy.deepcopy(frozen["selected_by_layer"]),
                   selected_by_family=copy.deepcopy(frozen["selected_by_family"]),
                   no_new_selection=True, no_refit=True, no_recalibration=True, records=[])
    try:
        verify_evaluation_sources(frozen)
        package = __package__ or "experiments.pbit_gate_pilot_20261022"
        optimize = importlib.import_module(package + ".optimize")
        torch = optimize.torch
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise RuntimeError("exactly one allocated CUDA device required")
        torch.set_num_threads(int(config.get("threads", 4)))
        summary["environment"] = dict(torch=torch.__version__, python=sys.version,
                                      device=torch.cuda.get_device_name(0))
        data = load_blind_dataset(frozen["blind_dataset"]["path"], frozen["blind_dataset_sha256"],
                                 expected_arrays=frozen["blind_dataset"]["arrays"])
        optimize.validate_dataset(data)
        if set(data["layer"].tolist()) != set(config["layers"]):
            raise ValueError("blind layer coverage differs from frozen configuration")
        if len(data["split"]) != frozen["blind_dataset"]["groups"]:
            raise ValueError("blind group count differs from capture")
        (output / "records").mkdir()
        for row in frozen["records"]:
            part = optimize.subset(data, data["layer"] == row["layer"])
            record_config = copy.deepcopy(frozen["search_sources"][row["source"]]["config"])
            with torch.inference_mode():
                result = optimize.evaluate_payload(payloads[row["id"]], part, 2, record_config)
            record = dict(id=row["id"], kind=row["kind"], preprocess=row["preprocess"],
                          source=row["source"], source_id=row["source_id"],
                          seed=row["seed"], temperature=row["temperature"], layer=row["layer"],
                          model_sha256=row["model_sha256"], model_file=row["frozen_model_file"],
                          qualification=row["qualification"], selected_by_layer=row["selected_by_layer"],
                          selected_by_family=row["selected_by_family"], holdout=result)
            write_json(output / "records" / (row["id"] + ".json"), record)
            summary["records"].append(record)
            summary["completed_records"] = len(summary["records"])
            summary["elapsed_seconds"] = time.time() - started
            write_json(output / "PARTIAL.json", summary, replace=True)
            print(json.dumps(dict(completed_record=row["id"], completed_records=len(summary["records"]))), flush=True)
        # Detect accidental source/payload changes during the run as well.
        load_frozen(freeze_path)
        verify_evaluation_sources(frozen)
        summary.update(status="completed", completed_utc=now(), elapsed_seconds=time.time() - started)
        write_json(output / "BLIND_SUMMARY.json", summary)
    except BaseException as exc:
        summary.update(status="failed", failed_utc=now(), error=dict(type=type(exc).__name__, message=str(exc)),
                       elapsed_seconds=time.time() - started)
        write_json(output / "FAILURE.json", summary)
        raise
    finally:
        manifest(output)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    first = commands.add_parser("freeze")
    first.add_argument("--search-root", required=True)
    first.add_argument("--additional-search-root")
    first.add_argument("--baseline-search-root")
    first.add_argument("--output", required=True)
    second = commands.add_parser("evaluate")
    second.add_argument("--freeze", required=True)
    second.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.action == "freeze":
        freeze(args.search_root, args.output, args.additional_search_root, args.baseline_search_root)
    else:
        evaluate(args.freeze, args.output)


if __name__ == "__main__":
    main()
