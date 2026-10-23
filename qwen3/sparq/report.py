"""Offline Issue157 artifact verification/reporting; standard library only.

python -m qwen3.sparq.report RESULTS_DIR --output REPORT_DIR [--source-root SNAPSHOT]
python -m qwen3.sparq.report --self-test

Only immutable result envelopes count as evidence. progress.jsonl, smoke scores
and incomplete .tmp writes never contribute to full quality numerators.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import statistics
import struct


MODEL = "Qwen/Qwen3-4B"
REVISION = "1cfa9a7208912126459214e8b04321603b3df60c"
TASKS = {
    "piqa": (1838, "validation", "40e1677bba609c8801deacc171d76f3e24c083f365c95a1cbda7520c923dfea2"),
    "arc_easy": (2376, "test", "4160597d618ae851c7eb04e281574f3f654776216ac6b6641588d64527b47177"),
    "hellaswag": (10042, "validation", "899813071e1e95efafec90f856e1987d2150fa4d020fc005df6962c259f660cd"),
}
PLAN_KEYS = ("segment_id", "begin", "end", "first_target", "last_target_exclusive", "prefill_tokens", "scored_tokens")
COUNTERS = ("query_groups", "sparse_groups", "dense_groups", "full_budget_groups", "zero_coverage_groups")


class AuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load(path):
    def duplicate_safe(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result
    def nonfinite(value):
        raise AuditError(f"nonfinite JSON value in {path}: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=duplicate_safe, parse_constant=nonfinite)


def _int(value, name, minimum=0):
    require(type(value) is int and value >= minimum, f"invalid {name}: {value}")
    return value


def _number(value, name, minimum=None):
    require(type(value) in (int, float) and math.isfinite(value), f"nonfinite/non-numeric {name}")
    require(minimum is None or value >= minimum, f"negative {name}")
    return value


def _equal_number(actual, expected, name):
    _number(actual, name)
    require(math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10), f"numeric mismatch {name}: {actual} != {expected}")


def _hash(value, name, length=64):
    require(isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value), f"invalid {name} hash")


def _safe_child(root, name):
    path = PurePosixPath(name)
    require(not path.is_absolute() and ".." not in path.parts and "\\" not in name, f"unsafe source/artifact path: {name}")
    target = (root / name).resolve()
    require(target.is_relative_to(root), f"path escapes root: {name}")
    return target


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def full_plan(n, context=2048, stride=1024):
    """Independent interval derivation; no import of the runner/scoring code."""
    _int(n, "source tokens", 2)
    require(context == 2048 and stride == 1024, "this review pins full WT2 2048/1024")
    result, next_target, begin = [], 1, 0
    while next_target < n:
        end = min(begin + context, n)
        require(begin < next_target < end, "invalid full plan coverage")
        result.append(dict(segment_id=len(result), begin=begin, end=end,
            first_target=next_target, last_target_exclusive=end,
            prefill_tokens=next_target-begin-1, scored_tokens=end-next_target))
        next_target, begin = end, begin + stride
    require(sum(r["scored_tokens"] for r in result) == n-1, "full plan denominator differs from N-1")
    return result


def _positions_hash(rows):
    digest = hashlib.sha256()
    for row in rows:
        for position in range(row["first_target"], row["last_target_exclusive"]):
            digest.update(struct.pack("<q", position))
    return digest.hexdigest()


def _nll(rows):
    if not rows:
        return dict(scored_tokens=0, nll_sum=0., mean_nll=None, perplexity=None)
    count = sum(r["scored_tokens"] for r in rows)
    value = math.fsum(_number(r["nll_sum"], "NLL", 0) for r in rows)
    require(count > 0 and value/count < 700, "invalid/overflowing PPL")
    return dict(scored_tokens=count, nll_sum=value, mean_nll=value/count, perplexity=math.exp(value/count))


def _check_nll(result, rows, where):
    computed = _nll(rows)
    for key, expected in computed.items():
        _equal_number(result.get(key), expected, where + "." + key)
    return computed


def _check_rows(rows, plan, where, target_hash=True):
    require(isinstance(rows, list) and rows, f"empty records: {where}")
    seen = set()
    for row in rows:
        i = _int(row.get("segment_id"), "segment id")
        require(i < len(plan) and i not in seen, f"duplicate/out-of-plan segment: {where}/{i}")
        seen.add(i)
        require(all(type(row.get(k)) is int and row[k] == plan[i][k] for k in PLAN_KEYS), f"window differs from actual plan: {where}/{i}")
        _number(row.get("nll_sum"), "NLL", 0)
        if target_hash:
            require(row.get("target_positions_sha256_le_int64") == _positions_hash([plan[i]]), f"target-position hash mismatch: {where}/{i}")
    require([r["segment_id"] for r in rows] == sorted(seen), f"records are out of order: {where}")


def _prefix(ids):
    value = 0
    while value in ids:
        value += 1
    return value


def _audit(result, queries, mode, identity):
    audit = result.get("execution_audit", {})
    require(audit.get("installed_layers") == 36, "Qwen3-4B audit must cover 36 layers")
    require(audit.get("every_scored_predictor_executed_all_layers") is True, "missing all-layer execution assertion")
    tokens = audit["tokens_per_layer"]
    for phase in ("prefill", "decode"):
        attention, ffn = tokens[phase]["attention"], tokens[phase]["ffn"]
        require(len(attention) == 36 and attention == ffn, "attention/FFN lifetime or layer coverage differs")
        require(all(type(x) is int and x >= 0 for x in attention), "invalid per-layer token count")
    require(tokens["decode"]["attention"] == [queries]*36, "scored predictor count differs from all-layer audit")
    require(result.get("ffn") == "none" and result.get("ffn_config") is None, "result changed original FFN")
    replacement = audit.get("replacement", {})
    require(replacement.get("mode") == mode and replacement.get("installed_layers") == 36, "replacement audit mode/layer mismatch")
    layers = replacement.get("layers", {})
    require(set(layers) == {str(i) for i in range(36)}, "missing replacement layers")
    if mode == "sparq":
        require(replacement.get("config") == identity["config"], "SparQ config differs from identity")
    counters = {}
    for layer, value in layers.items():
        require(value["decode_query_tokens"] == queries and value["head_rows"] == 32*queries, "Q head decode count mismatch")
        require(value["decode_calls"] == audit["calls"]["decode"], "decode call dispatch mismatch")
        if mode == "sparq":
            counts = {k: _int(value["diagnostics"].get("logical_counts."+k), k) for k in COUNTERS}
            require(counts["query_groups"] == 8*queries, "KV group count differs from queries")
            require(counts["sparse_groups"] + counts["dense_groups"] == counts["query_groups"], "sparse+dense groups do not conserve")
            require(counts["full_budget_groups"] + counts["zero_coverage_groups"] == counts["dense_groups"], "fallback groups do not conserve")
            counters[layer] = counts
    return counters


def _combine_audits(audits):
    layers = {}
    for audit in audits:
        for layer, counts in audit.items():
            layers.setdefault(layer, Counter()).update(counts)
    result = {}
    for layer, counts in sorted(layers.items(), key=lambda row: int(row[0])):
        result[layer] = dict(counts, sparse_group_fraction=counts["sparse_groups"]/counts["query_groups"] if counts["query_groups"] else None)
    total = Counter()
    for counts in layers.values():
        total.update(counts)
    return dict(layers=result, totals=dict(total), sparse_group_fraction=
                total["sparse_groups"]/total["query_groups"] if total["query_groups"] else None,
                meaning="group counters across all executed Q predictor tokens/layers; short contexts can fall back to all KV")


def _identity(identity, source_root):
    require(identity.get("model") == MODEL and identity.get("revision") == REVISION, "not the pinned post-trained Qwen3-4B")
    require(identity.get("original_ffn") is True, "identity does not preserve original FFN")
    cfg = identity["config"]
    require(all(cfg.get(k) == v for k, v in dict(r=32, k_total=128, local_total=32,
        reallocation=False, selection="probability_sum").items()), "unexpected SparQ algorithm/config")
    require(type(cfg.get("validate_finite")) is bool, "missing finite-check policy")
    require(identity["ppl"]["context"] == 2048 and identity["ppl"]["stride"] == 1024, "unexpected PPL protocol")
    _int(identity["ppl"]["chunk"], "PPL chunk", 1)
    _int(identity["task_chunk"], "task chunk", 1)
    for name, (count, split, checksum) in TASKS.items():
        record = identity["tasks"][name]
        require((record["documents"], record["split"], record["dataset_sha256"]) == (count, split, checksum), f"wrong official task split: {name}")
    _hash(identity["tokens_sha256"], "token IDs")
    _hash(identity["task_tokenization_sha256"], "task tokenization")
    _hash(identity["ready_sha256"], "READY")
    execution = identity["execution"]
    require(execution["repo"] == "rayggxia-workspace/pbit-llm-qwen-baselines", "unexpected repository")
    _hash(execution["commit"], "commit", 40)
    files = execution["files"]
    required = {"qwen3/sparq/"+n for n in ("core.py", "adapter.py", "run.py", "scoring.py", "SOURCES.json", "model_identity.json")}
    required.add("qwen3/stochastic/vendor/scoring.py")
    require(required <= set(files), "source identity omits core dependencies")
    for name, checksum in files.items():
        _hash(checksum, name)
        require(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts and "\\" not in name, "unsafe source path")
        if source_root is not None:
            path = _safe_child(source_root, name)
            require(path.is_file() and sha(path) == checksum, f"source bytes differ: {name}")
    return dict(model=MODEL, revision=REVISION, model_type="post-trained (not Base)",
        source_commit=execution["commit"], registered_source_files=len(files),
        local_source_bytes_verified=source_root is not None,
        model_weight_bytes_rehashed=False, original_ffn=True, config=cfg,
        limits="identity/envelope consistency is not an independent checkpoint rehash or cryptographic authorship proof")


def _load_artifacts(root, identity):
    experiment, artifacts, receipt, auxiliary = fingerprint(identity), {}, {}, []
    for path in sorted(root.rglob("*.json")):
        name = path.relative_to(root).as_posix()
        require(path.resolve().is_relative_to(root), f"artifact symlink escapes root: {name}")
        if name == "IDENTITY.json":
            continue
        if name.startswith(("ppl_parts/", "task_parts/", "anchor/")):
            require(re.fullmatch(r"(?:ppl_parts/(?:dense|sparq)_\d+|task_parts/(?:piqa|arc_easy|hellaswag)_(?:dense|sparq)_\d+|anchor/window_\d+)\.json", name),
                    f"unrecognized scientific shard name: {name}")
        value = _load(path)
        scientific = name.startswith(("ppl_parts/", "task_parts/", "anchor/")) or name[:-5] in (
            "ppl_dense", "ppl_sparq", "ppl_vectorized_bf16", "benchmark", "SUMMARY", "preflight", "document_batch_gate") or name.startswith("task_")
        envelope = isinstance(value, dict) and any(k in value for k in ("experiment", "result_sha256", "result"))
        if not envelope:
            require(not scientific, f"scientific result lacks integrity envelope: {name}")
            auxiliary.append(name)
            continue
        require(value.get("experiment") == experiment, f"experiment identity mismatch: {name}")
        require(value.get("result_sha256") == fingerprint(value.get("result")), f"result hash mismatch: {name}")
        artifacts[name[:-5]] = value["result"]
        receipt[name] = dict(file_sha256=sha(path), result_sha256=value["result_sha256"], job=value.get("job"))
        for record in _walk(value["result"]):
            for source, checksum in record.get("source_files_sha256", {}).items():
                require(identity["execution"]["files"].get(source) == checksum, f"result source differs from IDENTITY: {name}/{source}")
    transfer_verified = 0
    transfer_paths = set()
    for manifest_name in ("FILES.json", "TRANSFER.json"):
        manifest = root/manifest_name
        if not manifest.exists():
            continue
        contents = _load(manifest)
        entries = contents["files"] if manifest_name == "TRANSFER.json" else contents
        if manifest_name == "TRANSFER.json":
            require(contents["commit"] == identity["execution"]["commit"], "transfer manifest source commit differs")
        for name, record in entries.items():
            path = _safe_child(root, name)
            require(path.is_file() and sha(path) == record["sha256"], f"download manifest mismatch: {name}")
            transfer_paths.add(name)
    transfer_verified = len(transfer_paths)
    return artifacts, dict(experiment=experiment, identity_file_sha256=sha(root/"IDENTITY.json"),
        envelopes=receipt, envelope_count=len(receipt), downloaded_file_hashes_verified=transfer_verified,
        auxiliary_json_excluded=auxiliary, unfinished_tmp_files=[p.relative_to(root).as_posix() for p in root.rglob("*.tmp")])


def _source_count(artifacts, identity):
    counts = set()
    for result in artifacts.values():
        for row in _walk(result):
            if row.get("token_ids_sha256_le_int64") == identity["tokens_sha256"] and "scoring_plan" in row:
                counts.add(_int(row["scoring_plan"]["source_tokens"], "source tokens", 2))
            if row.get("token_ids_sha256") == identity["tokens_sha256"] and "source_tokens" in row:
                counts.add(_int(row["source_tokens"], "source tokens", 2))
    require(len(counts) <= 1, "same token hash claims different corpus lengths")
    return next(iter(counts), None)


def _ppl(artifacts, identity, plan):
    reports, maps = {}, {}
    for mode in ("dense", "sparq"):
        records, audits, parts = {}, [], []
        for name, result in sorted(artifacts.items()):
            match = re.fullmatch(r"ppl_parts/"+mode+r"_(\d+)", name)
            if not match:
                continue
            require(plan is not None, "PPL parts lack full-corpus token identity")
            start, chunk = int(match[1]), identity["ppl"]["chunk"]
            require(start % chunk == 0 and start < len(plan), "PPL shard start differs from run plan")
            expected = plan[start:min(start+chunk, len(plan))]
            rows = result["records"]
            require(result.get("mode") == mode and result.get("scope") == "partial_segments", "smoke/full PPL mixed into parts")
            require(result.get("complete") is False and result["scoring_plan"].get("smoke_limit") is None, "PPL part claims full or smoke scope")
            require(result["token_ids_sha256_le_int64"] == identity["tokens_sha256"], "PPL part token identity mismatch")
            require(result["scoring_parameters"]["protocol"] == "full", "suffix result cannot count as full PPL")
            parameters = result["scoring_parameters"]
            require(all(parameters.get(k) == identity["ppl"][k] for k in ("context", "stride", "batch")), "PPL batch/shape protocol differs from identity")
            require(parameters.get("segment_start") == start and parameters.get("segment_count") == len(expected), "PPL selected interval differs")
            require([r["segment_id"] for r in rows] == [r["segment_id"] for r in expected], "PPL shard missing/repeated windows")
            require(result["scoring_plan"]["segments"] == expected, "PPL metadata plan differs")
            require(result["scoring_plan"]["requested_segments"] == len(plan), "incorrect total window count")
            require(result["scoring_plan"]["target_positions_sha256_le_int64"] == _positions_hash(expected), "part target hash differs")
            _check_rows(rows, plan, name)
            computed = _check_nll(result, rows, name)
            require(result["scoring_plan"]["scored_tokens"] == computed["scored_tokens"], "part metadata target count differs")
            audits.append(_audit(result, computed["scored_tokens"], mode, identity))
            for row in rows:
                require(row["segment_id"] not in records, "duplicate PPL window across parts")
                records[row["segment_id"]] = row
            parts.append(name)
        rows = [records[i] for i in sorted(records)]
        final, complete = artifacts.get("ppl_"+mode), False
        if final is not None:
            require(plan is not None and final.get("complete") is True and final.get("mode") == mode, "bad PPL final summary")
            require(final["source_tokens"] == plan[-1]["end"] and final["token_ids_sha256"] == identity["tokens_sha256"], "PPL final source mismatch")
            _check_rows(final["records"], plan, "ppl_"+mode)
            require([r["segment_id"] for r in final["records"]] == list(range(len(plan))), "PPL final missing windows")
            _check_nll(final, final["records"], "ppl_"+mode)
            require(final["scored_tokens"] == plan[-1]["end"]-1, "PPL final denominator is not N-1")
            require(final.get("original_ffn") is True and final.get("all_scored_predictors_single_query_all_layers") is True, "PPL final omitted FFN/single-query audit")
            expected_names = [f"ppl_parts/{mode}_{s:04d}" for s in range(0, len(plan), identity["ppl"]["chunk"])]
            require(final["part_names"] == expected_names, "PPL final part manifest differs")
            for i, row in records.items():
                require(row == final["records"][i], "PPL final/part records differ")
            complete = len(records) == len(plan)
        reports[mode] = dict(**_nll(rows), verified_windows=len(rows),
            contiguous_prefix_windows=_prefix(records), expected_windows=len(plan) if plan else None,
            expected_targets=plan[-1]["end"]-1 if plan else None, final_summary_present=final is not None,
            verified_complete=complete, verified_parts=parts, attention=_combine_audits(audits))
        maps[mode] = records
    common = sorted(set(maps["dense"]) & set(maps["sparq"]))
    paired = {mode: _nll([maps[mode][i] for i in common]) for mode in maps}
    paired.update(windows=len(common), same_target_subset=True,
        delta_mean_nll=(paired["sparq"]["mean_nll"]-paired["dense"]["mean_nll"]) if common else None)
    return dict(modes=reports, paired_verified_subset=paired,
                warning="partial paired PPL is conditional on the downloaded target subset; not full WT2")


def _anchor(artifacts, plan):
    rows = {}
    for name, row in artifacts.items():
        match = re.fullmatch(r"anchor/window_(\d+)", name)
        if match:
            require(plan is not None, "anchor rows cannot be checked without corpus token identity")
            require(int(match[1]) == row["segment_id"], "anchor filename/row mismatch")
            _check_rows([row], plan, name, target_hash=False)
            require(row["segment_id"] not in rows, "duplicate anchor window")
            rows[row["segment_id"]] = row
    final = artifacts.get("ppl_vectorized_bf16")
    if final is not None:
        require(plan is not None and final.get("complete") is True, "bad vectorized anchor summary")
        _check_rows(final["records"], plan, "anchor summary", target_hash=False)
        require([r["segment_id"] for r in final["records"]] == list(range(len(plan))), "anchor summary missing windows")
        _check_nll(final, final["records"], "anchor summary")
        require(final["scored_tokens_expected"] == plan[-1]["end"]-1, "anchor expected targets differ")
        require(all(row == final["records"][i] for i, row in rows.items()), "anchor summary differs from windows")
    verified_rows = final["records"] if final is not None else [rows[i] for i in sorted(rows)]
    return dict(**_nll(verified_rows), verified_windows=len(verified_rows), downloaded_window_shards=len(rows),
        expected_windows=len(plan) if plan else None, final_summary_present=final is not None,
        verified_complete=final is not None and len(verified_rows) == len(plan),
        evidence="all window records inside full anchor envelope suffice; separately downloaded window shards cross-checked when present",
        scope="vectorized native BF16 anchor; different execution shape from cached paired PPL")


def _task_metrics(rows):
    return {key: math.fsum(float(r["metrics"][key]) for r in rows)/len(rows) if rows else None
            for key in ("acc", "acc_norm")}


def _task_row(row, name, index):
    require((row.get("id"), row.get("task"), row.get("doc_id")) == (f"{name}:{index}", name, index), "task document IDs are not contiguous official IDs")
    require(set(row["metrics"]) == {"acc", "acc_norm"}, "unexpected official metric keys")
    require(all(type(x) in (int, float, bool) and float(x) in (0., 1.) for x in row["metrics"].values()), "task metrics must be binary official rows")
    require(len(row["choices"]) >= 2, "missing task choices")
    for choice in row["choices"]:
        _int(choice["tokens"], "choice token count", 1)
        _number(choice["logprob"], "choice logprob")


def _tasks(artifacts, identity):
    reports = {}
    for task, (expected_count, _, _) in TASKS.items():
        modes, maps = {}, {}
        for mode in ("dense", "sparq"):
            records, audits, names = {}, [], []
            for name, part in sorted(artifacts.items()):
                match = re.fullmatch(r"task_parts/"+task+"_"+mode+r"_(\d+)", name)
                if not match:
                    continue
                start, chunk = int(match[1]), identity["task_chunk"]
                require(start % chunk == 0 and start < expected_count, "task part start differs from run plan")
                rows = part["documents"]
                require(part["mode"] == mode and part.get("shard_complete") is True and part.get("complete") is False,
                        "task smoke or completed-summary scope mixed into parts")
                require(part.get("smoke_limit") is None and part["shard_start"] == start, "task part smoke/start mismatch")
                if identity.get("document_batch") == 1:
                    require(part.get("test") == "qwen3_sparq_official_mc_likelihood" and
                            part.get("choice_batch") == identity.get("choice_batch", 4),
                            "formal serial-document protocol differs from identity")
                require(part["full_task_documents"] == expected_count and len(rows) == min(chunk, expected_count-start), "task part size mismatch")
                require(part["evaluated_documents"] == len(rows) == part["requested_documents"], "task shard document denominator differs")
                for index, row in enumerate(rows, start):
                    _task_row(row, task, index)
                    require(index not in records, "duplicate task document across shards")
                    records[index] = row
                targets = sum(c["tokens"] for row in rows for c in row["choices"])
                shared = sum(len(row["choices"])-1 for row in rows)
                require(part["choice_target_scores"] == targets and part["shared_first_target_reuses"] == shared, "task choice target/reuse counts differ")
                audits.append(_audit(part, targets-shared, mode, identity))
                names.append(name)
            rows = [records[i] for i in sorted(records)]
            metrics = _task_metrics(rows)
            final = artifacts.get(f"task_{task}_{mode}")
            complete = final is not None and len(rows) == expected_count
            if final is not None:
                require(final.get("complete") is True and final.get("task") == task and final.get("mode") == mode,
                        "bad official task summary identity")
                require(final["documents"] == expected_count and final["original_ffn"] is True, "task summary size/FFN mismatch")
                expected_names = [f"task_parts/{task}_{mode}_{s:05d}" for s in range(0, expected_count, identity["task_chunk"])]
                require(final["source_parts"] == expected_names, "task summary part manifest differs")
                if complete:
                    for key, value in metrics.items():
                        _equal_number(final["metrics"][key], value, f"{task}/{mode}/{key}")
                        _equal_number(final["binomial_standard_error"][key], math.sqrt(value*(1-value)/expected_count), "task standard error")
            modes[mode] = dict(verified_documents=len(rows), contiguous_prefix_documents=_prefix(records),
                expected_documents=expected_count, verified_complete=complete, final_summary_present=final is not None,
                metrics_from_official_rows=metrics, verified_parts=names, attention=_combine_audits(audits))
            maps[mode] = records
        common = sorted(set(maps["dense"]) & set(maps["sparq"]))
        paired = dict(documents=len(common), raw_prediction_flips=0, metrics={})
        for key in ("acc", "acc_norm"):
            states = Counter((int(maps["dense"][i]["metrics"][key]), int(maps["sparq"][i]["metrics"][key])) for i in common)
            paired["metrics"][key] = dict(both_correct=states[1, 1], both_wrong=states[0, 0],
                dense_correct_sparq_wrong=states[1, 0], dense_wrong_sparq_correct=states[0, 1],
                delta_percentage_points=100*(states[0, 1]-states[1, 0])/len(common) if common else None)
        for i in common:
            a, b = maps["dense"][i]["choices"], maps["sparq"][i]["choices"]
            require([x["tokens"] for x in a] == [x["tokens"] for x in b], "paired choice/tokenization differs")
            paired["raw_prediction_flips"] += max(range(len(a)), key=lambda j:a[j]["logprob"]) != max(range(len(b)), key=lambda j:b[j]["logprob"])
        reports[task] = dict(modes=modes, paired_verified_subset=paired,
            score_verification="independent aggregation of stored official per-row acc/acc_norm; labels and choice-character lengths are not in artifacts",
            normalized_prediction_recomputed=False)
    return reports


def _verify_power(item):
    power = item["power"]
    duration = item["wall_seconds"]
    require(power is not None and duration >= 1, "power uses unsupported short/missing window")
    require(item.get("phase_energy_attribution_validated") is False, "power mislabeled as validated phase attribution")
    samples = item["power_samples_relative_s_w"]
    require(len(samples) >= 3 and samples[0][0] <= 0 and samples[-1][0] >= duration and
            any(0 < t < duration for t, _ in samples), "power samples do not cover phase")
    energy, gap = 0., 0.
    for (t0, p0), (t1, p1) in zip(samples, samples[1:]):
        for value in (t0, t1, p0, p1):
            _number(value, "power sample")
        require(t1 > t0 and min(p0, p1) >= 0, "invalid power sample order/value")
        left, right = max(0., t0), min(duration, t1)
        if right > left:
            gap = max(gap, t1-t0)
            pa = p0+(p1-p0)*(left-t0)/(t1-t0)
            pb = p0+(p1-p0)*(right-t0)/(t1-t0)
            energy += (pa+pb)*(right-left)/2
    allowed = max(.25, 5*_number(item["power_poll_interval_s"], "power interval", .01))
    require(gap <= allowed, "raw power samples exceed gap threshold")
    _equal_number(item["max_sample_gap_s"], gap, "power sample gap")
    _equal_number(item["max_allowed_sample_gap_s"], allowed, "power gap threshold")
    _equal_number(power["sampled_board_energy_j"], energy, "sampled power integral")
    _equal_number(power["average_board_power_w"], energy/duration, "sampled average power")


def _benchmark(result, identity):
    if result is None:
        return dict(present=False, verified_complete=False)
    require(result["original_ffn_guard_passed"] is True and result.get("physical_PPA") is None, "benchmark FFN/PPA boundary differs")
    require(result.get("attention_config") == identity["config"], "benchmark config differs from quality identity")
    provenance = result.get("model_provenance", {})
    require((provenance.get("model"), provenance.get("revision"), provenance.get("source_commit")) ==
            (MODEL, REVISION, identity["execution"]["commit"]), "benchmark model/source identity differs")
    trials = {}
    for row in result["trials"]:
        key = (row["context_tokens"], row["decode_steps"], row["mode"], row["repeat"])
        require(key not in trials, "duplicate benchmark trial")
        for phase in ("prefill", "decode"):
            for field in ("wall_seconds", "cuda_event_seconds", "tokens_per_wall_second"):
                require(_number(row[phase][field], "benchmark timing", 0) > 0, "zero benchmark timing")
        trials[key] = row
    expected = {(c, d, m, r) for c in result["contexts"] for d in result["decode_lengths"]
                for m in result["modes"] for r in range(result["measured_repeats"])}
    require(set(trials) == expected, "benchmark trial matrix incomplete")
    summaries, seen = [], set()
    for saved in result["summaries"]:
        key = (saved["context_tokens"], saved["decode_steps"], saved["mode"])
        require(key not in seen, "duplicate benchmark summary")
        seen.add(key)
        selected = [row for k, row in trials.items() if k[:3] == key]
        require(selected, "benchmark summary has no trials")
        output = dict(context_tokens=key[0], decode_steps=key[1], mode=key[2])
        for phase in ("prefill", "decode"):
            values = {field: statistics.median(r[phase][field] for r in selected)
                      for field in ("wall_seconds", "cuda_event_seconds", "tokens_per_wall_second")}
            for field, value in values.items():
                _equal_number(saved[phase][field], value, "benchmark median")
            power = saved[phase].get("power")
            require((power is None) == any(row[phase].get("power") is None for row in selected), "power summary drops/invents available estimates")
            if power is not None:
                for row in selected:
                    _verify_power(row[phase])
                for field in ("sampled_board_energy_j", "average_board_power_w"):
                    _equal_number(power[field], statistics.median(_number(r[phase]["power"][field], "board telemetry", 0) for r in selected), "power median")
            values.update(power=power, power_scope="GPU board sampled estimate; not isolated dynamic/ASIC energy",
                sensor_semantics="recent GPU NVML GetPowerUsage is 1s averaged; polling is not sensor resolution",
                phase_energy_attribution_validated=False,
                power_unavailable_reasons=saved[phase].get("power_unavailable_reasons", []))
            output[phase] = values
        summaries.append(output)
    require(seen == {k[:3] for k in expected}, "benchmark summaries incomplete")
    ratios = []
    for c in result["contexts"]:
        for d in result["decode_lengths"]:
            rows = {r["mode"]:r for r in summaries if (r["context_tokens"],r["decode_steps"]) == (c,d)}
            if {"dense", "sparq"} <= set(rows):
                ratios.append(dict(context_tokens=c, decode_steps=d,
                    dense_over_sparq_decode_wall=rows["dense"]["decode"]["wall_seconds"]/rows["sparq"]["decode"]["wall_seconds"]))
    power_reason = result.get("nvml_unavailable_reason")
    files = identity["execution"]["files"]
    known_prefix_bug = (files.get("qwen3/sparq/run.py") == "062014149221ee535c542bde5edd78ccc0df1340c8336c19210893a7eb17f484"
        and files.get("qwen3/sparq/benchmark.py") == "914183ca600c60ed5ce62ec031b4a58be64ff2ff923f9e90c0a9c8276f0bcad9"
        and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", result.get("torch_device_uuid", ""))
        and power_reason == "requested GPU UUID does not match torch model device UUID; no index fallback")
    interpretation = ("本次已核源码调用方传入裸 UUID，而采样器要求 GPU- 前缀，导致采样未启用；不是另一块 GPU 或 NVML 缺失的证据。"
                      if known_prefix_bug else power_reason)
    return dict(present=True, verified_complete=True, gpu_name=result["gpu_name"], gpu_uuid=result.get("torch_device_uuid"),
        nvml_unavailable_reason_raw=power_reason, power_unavailable_interpretation=interpretation,
        summaries=summaries, paired_ratios=ratios,
        scope="actual full-model Python reference GPU timing, original FFN; not optimized sparse-kernel speedup", physical_asic_ppa=None)


def _formal_gate_passed(identity, gates):
    return gates["preflight"]["passed"] and (identity.get("document_batch") == 1 or gates["document_batch_gate"]["passed"])


def review(root, *, source_root=None):
    root = Path(root).resolve(strict=True)
    source_root = Path(source_root).resolve(strict=True) if source_root is not None else None
    identity = _load(root/"IDENTITY.json")
    identity_report = _identity(identity, source_root)
    artifacts, integrity = _load_artifacts(root, identity)
    count = _source_count(artifacts, identity)
    plan = full_plan(count) if count is not None else None
    ppl, tasks = _ppl(artifacts, identity, plan), _tasks(artifacts, identity)
    anchor, benchmark = _anchor(artifacts, plan), _benchmark(artifacts.get("benchmark"), identity)
    summary = artifacts.get("SUMMARY")
    component_complete = (all(r["verified_complete"] for r in ppl["modes"].values()) and
        all(r["verified_complete"] for task in tasks.values() for r in task["modes"].values()) and
        anchor["verified_complete"] and benchmark["verified_complete"])
    if summary is not None:
        require(summary.get("complete") is True and (summary.get("model"),summary.get("revision")) == (MODEL,REVISION), "bad final SUMMARY identity")
        require(summary.get("physical_asic_ppa") is None, "SUMMARY invents ASIC PPA")
        if component_complete:
            _equal_number(summary["anchor"], anchor["perplexity"], "SUMMARY anchor")
            for mode in ("dense", "sparq"):
                _equal_number(summary["ppl"][mode], ppl["modes"][mode]["perplexity"], "SUMMARY PPL")
                for name in TASKS:
                    require(summary["tasks"][name][mode] == artifacts[f"task_{name}_{mode}"], "SUMMARY task differs from final task file")
    gates = {name: dict(present=name in artifacts, passed=artifacts.get(name, {}).get("passed") is True)
             for name in ("preflight", "document_batch_gate")}
    gates["document_batch_gate"].update(optional_diagnostic=identity.get("document_batch") == 1,
        reported_failures=artifacts.get("document_batch_gate", {}).get("failures", []),
        scope="candidate cross-document batching; rejection does not invalidate formal serial-document evaluation")
    production_gate = _formal_gate_passed(identity, gates)
    complete = summary is not None and component_complete and production_gate
    result = dict(schema=1, status="complete_verified" if complete else "partial_verified", complete=complete,
        input_root=str(root), identity=identity_report, integrity=integrity,
        source_tokens=count, expected_ppl_windows=len(plan) if plan else None,
        expected_ppl_targets=count-1 if count is not None else None,
        final_SUMMARY_present=summary is not None, components_complete=component_complete,
        gates=gates, formal_task_document_batch=identity.get("document_batch"),
        ppl=ppl, vectorized_anchor=anchor, tasks=tasks, benchmark=benchmark,
        hardware=dict(physical_asic_area=None, physical_asic_power=None, physical_asic_speed=None),
        limitations=["smoke/preflight scores excluded from full metrics", "partial metrics apply only to verified downloaded subsets",
            "task labels/choice character lengths absent: official row metrics aggregated, not independently regenerated",
            "source SHA registration does not rehash model weights", "GPU telemetry and Python latency are not ASIC PPA"],
        reporter_sha256=sha(__file__))
    json.dumps(result, allow_nan=False)
    return result


def markdown(report):
    title = "完整结果已核验" if report["complete"] else "部分结果已核验，完整任务尚未确认"
    identity, integrity = report["identity"], report["integrity"]
    lines = [f"# SparQ / Qwen3-4B：{title}", "",
        f"模型：`{identity['model']}` 后训练版；revision `{identity['revision']}`。原 FFN 保留。",
        f"执行提交：`{identity['source_commit']}`。已逐 envelope 验证 {integrity['envelope_count']} 个结果；下载清单字节散列核验 {integrity['downloaded_file_hashes_verified']} 个文件。",
        f"源码实际字节复核：{'已完成' if identity['local_source_bytes_verified'] else '未提供源码快照，仅核身份中登记及结果引用的 SHA 一致'}；本次未重新散列模型权重。", "",
        f"全局 SUMMARY：{'存在' if report['final_SUMMARY_present'] else '尚未下载/生成'}。仅在 SUMMARY、全部部件及正式门禁均核验后标为 complete。",
        f"正式任务 document_batch={report['formal_task_document_batch']}；preflight passed={report['gates']['preflight']['passed']}。候选跨题 batching 诊断 present={report['gates']['document_batch_gate']['present']}、passed={report['gates']['document_batch_gate']['passed']}；其负结果不等于正式串行任务失败。", "",
        f"候选诊断记录的失败项：{json.dumps(report['gates']['document_batch_gate']['reported_failures'], ensure_ascii=False)}。", "",
        "## PPL（cached 配对；smoke 不计入）", "",
        f"实际源 token 数：{report['source_tokens']}；按 2048/1024 重建 {report['expected_ppl_windows']} 个 window，完整目标数 N−1={report['expected_ppl_targets']}。", "",
        "| 模式 | 已验 window / 总数 | 连续前缀 | 已验目标 | 子集 PPL | 本项完整 |", "|---|---:|---:|---:|---:|---|"]
    def num(value):
        return "待定" if value is None else f"{value:.6g}"
    for mode, row in report["ppl"]["modes"].items():
        lines.append(f"| {mode} | {row['verified_windows']} / {row['expected_windows']} | {row['contiguous_prefix_windows']} | {row['scored_tokens']} | {num(row['perplexity'])} | {row['verified_complete']} |")
    paired = report["ppl"]["paired_verified_subset"]
    lines += ["", f"两模式共同核验 {paired['windows']} 个 window；平均 NLL 差（SparQ−dense）={num(paired['delta_mean_nll'])}。未完整时不可称全 WT2 PPL。",
        f"向量化 BF16 anchor 单独统计：{report['vectorized_anchor']['verified_windows']} 个 window，PPL={num(report['vectorized_anchor']['perplexity'])}；执行形状不同。", "",
        "## 官方任务逐行分数复核", "", "以下准确率由保存的官方逐行 acc / acc_norm 重新聚合。制品没有 gold 标签与选项字符长度，不能声称独立重做官方判题；没有用 token 数冒充 acc_norm 分母。", "",
        "| 任务 | dense 文档 | SparQ 文档 | 两者共同 | Δacc pp | Δacc_norm pp |", "|---|---:|---:|---:|---:|---:|"]
    flip_lines = []
    for name, task in report["tasks"].items():
        a, b, pair = task["modes"]["dense"], task["modes"]["sparq"], task["paired_verified_subset"]
        lines.append(f"| {name} | {a['verified_documents']}/{a['expected_documents']} | {b['verified_documents']}/{b['expected_documents']} | {pair['documents']} | {num(pair['metrics']['acc']['delta_percentage_points'])} | {num(pair['metrics']['acc_norm']['delta_percentage_points'])} |")
        for key in ("acc", "acc_norm"):
            flips = pair["metrics"][key]
            flip_lines.append(f"\n{name} {key}：dense对→SparQ错 {flips['dense_correct_sparq_wrong']}；dense错→SparQ对 {flips['dense_wrong_sparq_correct']}。dense={num(a['metrics_from_official_rows'][key])}，SparQ={num(b['metrics_from_official_rows'][key])}（各自已验子集）。")
    lines.extend(flip_lines)
    lines += ["", "## 稀疏路径覆盖", "", "以下按各层 KV group 的实际逻辑计数汇总；逐层数值见 JSON。短任务上下文落在完整预算内时会 dense fallback，不能把这些分数当成稀疏路径质量证据。"]
    for label, row in [("PPL", report["ppl"]["modes"]["sparq"])] + [(n,t["modes"]["sparq"]) for n,t in report["tasks"].items()]:
        audit = row["attention"]
        lines.append(f"\n{label}：sparse/query group 比例={num(audit['sparse_group_fraction'])}；计数={json.dumps(audit['totals'], ensure_ascii=False)}。")
    lines += ["", "## GPU 实测与硬件边界", ""]
    bench = report["benchmark"]
    if not bench["present"]:
        lines.append("完整 benchmark envelope 尚未下载/生成；不从 progress 或参数估计补造速度、功率。")
    else:
        lines += [f"GPU：{bench['gpu_name']}，UUID `{bench['gpu_uuid']}`。完整模型、原 FFN、Python 数值参考的实际计时；不代表优化稀疏 kernel。", "",
            f"功率采样状态：{bench['power_unavailable_interpretation'] or '按各阶段采样覆盖门禁判定；见 JSON'}", "",
            "| 上下文 | decode步数 | 模式 | prefill秒 | decode秒 | decode token/s | 板级估计J（decode） |", "|---|---:|---|---:|---:|---:|---:|"]
        for row in bench["summaries"]:
            power = row["decode"]["power"]
            lines.append(f"| {row['context_tokens']} | {row['decode_steps']} | {row['mode']} | {num(row['prefill']['wall_seconds'])} | {num(row['decode']['wall_seconds'])} | {num(row['decode']['tokens_per_wall_second'])} | {num(power['sampled_board_energy_j'] if power else None)} |")
        lines.append("\n功率为 GPU 板级采样估计，较新 GPU 的 NVML 值有 1 秒平均；短窗口/缺采样返回 null。没有验证隔离的阶段能量归因，不能称 ASIC 动态能耗。")
    lines += ["", "物理 ASIC 面积、功率与速度均为 null；不得与 GPU 结果或逻辑访问账本混称。", ""]
    return "\n".join(lines)


def _self_test():
    import tempfile
    import unittest
    import sys

    identity = dict(config=dict(r=32,k_total=128,local_total=32,reallocation=False,
        selection="probability_sum",validate_finite=False), ppl=dict(context=2048,stride=1024,batch=32,chunk=1),
        tokens_sha256="a"*64, task_chunk=2, document_batch=1, choice_batch=4)

    def audit(mode, queries):
        layers = {}
        for index in range(36):
            counts = dict(query_groups=8*queries, sparse_groups=4*queries, dense_groups=4*queries,
                          full_budget_groups=4*queries, zero_coverage_groups=0)
            layers[str(index)] = dict(decode_query_tokens=queries, head_rows=32*queries, decode_calls=1,
                diagnostics={"logical_counts."+k:v for k,v in counts.items()} if mode == "sparq" else {})
        return dict(installed_layers=36,every_scored_predictor_executed_all_layers=True,
            calls=dict(decode=1,prefill=0), tokens_per_layer={phase:dict(attention=[value]*36,ffn=[value]*36)
                for phase,value in (("decode",queries),("prefill",0))},
            replacement=dict(mode=mode,installed_layers=36,layers=layers,config=identity["config"]))

    def ppl_part(mode, row, plan):
        expected = [{k:row[k] for k in PLAN_KEYS}]
        return dict(mode=mode,scope="partial_segments",complete=False,ffn="none",ffn_config=None,
            records=[row], **_nll([row]),token_ids_sha256_le_int64=identity["tokens_sha256"],
            scoring_parameters=dict(protocol="full",context=2048,stride=1024,batch=32,segment_start=row["segment_id"],segment_count=1),
            scoring_plan=dict(smoke_limit=None,segments=expected,requested_segments=len(plan),
                target_positions_sha256_le_int64=_positions_hash(expected),scored_tokens=row["scored_tokens"]),
            execution_audit=audit(mode,row["scored_tokens"]))

    def task_part(mode, count=2):
        rows = []
        for i in range(count):
            correct = int((i % 2 == 0) == (mode == "dense"))
            rows.append(dict(id=f"piqa:{i}",task="piqa",doc_id=i,
                choices=[dict(tokens=1,logprob=-float(correct),is_greedy=False),
                         dict(tokens=1,logprob=-float(1-correct),is_greedy=False)],
                metrics=dict(acc=correct,acc_norm=int(i % 2 == 1 or mode == "sparq"))))
        return dict(mode=mode,shard_complete=True,complete=False,shard_start=0,smoke_limit=None,
            test="qwen3_sparq_official_mc_likelihood",choice_batch=4,full_task_documents=1838,
            documents=rows,evaluated_documents=count,requested_documents=count,
            choice_target_scores=2*count,shared_first_target_reuses=count,
            execution_audit=audit(mode,count),ffn="none",ffn_config=None)

    class Tests(unittest.TestCase):
        def test_actual_plan_tail_and_denominator(self):
            for n in (2048, 2049, 298000, 300000):
                rows = full_plan(n)
                self.assertEqual(sum(r["scored_tokens"] for r in rows), n-1)
                self.assertEqual(rows[-1]["end"], n)
                self.assertEqual([p for r in rows for p in range(r["first_target"], r["end"])], list(range(1,n)))
            self.assertEqual((len(full_plan(298000)), len(full_plan(300000))), (291, 292))

        def test_wrong_window_and_target_hash_fail(self):
            plan = full_plan(3000)
            row = dict(plan[0], nll_sum=1., target_positions_sha256_le_int64=_positions_hash([plan[0]]))
            _check_rows([row], plan, "fixture")
            row["first_target"] = 2
            with self.assertRaises(AuditError):
                _check_rows([row], plan, "fixture")

        def test_partial_ppl_pair_then_complete_parts_and_final(self):
            plan, artifacts = full_plan(3000), {}
            rows = [dict(row,nll_sum=2.*row["scored_tokens"],target_positions_sha256_le_int64=_positions_hash([row])) for row in plan]
            for mode in ("dense", "sparq"):
                artifacts[f"ppl_parts/{mode}_0000"] = ppl_part(mode,rows[0],plan)
            partial = _ppl(artifacts,identity,plan)
            self.assertEqual(partial["paired_verified_subset"]["windows"], 1)
            self.assertFalse(partial["modes"]["dense"]["verified_complete"])
            self.assertEqual(partial["modes"]["sparq"]["attention"]["sparse_group_fraction"], .5)
            for mode in ("dense", "sparq"):
                artifacts[f"ppl_parts/{mode}_0001"] = ppl_part(mode,rows[1],plan)
                artifacts["ppl_"+mode] = dict(complete=True,mode=mode,source_tokens=3000,
                    token_ids_sha256=identity["tokens_sha256"],records=rows,**_nll(rows),
                    part_names=[f"ppl_parts/{mode}_{i:04d}" for i in range(2)],
                    original_ffn=True,all_scored_predictors_single_query_all_layers=True)
            complete = _ppl(artifacts,identity,plan)
            self.assertTrue(complete["modes"]["dense"]["verified_complete"])
            self.assertEqual(complete["modes"]["sparq"]["scored_tokens"], 2999)
            artifacts["ppl_dense"]["perplexity"] += .1
            with self.assertRaises(AuditError):
                _ppl(artifacts,identity,plan)

        def test_task_partial_pairs_ids_and_per_layer_groups(self):
            artifacts = {f"task_parts/piqa_{m}_00000":task_part(m) for m in ("dense","sparq")}
            report = _tasks(artifacts,identity)["piqa"]
            pair = report["paired_verified_subset"]
            self.assertEqual(pair["documents"],2)
            self.assertEqual(pair["raw_prediction_flips"],2)
            self.assertEqual(pair["metrics"]["acc"]["dense_correct_sparq_wrong"],1)
            self.assertEqual(pair["metrics"]["acc"]["dense_wrong_sparq_correct"],1)
            self.assertEqual(pair["metrics"]["acc_norm"]["delta_percentage_points"],50)
            self.assertEqual(report["modes"]["sparq"]["attention"]["totals"]["query_groups"],36*2*8)
            artifacts["task_parts/piqa_dense_00000"]["documents"][1]["id"] = "piqa:99"
            with self.assertRaises(AuditError):
                _tasks(artifacts,identity)

        def test_task_full_summary_recomputed_from_every_row(self):
            actual_identity = dict(identity,task_chunk=1838)
            part = task_part("dense",1838)
            metrics = _task_metrics(part["documents"])
            final = dict(task="piqa",mode="dense",complete=True,documents=1838,original_ffn=True,
                source_parts=["task_parts/piqa_dense_00000"],metrics=metrics,
                binomial_standard_error={k:math.sqrt(v*(1-v)/1838) for k,v in metrics.items()})
            artifacts = {"task_parts/piqa_dense_00000":part,"task_piqa_dense":final}
            self.assertTrue(_tasks(artifacts,actual_identity)["piqa"]["modes"]["dense"]["verified_complete"])
            final["metrics"]["acc"] = .99
            with self.assertRaises(AuditError):
                _tasks(artifacts,actual_identity)

        def test_rejected_optional_batching_not_formal_serial_failure(self):
            gates = dict(preflight=dict(passed=True),document_batch_gate=dict(passed=False))
            self.assertTrue(_formal_gate_passed(dict(document_batch=1),gates))
            self.assertFalse(_formal_gate_passed(dict(document_batch=8),gates))
            gates["preflight"]["passed"] = False
            self.assertFalse(_formal_gate_passed(dict(document_batch=1),gates))

        def test_power_recomputed_and_missing_gap_rejected(self):
            item = dict(wall_seconds=2.,phase_energy_attribution_validated=False,power_poll_interval_s=.02,
                power_samples_relative_s_w=[(i/10,20.) for i in range(-1,22)],
                max_sample_gap_s=.1,max_allowed_sample_gap_s=.25,
                power=dict(sampled_board_energy_j=40.,average_board_power_w=20.))
            _verify_power(item)
            item["power_samples_relative_s_w"] = [(-.1,20.),(.1,20.),(1.9,20.),(2.1,20.)]
            with self.assertRaises(AuditError):
                _verify_power(item)

        def test_tamper_and_cross_experiment_fail(self):
            with tempfile.TemporaryDirectory(prefix="report_test_", dir=Path(__file__).parent) as temp:
                root = Path(temp)
                identity = {"execution":{"files":{}}}
                (root/"IDENTITY.json").write_text(json.dumps(identity), encoding="utf-8")
                value = dict(experiment=fingerprint(identity), result={"x":1}, result_sha256=fingerprint({"x":1}))
                path = root/"preflight.json"
                path.write_text(json.dumps(value), encoding="utf-8")
                self.assertEqual(_load_artifacts(root, identity)[1]["envelope_count"], 1)
                value["result"]["x"] = 2
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(AuditError):
                    _load_artifacts(root, identity)
                value["result_sha256"] = fingerprint(value["result"])
                value["experiment"] = "0"*64
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(AuditError):
                    _load_artifacts(root, identity)

        def test_official_metric_aggregation_not_token_norm(self):
            rows = [dict(metrics=dict(acc=1, acc_norm=0)), dict(metrics=dict(acc=0, acc_norm=1)), dict(metrics=dict(acc=1, acc_norm=1))]
            self.assertEqual(_task_metrics(rows), dict(acc=2/3, acc_norm=2/3))
            self.assertNotIn("torch", sys.modules)

        def test_duplicate_json_keys_fail(self):
            with tempfile.TemporaryDirectory(prefix="report_test_", dir=Path(__file__).parent) as temp:
                path = Path(temp)/"bad.json"
                path.write_text('{"a":1,"a":2}', encoding="utf-8")
                with self.assertRaises(AuditError):
                    _load(path)

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not result.wasSuccessful():
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="?")
    parser.add_argument("--output")
    parser.add_argument("--source-root")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        _self_test()
        return
    if not args.results or not args.output:
        parser.error("results and --output are required")
    source = Path(args.results).resolve(strict=True)
    destination = Path(args.output).resolve()
    require(not destination.is_relative_to(source), "report output must be outside immutable input results")
    result = review(source, source_root=args.source_root)
    outputs = (("REVIEW.json", json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n"),
               ("REVIEW_ZH.md", markdown(result)))
    for name, _ in outputs:
        require(not (destination/name).exists(), f"refusing to overwrite prior review: {destination/name}")
    destination.mkdir(parents=True, exist_ok=True)
    for name, text in outputs:
        path = destination/name
        path.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps(dict(status=result["status"], verified_envelopes=result["integrity"]["envelope_count"],
                          output=str(destination)), ensure_ascii=False))


if __name__ == "__main__":
    main()
