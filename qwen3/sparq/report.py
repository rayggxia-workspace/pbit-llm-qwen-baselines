"""Offline Issue157 artifact verification/reporting; standard library only.

python -m qwen3.sparq.report RESULTS_DIR --output REPORT_DIR [--source-root SNAPSHOT]
python -m qwen3.sparq.report SUPPLEMENT_DIR --supplement --source-root BUNDLE --parent-results RESULTS_DIR --output REPORT_DIR
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
# Issue157's declared run.py/benchmark.py protocol, independent of result claims.
BENCHMARK_CONTEXTS = (128, 512, 2048)
BENCHMARK_DECODE_LENGTHS = (64, 128)
BENCHMARK_MODES = ("native", "dense", "sparq")
BENCHMARK_REPEATS = 3
BENCHMARK_WARMUP = 1
BENCHMARK_BATCH = 1
SUPPLEMENT_SOURCES = {"qwen3/sparq/"+name for name in (
    "bench_only.py", "benchmark.py", "core.py", "adapter.py", "run.py", "scoring.py", "task_data.py",
    "batch_scoring.py", "SOURCES.json", "model_identity.json", "test_bench_only.py", "BENCH_ONLY_ZH.md")}
SUPPLEMENT_SOURCES.add("qwen3/stochastic/vendor/scoring.py")
UNCHANGED_NUMERICS = {"qwen3/sparq/core.py", "qwen3/sparq/adapter.py", "qwen3/stochastic/vendor/scoring.py"}
SUPPLEMENT_MODEL_FILES = {"config.json", "generation_config.json", "merges.txt", "model-00001-of-00003.safetensors",
    "model-00002-of-00003.safetensors", "model-00003-of-00003.safetensors", "model.safetensors.index.json",
    "tokenizer.json", "tokenizer_config.json", "vocab.json"}


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


def _benchmark(result, identity, *, supplement=False):
    if result is None:
        return dict(present=False, verified_complete=False)
    require(result["original_ffn_guard_passed"] is True and result.get("physical_PPA") is None, "benchmark FFN/PPA boundary differs")
    require(result.get("attention_config") == identity["config"], "benchmark config differs from quality identity")
    provenance = result.get("model_provenance", {})
    execution = identity["measuring_execution"] if supplement else identity["execution"]
    source_key = "measuring_source_commit" if supplement else "source_commit"
    require((provenance.get("model"), provenance.get("revision"), provenance.get(source_key)) ==
            (MODEL, REVISION, execution["commit"]), "benchmark model/source identity differs")
    if supplement:
        require(provenance.get("role") == "measurement_supplement" and
                provenance.get("parent_quality_source_commit") == identity["parent"]["quality_source_commit"] and
                provenance.get("parent_identity_sha256") == identity["parent"]["identity_sha256"] and
                provenance.get("job") == identity["job"], "supplement benchmark parent/job provenance differs")
    require(result.get("test") == "qwen3_sparq_real_model_reference_benchmark" and
            _int(result.get("schema"), "benchmark schema") == 1, "unsupported benchmark schema")
    for field, declared in (("contexts", BENCHMARK_CONTEXTS), ("decode_lengths", BENCHMARK_DECODE_LENGTHS),
                            ("modes", BENCHMARK_MODES)):
        require(result.get(field) == list(declared), f"benchmark {field} differs from fixed Issue157 protocol")
        if field != "modes":
            for value in result[field]:
                _int(value, f"benchmark {field}", 1)
    require(_int(result.get("measured_repeats"), "benchmark repeats", 1) == BENCHMARK_REPEATS and
            _int(result.get("warmup_trials_per_case_mode"), "benchmark warmup", 1) == BENCHMARK_WARMUP,
            "benchmark repeat/warmup count differs from fixed Issue157 protocol")
    shape = result.get("token_ids_shape")
    require(isinstance(shape, list) and len(shape) == 2, "invalid benchmark token shape")
    require(_int(shape[0], "benchmark batch", 1) == BENCHMARK_BATCH and
            _int(shape[1], "benchmark sequence length", 1) >= max(BENCHMARK_CONTEXTS)+max(BENCHMARK_DECODE_LENGTHS),
            "benchmark token shape does not cover fixed Issue157 protocol")
    expected = {(c, d, m, r) for c in BENCHMARK_CONTEXTS for d in BENCHMARK_DECODE_LENGTHS
                for m in BENCHMARK_MODES for r in range(BENCHMARK_REPEATS)}
    trials = {}
    for row in result["trials"]:
        context = _int(row["context_tokens"], "benchmark context", 1)
        decode = _int(row["decode_steps"], "benchmark decode steps", 1)
        key = (context, decode, row["mode"], _int(row["repeat"], "benchmark repeat"))
        require(key in expected, "unexpected benchmark trial")
        require(key not in trials, "duplicate benchmark trial")
        require(_int(row["batch"], "trial batch", 1) == shape[0], "trial batch differs from token shape")
        require(_int(row["first_decode_cache_tokens"], "first decode cache tokens", 1) == context+1 and
                _int(row["last_decode_cache_tokens"], "last decode cache tokens", 1) == context+decode,
                "benchmark declared cache bounds differ")
        require(row.get("last_decode_logits_finite") is True, "benchmark finite-output gate did not pass")
        for phase, steps in (("prefill", context), ("decode", decode)):
            for field in ("wall_seconds", "cuda_event_seconds", "tokens_per_wall_second"):
                require(_number(row[phase][field], "benchmark timing", 0) > 0, "zero benchmark timing")
            tokens = shape[0]*steps
            require(_int(row[phase]["input_tokens"], "phase input tokens", 1) == tokens, "benchmark phase token count differs")
            _equal_number(row[phase]["tokens_per_wall_second"], tokens/row[phase]["wall_seconds"], "benchmark tokens/wall time")
        _equal_number(row["decode"]["wall_seconds_per_decode_step"], row["decode"]["wall_seconds"]/decode,
                      "benchmark decode step time")
        trials[key] = row
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
    for c in BENCHMARK_CONTEXTS:
        for d in BENCHMARK_DECODE_LENGTHS:
            rows = {r["mode"]:r for r in summaries if (r["context_tokens"],r["decode_steps"]) == (c,d)}
            if {"dense", "sparq"} <= set(rows):
                ratios.append(dict(context_tokens=c, decode_steps=d,
                    dense_over_sparq_decode_wall=rows["dense"]["decode"]["wall_seconds"]/rows["sparq"]["decode"]["wall_seconds"]))
    power_reason = result.get("nvml_unavailable_reason")
    files = execution["files"]
    known_prefix_bug = (files.get("qwen3/sparq/run.py") == "062014149221ee535c542bde5edd78ccc0df1340c8336c19210893a7eb17f484"
        and files.get("qwen3/sparq/benchmark.py") == "914183ca600c60ed5ce62ec031b4a58be64ff2ff923f9e90c0a9c8276f0bcad9"
        and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", result.get("torch_device_uuid", ""))
        and power_reason == "requested GPU UUID does not match torch model device UUID; no index fallback")
    interpretation = ("本次已核源码调用方传入裸 UUID，而采样器要求 GPU- 前缀，导致采样未启用；不是另一块 GPU 或 NVML 缺失的证据。"
                      if known_prefix_bug else power_reason)
    return dict(present=True, verified_complete=True, gpu_name=result["gpu_name"], gpu_uuid=result.get("torch_device_uuid"),
        verified_trial_count=len(trials), expected_trial_count=len(expected),
        protocol="fixed Issue157: batch1, contexts128/512/2048, decode64/128, native/dense/sparq, warmup1, repeats3",
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


def _verified_envelope(path, identity, files):
    value = _load(path)
    require(value.get("experiment") == fingerprint(identity), f"experiment identity mismatch: {path.name}")
    require(value.get("result_sha256") == fingerprint(value.get("result")), f"result hash mismatch: {path.name}")
    for record in _walk(value["result"]):
        for name, checksum in record.get("source_files_sha256", {}).items():
            require(files.get(name) == checksum, f"result source differs from identity: {name}")
    return value["result"], dict(file_sha256=sha(path), result_sha256=value["result_sha256"], job=value.get("job"))


def _gpu_uuid(value):
    require(isinstance(value, str), "missing GPU UUID")
    bare = value[4:] if value.startswith("GPU-") else value
    require(re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", bare), "invalid GPU UUID")
    return "GPU-"+bare.lower()


def review_benchmark_supplement(root, source_root, *, parent_results):
    """Verify separate measurement artifacts; never inherit quality completion.

    The caller must provide the actual parent IDENTITY bytes and frozen measuring
    bundle. This checks hashes and consistency, not authorship or checkpoint bytes.
    Missing completion files return partial; inconsistent present files fail closed.
    """
    require(source_root is not None and parent_results is not None, "supplement needs source_root and parent_results")
    root, source_root, parent_results = (Path(p).resolve(strict=True) for p in (root, source_root, parent_results))
    require(not root.is_relative_to(parent_results) and not parent_results.is_relative_to(root),
            "supplement and original quality result directories must be separate")
    identity_path = _safe_child(root, "IDENTITY.json")
    identity = _load(identity_path)
    require(identity.get("kind") == "benchmark_supplement", "not a benchmark supplement identity")
    require(identity.get("quality_evaluation_performed") is False and
            identity.get("original_quality_results_inherited") is False and
            identity.get("task_datasets_revalidated") is False, "supplement claims inherited/new task evaluation")
    require((identity.get("model"), identity.get("revision"), identity.get("original_ffn")) ==
            (MODEL, REVISION, True) and identity["original_ffn"] is True, "supplement model/FFN differs")
    require(_int(identity.get("seed"), "supplement seed") == 0, "supplement seed differs")
    job = identity.get("job")
    require(isinstance(job, str) and re.fullmatch(r"[0-9]+", job), "invalid supplement job identity")
    gpu_uuid = _gpu_uuid(identity.get("gpu_uuid"))
    schedule = dict(contexts=list(BENCHMARK_CONTEXTS), decode_lengths=list(BENCHMARK_DECODE_LENGTHS),
        modes=list(BENCHMARK_MODES), warmup=BENCHMARK_WARMUP, repeats=BENCHMARK_REPEATS, power_interval_s=.02)
    require(fingerprint(identity.get("benchmark_schedule")) == fingerprint(schedule), "supplement schedule differs")
    execution = identity["measuring_execution"]
    require(execution == _load(_safe_child(source_root, "EXECUTION.json")), "bundle EXECUTION differs from supplement identity")
    require(execution.get("repo") == "rayggxia-workspace/pbit-llm-qwen-baselines" and
            execution.get("purpose") == "benchmark_supplement" and type(execution.get("schema")) is int and
            execution["schema"] == 1, "invalid supplement source manifest")
    _hash(execution.get("commit"), "measuring source commit", 40)
    files = execution["files"]
    require(set(files) == SUPPLEMENT_SOURCES, "supplement source closure differs")
    for name, checksum in files.items():
        _hash(checksum, name)
        path = _safe_child(source_root, name)
        require(path.is_file() and sha(path) == checksum, f"supplement source bytes differ: {name}")

    parent_path = _safe_child(parent_results, "IDENTITY.json")
    parent = _load(parent_path)
    parent_identity = _identity(parent, None)
    link = identity["parent"]
    require(link.get("identity_sha256") == sha(parent_path) and
            link.get("identity_fingerprint") == fingerprint(parent) and
            link.get("quality_source_commit") == parent["execution"]["commit"], "parent IDENTITY raw hash/fingerprint/source differs")
    require(identity["ready_sha256"] == parent["ready_sha256"] and identity["tokens_sha256"] == parent["tokens_sha256"] and
            identity["environment"] == parent["environment"] and
            fingerprint(identity["config"]) == fingerprint(parent["config"]) and
            identity["config"]["validate_finite"] is False and parent.get("seed") == 0,
            "supplement parent inputs/config/environment differ")
    for name in UNCHANGED_NUMERICS:
        require(files[name] == parent["execution"]["files"].get(name), f"supplement numerical dependency changed: {name}")
    parent_receipts = {}
    for name in ("preflight", "benchmark"):
        path = _safe_child(parent_results, name+".json")
        require(sha(path) == link.get(name+"_artifact_sha256"), f"parent {name} raw hash differs")
        value, parent_receipts[name] = _verified_envelope(path, parent, parent["execution"]["files"])
        if name == "preflight":
            require(value.get("passed") is True, "parent preflight did not pass")
        else:
            original_benchmark = value
            require(value.get("source_files_sha256") == {"qwen3/sparq/"+n:parent["execution"]["files"].get("qwen3/sparq/"+n)
                for n in ("benchmark.py","adapter.py","core.py")}, "parent benchmark source references differ")
            _hash(value.get("token_ids_shape_and_le_int64_sha256"), "parent benchmark token/shape fingerprint")
            _benchmark(value, parent)
    model_files = identity["verified_model_files"]
    require(len(model_files) == 10 and {r["name"] for r in model_files} == SUPPLEMENT_MODEL_FILES,
            "supplement model-file receipt differs")
    for row in model_files:
        _int(row["bytes"], "recorded model file bytes", 1)
        _hash(row["sha256"], "recorded model file")
    _hash(identity["verified_corpus_sha256"], "recorded corpus")

    artifact_path = _safe_child(root, "benchmark_supplement.json")
    benchmark, receipts, completed = dict(present=False, verified_complete=False), {}, None
    power_windows, phase_windows = 0, 0
    if artifact_path.exists():
        completed, receipts[artifact_path.name] = _verified_envelope(artifact_path, identity, files)
        require(receipts[artifact_path.name]["job"] == job, "supplement envelope job differs")
        require(completed.get("measurement_complete") is True and completed.get("quality_evaluation_complete") is False and
                completed.get("physical_asic_ppa") is None and completed.get("parent") == link and
                completed.get("measuring_source_commit") == execution["commit"], "supplement completion scope/source differs")
        measured = completed["benchmark"]
        required_hashes = {"qwen3/sparq/"+n:files["qwen3/sparq/"+n] for n in ("benchmark.py","adapter.py","core.py")}
        require(measured.get("source_files_sha256") == required_hashes, "supplement benchmark source references differ")
        require(measured.get("token_ids_shape") == original_benchmark["token_ids_shape"] and
                measured.get("token_ids_shape_and_le_int64_sha256") == original_benchmark["token_ids_shape_and_le_int64_sha256"],
                "supplement benchmark input token/shape fingerprint differs")
        require(_gpu_uuid(measured.get("torch_device_uuid")) == gpu_uuid and
                measured.get("gpu_name") == identity["gpu_name"], "supplement measured GPU differs")
        require(measured.get("torch_version") == identity["environment"]["torch"] and
                measured.get("parameter_dtypes") == ["torch.bfloat16"], "supplement measured runtime/dtype differs")
        benchmark = _benchmark(measured, identity, supplement=True)
        for row in measured["trials"]:
            for phase in ("prefill", "decode"):
                item = row[phase]
                phase_windows += 1
                require(item.get("phase_energy_attribution_validated") is False, "supplement overclaims phase power attribution")
                _equal_number(item["power_poll_interval_s"], schedule["power_interval_s"], "supplement power interval")
                if item.get("power") is not None:
                    # Verify even when another repeat's null makes the median null.
                    require(item.get("power_unavailable_reason") is None, "available power also claims unavailable")
                    _verify_power(item)
                    power_windows += 1
                else:
                    require(isinstance(item.get("power_unavailable_reason"), str) and item["power_unavailable_reason"],
                            "null power lacks reason")
        if measured.get("nvml_gpu_uuid") is not None:
            require(_gpu_uuid(measured["nvml_gpu_uuid"]) == gpu_uuid, "supplement NVML GPU attribution differs")
        if power_windows:
            require(measured.get("nvml_unavailable_reason") is None and measured.get("nvml_gpu_uuid") is not None,
                    "supplement available power lacks NVML attribution")
        power_status = "sampled_board_estimates" if power_windows else "unavailable"
        require(_int(completed.get("power_windows_available"), "power window count") == power_windows and
                _int(completed.get("total_phase_windows"), "phase window count") == phase_windows == 108 and
                completed.get("power_status") == power_status, "supplement power coverage/status differs")

    producer_path, sidecar_path = _safe_child(root, "report.json"), _safe_child(root, "report.sha256.json")
    transfer_hashes, producer_verified = {}, False
    if producer_path.exists() and sidecar_path.exists():
        require(completed is not None, "supplement report lacks completed benchmark envelope")
        sidecar = _load(sidecar_path)
        require(sidecar.get("file") == "report.json" and sidecar.get("sha256") == sha(producer_path), "supplement report raw hash differs")
        producer = _load(producer_path)
        expected_fields = dict(kind="benchmark_supplement_report", measurement_complete=True,
            quality_evaluation_complete=False, original_quality_results_inherited=False,
            parent=link, model=MODEL, revision=REVISION, measuring_execution=execution, job=job,
            gpu_uuid=identity["gpu_uuid"], gpu_name=identity["gpu_name"], environment=identity["environment"],
            config=identity["config"], schedule=schedule, original_ffn=True,
            ready_sha256=identity["ready_sha256"], verified_corpus_sha256=identity["verified_corpus_sha256"],
            verified_model_files=model_files, tokens_sha256=identity["tokens_sha256"],
            power_status=completed["power_status"], power_windows_available=power_windows,
            phase_energy_attribution_validated=False, physical_asic_ppa=None,
            timing_protocol=measured["timing_protocol"], scope=measured["scope"],
            nvml_gpu_uuid=measured["nvml_gpu_uuid"], nvml_unavailable_reason=measured["nvml_unavailable_reason"],
            summaries=measured["summaries"], trial_count=54)
        for name, expected in expected_fields.items():
            require(fingerprint(producer.get(name)) == fingerprint(expected), f"producer report differs: {name}")
        transfers = producer.get("transfer_artifacts", {})
        require({"IDENTITY.json", "INVOCATION.json", "benchmark_supplement.json"} <= set(transfers) <=
                {"IDENTITY.json", "INVOCATION.json", "benchmark_supplement.json", "progress.jsonl", "FAILED.json"},
                "supplement transfer manifest missing/unexpected artifacts")
        for name, record in transfers.items():
            path = _safe_child(root, name)
            require(path.is_file() and sha(path) == record["sha256"] and
                    _int(record["bytes"], "transfer bytes") == path.stat().st_size, f"supplement transfer bytes differ: {name}")
            transfer_hashes[name] = record
        require(_load(_safe_child(root, "INVOCATION.json")).get("job") == job, "supplement invocation job differs")
        producer_verified = True
    measurement_complete = benchmark["verified_complete"] and producer_verified
    result = dict(schema=1, kind="benchmark_supplement_review",
        status="measurement_complete_verified" if measurement_complete else "measurement_partial_verified",
        measurement_complete=measurement_complete, quality_evaluation_complete=False,
        original_quality_results_inherited=False, input_root=str(root),
        identity=dict(model=MODEL, revision=REVISION, original_ffn=True, config=identity["config"],
            measuring_source_commit=execution["commit"], local_source_bytes_verified=True,
            registered_source_files=len(files), source_manifest_sha256=sha(source_root/"EXECUTION.json"),
            model_weight_bytes_rehashed=False, job=job),
        parent=dict(identity_file_sha256=sha(parent_path), identity_fingerprint=fingerprint(parent),
            quality_source_commit=parent_identity["source_commit"], artifacts=parent_receipts,
            preflight_passed=True, quality_completion_not_evaluated=True),
        integrity=dict(experiment=fingerprint(identity), identity_file_sha256=sha(identity_path),
            envelopes=receipts, envelope_count=len(receipts), producer_report_verified=producer_verified,
            producer_report_sha256=sha(producer_path) if producer_verified else None,
            downloaded_file_hashes_verified=len(transfer_hashes), transfer_artifacts=transfer_hashes),
        benchmark=benchmark, power_windows_available=power_windows, total_phase_windows=phase_windows,
        phase_energy_attribution_validated=False, physical_asic_ppa=None,
        prior_failure_diagnostic_present=_safe_child(root, "FAILED.json").exists(),
        limitations=["supplement does not evaluate or inherit PPL/task completion",
            "offline verification rehashes measuring source; model/corpus byte checks are execution receipts, not repeated here",
            "GPU board sampled estimates are not isolated phase/ASIC power; null windows retain reasons",
            "hash consistency is not cryptographic authorship proof"], reporter_sha256=sha(__file__))
    json.dumps(result, allow_nan=False)
    return result


def supplement_markdown(report):
    bench, identity, parent = report["benchmark"], report["identity"], report["parent"]
    lines = ["# SparQ / Qwen3-4B：独立 benchmark 补测核验", "",
        f"测量完整：`{report['measurement_complete']}`；质量评测完整：`False`。本报告不继承或补全原 PPL / 任务结果。",
        f"测量源码：`{identity['measuring_source_commit']}`，已核 {identity['registered_source_files']} 个实际文件字节；原 FFN 保留。",
        f"原质量源码：`{parent['quality_source_commit']}`；原 IDENTITY 原始 SHA：`{parent['identity_file_sha256']}`。",
        f"核验完成 envelope {report['integrity']['envelope_count']} 个；生产报告及传输散列已核：`{report['integrity']['producer_report_verified']}`。", ""]
    if bench["present"]:
        lines += [f"GPU：{bench['gpu_name']}，UUID `{bench['gpu_uuid']}`。54 次完整模型 Python 参考运行；不是优化稀疏 kernel。",
            f"有效功率窗口：{report['power_windows_available']}/{report['total_phase_windows']}；每个非空窗口独立重积分。NVML 原因：{bench['power_unavailable_interpretation']}。", "",
            "| 上下文 | decode步数 | 模式 | prefill秒 | decode秒 | decode token/s | decode板级估计J |",
            "|---|---:|---|---:|---:|---:|---:|"]
        for row in bench["summaries"]:
            power = row["decode"]["power"]
            energy = "null" if power is None else f"{power['sampled_board_energy_j']:.6g}"
            lines.append(f"| {row['context_tokens']} | {row['decode_steps']} | {row['mode']} | {row['prefill']['wall_seconds']:.6g} | {row['decode']['wall_seconds']:.6g} | {row['decode']['tokens_per_wall_second']:.6g} | {energy} |")
    else:
        lines.append("完成的 benchmark envelope 尚未下载/生成；progress 不作为完整结果。")
    lines += ["", "NVML 为板级采样估计，近期 GPU 的传感值为约 1 秒平均；逐 phase 能量归因未验证。ASIC 面积、功率、速度均为 null。",
        "离线已重算源码和结果散列；模型/语料字节核验来自执行端 receipt，本报告未重新读取大模型权重。", ""]
    return "\n".join(lines)


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
    import copy
    import tempfile
    import unittest
    import sys
    import subprocess

    identity = dict(config=dict(r=32,k_total=128,local_total=32,reallocation=False,
        selection="probability_sum",validate_finite=False), ppl=dict(context=2048,stride=1024,batch=32,chunk=1),
        tokens_sha256="a"*64, task_chunk=2, document_batch=1, choice_batch=4,
        execution=dict(commit="b"*40, files={}))

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

    def benchmark_fixture():
        trials, summaries = [], []
        for context in BENCHMARK_CONTEXTS:
            for decode in BENCHMARK_DECODE_LENGTHS:
                for mode in BENCHMARK_MODES:
                    phases = {name:dict(wall_seconds=2., cuda_event_seconds=1.5,
                        input_tokens=steps, tokens_per_wall_second=steps/2., power=None)
                        for name, steps in (("prefill",context),("decode",decode))}
                    phases["decode"]["wall_seconds_per_decode_step"] = 2./decode
                    summaries.append(dict(context_tokens=context,decode_steps=decode,mode=mode,**copy.deepcopy(phases)))
                    for repeat in range(BENCHMARK_REPEATS):
                        trials.append(dict(context_tokens=context,decode_steps=decode,mode=mode,repeat=repeat,batch=1,
                            first_decode_cache_tokens=context+1,last_decode_cache_tokens=context+decode,
                            last_decode_logits_finite=True,**copy.deepcopy(phases)))
        return dict(test="qwen3_sparq_real_model_reference_benchmark",schema=1,
            original_ffn_guard_passed=True,physical_PPA=None,attention_config=identity["config"],
            model_provenance=dict(model=MODEL,revision=REVISION,source_commit=identity["execution"]["commit"]),
            contexts=list(BENCHMARK_CONTEXTS),decode_lengths=list(BENCHMARK_DECODE_LENGTHS),modes=list(BENCHMARK_MODES),
            measured_repeats=3,warmup_trials_per_case_mode=1,token_ids_shape=[1,3000],
            gpu_name="CPU fixture only; no GPU measurement",trials=trials,summaries=summaries)

    def supplement_fixture(directory):
        # Synthetic unit fixture only. No real measurement is rewritten/relabelled.
        directory = Path(directory)
        source, parent_root, root = (directory/name for name in ("source","parent","supplement"))
        for path in (source,parent_root,root):
            path.mkdir()
        def save(path, value):
            path.write_text(json.dumps(value,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8",newline="\n")
        files = {}
        for name in SUPPLEMENT_SOURCES:
            path = source/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(("synthetic non-executable unit source: "+name+"\n").encode())
            files[name] = sha(path)
        execution = dict(schema=1,purpose="benchmark_supplement",commit="c"*40,
            repo="rayggxia-workspace/pbit-llm-qwen-baselines",files=files)
        save(source/"EXECUTION.json", execution)
        parent = copy.deepcopy(identity)
        parent.update(model=MODEL,revision=REVISION,original_ffn=True,seed=0,
            tasks={n:dict(documents=c,split=s,dataset_sha256=h) for n,(c,s,h) in TASKS.items()},
            ready_sha256="d"*64,task_tokenization_sha256="e"*64,environment={"torch":"synthetic unit fixture; no model"})
        parent["execution"].update(repo=execution["repo"],files=copy.deepcopy(files))
        parent["execution"]["files"]["qwen3/sparq/benchmark.py"] = "1"*64
        save(parent_root/"IDENTITY.json",parent)
        original = benchmark_fixture()
        original.update(source_files_sha256={n:parent["execution"]["files"][n] for n in
            ("qwen3/sparq/benchmark.py","qwen3/sparq/adapter.py","qwen3/sparq/core.py")},
            token_ids_shape_and_le_int64_sha256="f"*64)
        for name,value in (("preflight",dict(passed=True)),("benchmark",original)):
            save(parent_root/(name+".json"),dict(experiment=fingerprint(parent),result=value,result_sha256=fingerprint(value)))
        link = dict(identity_sha256=sha(parent_root/"IDENTITY.json"),identity_fingerprint=fingerprint(parent),
            quality_source_commit=parent["execution"]["commit"],path="/synthetic/parent",
            benchmark_artifact_sha256=sha(parent_root/"benchmark.json"),preflight_artifact_sha256=sha(parent_root/"preflight.json"))
        schedule = dict(contexts=list(BENCHMARK_CONTEXTS),decode_lengths=list(BENCHMARK_DECODE_LENGTHS),
            modes=list(BENCHMARK_MODES),warmup=1,repeats=3,power_interval_s=.02)
        supplement_identity = dict(kind="benchmark_supplement",parent=link,measuring_execution=execution,
            ready_sha256=parent["ready_sha256"],model=MODEL,revision=REVISION,
            verified_model_files=[dict(name=n,bytes=1,sha256="a"*64) for n in sorted(SUPPLEMENT_MODEL_FILES)],
            verified_corpus_sha256="b"*64,tokens_sha256=parent["tokens_sha256"],config=parent["config"],
            benchmark_schedule=schedule,original_ffn=True,seed=0,environment=parent["environment"],
            gpu_name=original["gpu_name"],gpu_uuid="01234567-89ab-cdef-0123-456789abcdef",job="999",
            original_quality_results_inherited=False,quality_evaluation_performed=False,task_datasets_revalidated=False)
        measured = copy.deepcopy(original)
        measured.update(model_provenance=dict(model=MODEL,revision=REVISION,measuring_source_commit=execution["commit"],
            parent_quality_source_commit=link["quality_source_commit"],parent_identity_sha256=link["identity_sha256"],
            job="999",role="measurement_supplement"),torch_device_uuid=supplement_identity["gpu_uuid"],
            nvml_gpu_uuid=None,nvml_unavailable_reason="synthetic unit fixture; no NVML",timing_protocol="unit fixture",
            torch_version=parent["environment"]["torch"],parameter_dtypes=["torch.bfloat16"],
            scope="synthetic unit fixture; no real GPU measurement",
            source_files_sha256={n:files[n] for n in original["source_files_sha256"]})
        for row in measured["trials"]:
            for phase in ("prefill","decode"):
                row[phase].update(phase_energy_attribution_validated=False,power_poll_interval_s=.02,
                    power_unavailable_reason="synthetic unit fixture; no NVML")
        completed = dict(measurement_complete=True,quality_evaluation_complete=False,parent=link,
            measuring_source_commit=execution["commit"],benchmark=measured,power_windows_available=0,
            total_phase_windows=108,power_status="unavailable",physical_asic_ppa=None)
        def flush():
            save(root/"IDENTITY.json",supplement_identity)
            save(root/"INVOCATION.json",dict(job="999",unit_fixture=True))
            save(root/"benchmark_supplement.json",dict(experiment=fingerprint(supplement_identity),
                result=completed,result_sha256=fingerprint(completed),job="999"))
            producer = {key:supplement_identity[key] for key in ("parent","model","revision","measuring_execution",
                "job","gpu_uuid","gpu_name","environment","config","original_ffn","verified_model_files","tokens_sha256",
                "ready_sha256","verified_corpus_sha256")}
            producer.update(kind="benchmark_supplement_report",measurement_complete=True,quality_evaluation_complete=False,
                original_quality_results_inherited=False,schedule=schedule,power_status=completed["power_status"],
                power_windows_available=completed["power_windows_available"],phase_energy_attribution_validated=False,
                physical_asic_ppa=None,trial_count=len(measured["trials"]),
                **{k:measured[k] for k in ("timing_protocol","scope","nvml_gpu_uuid","nvml_unavailable_reason","summaries")})
            producer["transfer_artifacts"] = {n:dict(bytes=(root/n).stat().st_size,sha256=sha(root/n)) for n in
                ("IDENTITY.json","INVOCATION.json","benchmark_supplement.json")}
            save(root/"report.json",producer)
            save(root/"report.sha256.json",dict(file="report.json",sha256=sha(root/"report.json")))
        flush()
        return dict(root=root,source=source,parent=parent_root,identity=supplement_identity,
                    completed=completed,measured=measured,flush=flush,save=save)

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

        def test_benchmark_fixed_matrix_and_self_certification_rejected(self):
            valid = benchmark_fixture()
            report = _benchmark(valid, identity)
            self.assertTrue(report["verified_complete"])
            self.assertEqual(report["verified_trial_count"], 54)
            for field, value in (("contexts", []), ("decode_lengths", []), ("modes", []),
                    ("contexts", [128,512,2048,2048]), ("decode_lengths", [64,128,128]),
                    ("modes", ["native","dense","sparq","sparq"]),
                    ("modes", ["dense","sparq"]), ("measured_repeats", 0),
                    ("measured_repeats", 2), ("warmup_trials_per_case_mode", 0),
                    ("warmup_trials_per_case_mode", True)):
                with self.subTest(field=field,value=value):
                    bad = copy.deepcopy(valid)
                    bad[field] = value
                    # Keep the artifacts internally consistent with their own claimed
                    # matrix: the old self-certified coverage check accepted these.
                    bad["trials"] = [r for r in bad["trials"] if r["context_tokens"] in bad["contexts"] and
                        r["decode_steps"] in bad["decode_lengths"] and r["mode"] in bad["modes"] and
                        r["repeat"] < bad["measured_repeats"]]
                    keys = {(r["context_tokens"],r["decode_steps"],r["mode"]) for r in bad["trials"]}
                    bad["summaries"] = [r for r in bad["summaries"] if
                        (r["context_tokens"],r["decode_steps"],r["mode"]) in keys]
                    with self.assertRaises(AuditError):
                        _benchmark(bad, identity)

        def test_benchmark_token_rate_and_declared_bounds_recomputed(self):
            inflated = benchmark_fixture()
            for row in inflated["trials"]+inflated["summaries"]:
                for phase in ("prefill","decode"):
                    row[phase]["tokens_per_wall_second"] *= 100
            with self.assertRaises(AuditError):
                _benchmark(inflated, identity)
            for field, value in (("batch",2), ("batch",True), ("first_decode_cache_tokens",128),
                                 ("last_decode_cache_tokens",191), ("last_decode_logits_finite",False)):
                with self.subTest(field=field):
                    bad = benchmark_fixture()
                    bad["trials"][0][field] = value
                    with self.assertRaises(AuditError):
                        _benchmark(bad, identity)
            for phase, field in (("prefill","input_tokens"), ("decode","input_tokens"),
                                 ("decode","wall_seconds_per_decode_step")):
                with self.subTest(phase=phase,field=field):
                    bad = benchmark_fixture()
                    bad["trials"][0][phase][field] *= 2
                    with self.assertRaises(AuditError):
                        _benchmark(bad, identity)

        def test_supplement_complete_null_power_never_inherits_quality(self):
            with tempfile.TemporaryDirectory(prefix="supplement_unit_",dir=Path(__file__).parent) as temp:
                s = supplement_fixture(temp)
                got = review_benchmark_supplement(s["root"],s["source"],parent_results=s["parent"])
                self.assertTrue(got["measurement_complete"])
                self.assertFalse(got["quality_evaluation_complete"])
                self.assertEqual(got["benchmark"]["verified_trial_count"],54)
                self.assertEqual(got["power_windows_available"],0)
                self.assertEqual(got["identity"]["registered_source_files"],13)
                self.assertIn("质量评测完整：`False`",supplement_markdown(got))
                output = Path(temp)/"review"
                command = [sys.executable,"-m","qwen3.sparq.report",str(s["root"]),"--supplement",
                    "--source-root",str(s["source"]),"--parent-results",str(s["parent"]),"--output",str(output)]
                subprocess.run(command,cwd=Path(__file__).resolve().parents[2],capture_output=True,
                               text=True,encoding="utf-8",check=True)
                written = _load(output/"REVIEW.json")
                self.assertTrue(written["measurement_complete"])
                self.assertFalse(written["quality_evaluation_complete"])
                self.assertTrue((output/"REVIEW_ZH.md").is_file())
                (s["root"]/"report.sha256.json").unlink()
                partial = review_benchmark_supplement(s["root"],s["source"],parent_results=s["parent"])
                self.assertFalse(partial["measurement_complete"])
                self.assertFalse(partial["quality_evaluation_complete"])
                (s["root"]/"benchmark_supplement.json").unlink()
                (s["root"]/"report.json").unlink()
                partial = review_benchmark_supplement(s["root"],s["source"],parent_results=s["parent"])
                self.assertFalse(partial["benchmark"]["present"])
                self.assertFalse(partial["measurement_complete"])

        def test_supplement_hash_source_parent_scope_and_matrix_fail_closed(self):
            mutations = (
                lambda s: (s["source"]/"qwen3/sparq/adapter.py").write_bytes(b"changed source"),
                lambda s: (s["parent"]/"IDENTITY.json").write_bytes((s["parent"]/"IDENTITY.json").read_bytes()+b" "),
                lambda s: (s["root"]/"report.json").write_bytes((s["root"]/"report.json").read_bytes()+b" "),
                lambda s: s["save"](s["root"]/"INVOCATION.json",dict(job="other")),
                lambda s: (s["completed"].update(quality_evaluation_complete=True),s["flush"]()),
                lambda s: (s["measured"]["model_provenance"].update(measuring_source_commit="0"*40),s["flush"]()),
                lambda s: (s["measured"]["trials"].pop(),s["flush"]()),
                lambda s: (s["identity"]["parent"].update(identity_sha256="0"*64),s["flush"]()),
                lambda s: (s["measured"].update(token_ids_shape_and_le_int64_sha256="0"*64),s["flush"]()),
            )
            for index,mutation in enumerate(mutations):
                with self.subTest(case=index), tempfile.TemporaryDirectory(prefix="supplement_unit_",dir=Path(__file__).parent) as temp:
                    s = supplement_fixture(temp)
                    mutation(s)
                    with self.assertRaises(AuditError):
                        review_benchmark_supplement(s["root"],s["source"],parent_results=s["parent"])

        def test_supplement_verifies_power_even_when_summary_is_null(self):
            with tempfile.TemporaryDirectory(prefix="supplement_unit_",dir=Path(__file__).parent) as temp:
                s = supplement_fixture(temp)
                measured = s["measured"]
                measured.update(nvml_gpu_uuid="GPU-"+s["identity"]["gpu_uuid"],nvml_unavailable_reason=None)
                item = measured["trials"][0]["decode"]
                item.update(power=dict(sampled_board_energy_j=40.,average_board_power_w=20.),
                    power_unavailable_reason=None,
                    power_samples_relative_s_w=[(i/10,20.) for i in range(-1,22)],
                    max_sample_gap_s=.1,max_allowed_sample_gap_s=.25)
                s["completed"].update(power_windows_available=1,power_status="sampled_board_estimates")
                s["flush"]()
                got = review_benchmark_supplement(s["root"],s["source"],parent_results=s["parent"])
                self.assertTrue(got["measurement_complete"])
                self.assertEqual(got["power_windows_available"],1)
                self.assertIsNone(got["benchmark"]["summaries"][0]["decode"]["power"])
                item["power"]["sampled_board_energy_j"] = 4000.
                s["flush"]()
                with self.assertRaisesRegex(AuditError,"power integral"):
                    review_benchmark_supplement(s["root"],s["source"],parent_results=s["parent"])
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
    parser.add_argument("--supplement", action="store_true", help="verify independent benchmark supplement only")
    parser.add_argument("--parent-results", help="actual original quality result directory for supplement parent raw SHA checks")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        _self_test()
        return
    if not args.results or not args.output:
        parser.error("results and --output are required")
    if args.supplement and (not args.source_root or not args.parent_results):
        parser.error("--supplement requires --source-root and --parent-results")
    if args.parent_results and not args.supplement:
        parser.error("--parent-results is only valid with --supplement")
    source = Path(args.results).resolve(strict=True)
    destination = Path(args.output).resolve()
    require(not destination.is_relative_to(source), "report output must be outside immutable input results")
    if args.supplement:
        for protected in (args.source_root, args.parent_results):
            require(not destination.is_relative_to(Path(protected).resolve(strict=True)), "report output must be outside source/parent artifacts")
        result = review_benchmark_supplement(source, args.source_root, parent_results=args.parent_results)
    else:
        result = review(source, source_root=args.source_root)
    outputs = (("REVIEW.json", json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n"),
               ("REVIEW_ZH.md", supplement_markdown(result) if args.supplement else markdown(result)))
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
