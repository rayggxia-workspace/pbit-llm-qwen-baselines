"""CPU-allocation evidence package; never train, refit, or load model/data arrays."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import tarfile


PROJECT = Path("/home/Weican_Chen/projects/pbit-gate-pilot-issue92")
STRIPPED = {"per_document", "checkpoints"}


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def inside(path, root=PROJECT, strict=False):
    target = Path(path).resolve(strict=strict)
    if not target.is_relative_to(root.resolve(strict=True)):
        raise ValueError("path escapes verified personal project: " + str(target))
    return target


def info(path):
    path = Path(path)
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("only regular files are accepted: " + str(path))
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha(path)}


def compact(value):
    if isinstance(value, dict):
        return {key: compact(child) for key, child in value.items() if key not in STRIPPED}
    if isinstance(value, list):
        return [compact(child) for child in value]
    return value


def cpu_context(paths):
    if not os.environ.get("SLURM_JOB_ID") or os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise RuntimeError("packaging requires a Slurm CPU allocation with CUDA_VISIBLE_DEVICES=''")
    import pwd
    account = pwd.getpwuid(os.getuid())
    home = Path(account.pw_dir).resolve(strict=True)
    if (account.pw_name != "Weican_Chen" or home != Path("/home/Weican_Chen").resolve(strict=True)
            or home.stat().st_uid != os.getuid() or Path.home().resolve() != home):
        raise RuntimeError("logged-in identity/canonical personal home mismatch")
    project = PROJECT.resolve(strict=True)
    if not project.is_relative_to(home) or project.stat().st_uid != os.getuid():
        raise RuntimeError("project is not an owned personal root")
    for path in paths:
        inside(path, project)
    return {"user": account.pw_name, "uid": os.getuid(), "home": str(home),
            "project": str(project), "job": os.environ["SLURM_JOB_ID"], "node": platform.node(),
            "CUDA_VISIBLE_DEVICES": ""}


def manifest_entries(path, root):
    result = {}
    for item in read(path)["files"]:
        target = inside(Path(root) / item["path"], root, strict=True)
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("invalid manifest SHA")
        result[str(target)] = dict(item, path=str(target), manifest_path=str(Path(path).resolve()),
                                   provenance="recorded in original manifest; rehashed only when copied/validated")
    return result


def verify_file(path, entries):
    actual = info(path)
    expected = entries.get(actual["path"])
    if expected is None or actual["bytes"] != expected["bytes"] or actual["sha256"] != expected["sha256"]:
        raise ValueError("artifact differs from source manifest: " + actual["path"])
    return actual


def raw_copy_ids(frozen):
    """Copy policy uses only pre-blind frozen VAL fields, not blind outcomes."""
    rows = frozen["records"]
    chosen = [row["id"] for row in rows if row["source"] == "refine1"]
    if len(chosen) != 9:
        raise ValueError("expected nine refinement models")
    for layer in (0, 12, 23):
        references = [r for r in rows if r["source"] == "primary" and
                      r["source_id"] == f"layer{layer}_max4_temp1"]
        if len(references) != 1:
            raise ValueError("missing unique primary temperature1 control")
        chosen.append(references[0]["id"])
        controls = [r for r in rows if r["layer"] == layer and r["kind"] in
                    {"max4_standardized_sigmoid", "max4_train_threshold"}
                    and r["qualification"]["val_budget_pass"]]
        if not controls:
            raise ValueError("no VAL-budget-eligible max4 control")
        chosen.append(min(controls, key=lambda r: r["val"]["expected_missed_mass"])["id"])
    return list(dict.fromkeys(chosen))


def archive_package(package, archive, max_bytes=20 * 1024 * 1024):
    """Explicit immutable regular-file list, destination outside source tree."""
    package, archive = Path(package).resolve(strict=True), Path(archive).resolve()
    if archive.is_relative_to(package) or archive.exists():
        raise ValueError("archive must be new and outside the package source tree")
    files = sorted(p for p in package.rglob("*") if p.is_file() and p.name != "RECEIPT.json")
    originals = {p.relative_to(package).as_posix(): info(p) for p in files}
    declared = read(package / "PACKAGE_MANIFEST.json")["files"]
    if {r["path"] for r in declared} != set(originals) - {"PACKAGE_MANIFEST.json"}:
        raise ValueError("package manifest does not cover the exact regular-file set")
    for item in declared:
        actual = originals[item["path"]]
        if item["bytes"] != actual["bytes"] or item["sha256"] != actual["sha256"]:
            raise ValueError("package payload differs from its manifest: " + item["path"])
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as output:
        for path in files:
            output.add(path, arcname=path.relative_to(package).as_posix(), recursive=False)
    with tarfile.open(archive, "r:gz") as saved:
        members = saved.getmembers()
        if len(members) != len(originals) or {m.name for m in members} != set(originals):
            raise ValueError("archive member list differs from explicit payload")
        for member in members:
            if not member.isfile():
                raise ValueError("archive contains a nonregular entry")
            digest = hashlib.sha256()
            with saved.extractfile(member) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            expected = originals[member.name]
            if member.size != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
                raise ValueError("archive member content differs: " + member.name)
    receipt = {"archive_path": str(archive), "bytes": archive.stat().st_size,
               "sha256": sha(archive), "file_count": len(files), "archive_verified": True,
               "package_manifest_sha256": sha(package / "PACKAGE_MANIFEST.json"),
               "receipt_in_archive": False, "max_archive_bytes": max_bytes}
    if receipt["bytes"] > max_bytes:
        raise ValueError("verified archive exceeds configured small-artifact limit: " + str(receipt))
    return receipt


def run(config_path, output_path):
    config_path = Path(config_path).resolve(strict=True)
    config = read(config_path)
    roots = {name: Path(config[name + "_root"]).resolve(strict=True)
             for name in ("primary", "refine", "baseline", "blind")}
    freeze_path = Path(config["freeze_path"]).resolve(strict=True)
    output = Path(output_path).resolve()
    downloads = PROJECT / "downloads"
    context = cpu_context([config_path, output, downloads, freeze_path, *roots.values()])
    if output.exists():
        raise FileExistsError(output)
    for root in roots.values():
        if root.stat().st_uid != os.getuid():
            raise ValueError("source root is not owned by logged-in user")
    freeze = read(freeze_path)
    rows = freeze["records"]
    ids = [row["id"] for row in rows]
    if (freeze.get("status") != "frozen" or freeze.get("record_count") != 90
            or len(ids) != 90 or len(set(ids)) != 90
            or Counter(row["source"] for row in rows) != {"primary": 69, "refine1": 9, "baseline1": 12}):
        raise ValueError("freeze does not cover all ninety registered records")
    if any(not re.fullmatch(r"[A-Za-z0-9_.-]+", identity) for identity in ids):
        raise ValueError("unsafe record ID")
    # Declare raw-copy choices before opening the blind summary.
    raw_ids = raw_copy_ids(freeze)
    freeze_manifest = freeze_path.parent / "FREEZE_MANIFEST.json"
    frozen_entries = manifest_entries(freeze_manifest, freeze_path.parent)
    freeze_info = verify_file(freeze_path, frozen_entries)
    blind_manifest = roots["blind"] / "RESULT_MANIFEST.json"
    blind_entries = manifest_entries(blind_manifest, roots["blind"])
    blind_path = roots["blind"] / "BLIND_SUMMARY.json"
    verify_file(blind_path, blind_entries)
    blind = read(blind_path)
    started_path = roots["blind"] / "EVAL_STARTED.json"
    verify_file(started_path, blind_entries)
    started = read(started_path)
    if (blind.get("status") != "completed" or blind.get("completed_records") != 90
            or len(blind.get("records", [])) != 90
            or {r["id"] for r in blind["records"]} != set(ids)
            or started["freeze_sha256"] != freeze_info["sha256"]
            or Path(started["freeze_path"]).resolve() != freeze_path
            or set(started["record_ids"]) != set(ids)
            or blind.get("binding") != started
            or any(blind.get(key) is not True for key in ("no_new_selection", "no_refit", "no_recalibration"))):
        raise ValueError("blind completion/coverage/freeze binding failed")
    for label, source in (("primary", "primary"), ("refine", "refine1"), ("baseline", "baseline1")):
        if Path(freeze["search_sources"][source]["root"]).resolve() != roots[label]:
            raise ValueError("packaging roots differ from frozen training sources")
        prefix = "" if source == "primary" else source + "_"
        for name, relative in (("summary", "search/SCAN_SUMMARY.json"),
                               ("runtime", "runtime_config.json"),
                               ("binding", "search/DATA_BINDING.json"),
                               ("capture", "capture/capture.json")):
            expected = frozen_entries[str(inside(freeze_path.parent / "inputs" / (prefix + name + ".json"),
                                                freeze_path.parent, strict=True))]
            actual = info(inside(roots[label] / relative, roots[label], strict=True))
            if actual["sha256"] != expected["sha256"] or actual["bytes"] != expected["bytes"]:
                raise ValueError("source metadata changed since freeze: " + label + "/" + name)
        run_status = read(inside(roots[label] / "RUN.json", roots[label], strict=True))
        if run_status.get("status") != "completed_trainval_only" or run_status.get("blind_evaluated") is not False:
            raise ValueError("source run lacks completed TRAIN/VAL-only receipt")
    output.mkdir(parents=True, exist_ok=False)
    index = {"scope": "Original bytes/hashes retained; compacts remove only per_document/checkpoints.",
             "source_artifacts": [], "server_manifest_index": {}, "excluded_payloads":
             ["NPZ arrays", "large model weights", "raw training text", "complete large summaries/freeze", "active logs"],
             "server_originals_retained": True}

    def register(path, role, copy_to=None, compact_to=None, value=None):
        path = inside(path, strict=True)
        record = dict(info(path), role=role)
        if copy_to:
            target = output / copy_to
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            if sha(target) != record["sha256"]:
                raise ValueError("copy SHA mismatch")
            record["copied_to"] = copy_to
        if compact_to:
            write(output / compact_to, compact(read(path) if value is None else value))
            record["compact_to"] = compact_to
            record["stripped_keys"] = sorted(STRIPPED)
        index["source_artifacts"].append(record)
        return record

    register(freeze_path, "full_freeze_kept_server", compact_to="compacts/FREEZE_COMPACT.json", value=freeze)
    register(blind_path, "all_90_blind_records", compact_to="compacts/BLIND_COMPACT.json", value=blind)
    register(started_path, "original_eval_start", copy_to="raw/blind/EVAL_STARTED.json")
    register(config_path, "package_config", copy_to="raw/PACKAGE_CONFIG.json")
    for label, title in (("primary", "SEARCH"), ("refine", "REFINE"), ("baseline", "CONTROLS")):
        root = roots[label]
        summary_path = root / "search/SCAN_SUMMARY.json"
        register(summary_path, label + "_all_search_records", compact_to=f"compacts/{title}_COMPACT.json")
        for relative in ("RUN.json", "runtime_config.json", "search/DATA_BINDING.json",
                         "search/RESULT_MANIFEST.json", "MANIFEST.json"):
            source = inside(root / relative, root, strict=True)
            register(source, label + "_original_metadata", copy_to=f"raw/{label}/{Path(relative).name}")
        if label == "primary":
            register(root / "capture/capture.json", "original_teacher_capture", copy_to="raw/primary/capture.json")
            if (root / "capture/RESULT_MANIFEST.json").is_file():
                register(root / "capture/RESULT_MANIFEST.json", "capture_manifest", copy_to="raw/primary/CAPTURE_MANIFEST.json")
        if label == "baseline":
            register(root / "CURVE_SUMMARY.json", "original_training_curve_summary", copy_to="raw/baseline/CURVE_SUMMARY.json")
        for relative in ("MANIFEST.json", "search/RESULT_MANIFEST.json"):
            index["server_manifest_index"].update(manifest_entries(root / relative, root / Path(relative).parent))
    register(freeze_manifest, "complete_freeze_manifest", copy_to="raw/freeze/FREEZE_MANIFEST.json")
    register(blind_manifest, "complete_blind_manifest", copy_to="raw/blind/RESULT_MANIFEST.json")
    index["server_manifest_index"].update(frozen_entries)
    index["server_manifest_index"].update(blind_entries)
    blind_rows = {row["id"]: row for row in blind["records"]}
    for row in rows:
        path = inside(row["frozen_model_file"], freeze_path.parent, strict=True)
        actual = verify_file(path, frozen_entries)
        if actual["sha256"] != row["model_sha256"] or blind_rows[row["id"]]["model_sha256"] != row["model_sha256"]:
            raise ValueError("freeze/blind model SHA mismatch")
        if path.stat().st_size > 256 * 1024:
            raise ValueError("frozen gate model unexpectedly large")
        register(path, "frozen_small_model", copy_to="models/" + row["id"] + ".json")
        record_path = inside(roots["blind"] / "records" / (row["id"] + ".json"), roots["blind"], strict=True)
        verify_file(record_path, blind_entries)
        raw_record = read(record_path)
        if raw_record != blind_rows[row["id"]] or raw_record["model_sha256"] != row["model_sha256"]:
            raise ValueError("per-record blind artifact differs from all-record summary")
        if row["id"] in raw_ids:
            register(record_path, "predeclared_raw_blind_record", copy_to="raw_records/" + row["id"] + ".json")
    write(output / "RAW_COPY_POLICY.json", {"freeze_sha256": freeze_info["sha256"], "record_ids": raw_ids,
        "maximum_raw_records": 15, "actual_raw_records": len(raw_ids), "policy":
        "nine refine1 models, three primary temperature1 controls, and one VAL-budget-eligible minimum-missed-mass max4 control per layer; deduplicated",
        "selection_input": "frozen validation fields only, before reading blind summary",
        "candidate_conclusions_unchanged": True, "all_90_results_retained_in_compact": True})
    write(output / "VALIDATION.json", {"status": "passed", "allocation": context,
        "created_utc": datetime.now(timezone.utc).isoformat(), "freeze_sha256": freeze_info["sha256"],
        "record_count": 90, "frozen_model_count": 90, "verified_individual_blind_records": 90,
        "blind_completed": True, "model_sha_binding": True, "no_new_model_selection": True,
        "no_training_or_array_loading": True, "all_full_originals_retained_server": True,
        "raw_copy_choices_are_not_model_selection": True, "package_source_sha256": sha(__file__)})
    write(output / "ARTIFACT_INDEX.json", index)
    package_files = sorted(p for p in output.rglob("*") if p.is_file())
    write(output / "PACKAGE_MANIFEST.json", {"self_excluded": True, "receipt_not_archived": True,
        "files": [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)} for p in package_files]})
    receipt = archive_package(output, downloads / (output.name + ".tar.gz"), config.get("max_archive_bytes", 20 * 1024 * 1024))
    receipt.update(status="completed", package_path=str(output), validated_records=90, raw_records=len(raw_ids))
    write(output / "RECEIPT.json", receipt)
    print(json.dumps(receipt), flush=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True, help="new personal package directory")
    args = parser.parse_args()
    run(args.config, args.output)


if __name__ == "__main__":
    main()
