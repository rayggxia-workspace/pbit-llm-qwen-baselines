"""Independently audit archived bytes, exact scoring coverage, and NLL aggregation.

Does not rerun GPU inference. Frozen evaluator and original results are not edited.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "qwen3/results/bf16_20261023"
EXECUTION = "968046f9346258029192983000b4def643667cca"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git_bytes(path):
    return subprocess.check_output(["git", "show", EXECUTION + ":" + path], cwd=ROOT)


def validate_result(result):
    assert result["unmodified_model"] is True
    assert result["attention"] == "sdpa" and result["ffn"] == "native SwiGLU"
    assert result["seed"] == 0 and not result["use_cache"] and not result["add_special_tokens"]
    assert result["window"] == 2048 and result["stride"] == 1024
    length = result["corpus_tokens"]
    assert result["scored_tokens"] == length - 1
    previous_end, scored = 0, 0
    nll_values = []
    for index, window in enumerate(result["windows"]):
        begin = index * 1024
        end = min(begin + 2048, length)
        first = max(previous_end, begin + 1)
        assert window["window"] == index + 1
        assert (window["begin"], window["end"], window["first_target"]) == (begin, end, first)
        assert window["targets"] == end - first and first == scored + 1
        assert window["targets"] > 0 and math.isfinite(window["nll_sum"])
        scored += window["targets"]
        previous_end = end
        nll_values.append(window["nll_sum"])
    assert previous_end == length and scored == length - 1
    total = math.fsum(nll_values)
    assert math.isclose(total, result["nll_sum"], rel_tol=0, abs_tol=1e-8)
    assert math.isclose(total / scored, result["mean_nll"], rel_tol=0, abs_tol=1e-12)
    assert math.isclose(math.exp(total / scored), result["perplexity"], rel_tol=0, abs_tol=1e-12)
    assert result["source"]["commit"] == EXECUTION


def main():
    verified = []
    for line in (ARCHIVE / "SERVER_SHA256SUMS.txt").read_text().splitlines():
        expected, name = line.split("  ", 1)
        raw = (ARCHIVE / name).read_bytes()
        assert digest(raw) == expected, name
        verified.append({"path": name, "bytes": len(raw), "sha256": expected})
    assert len(verified) == 11
    assert json.loads((ARCHIVE / "prepared/cpu_tests_passed.json").read_text())["passed"]
    config_raw = git_bytes("qwen3/baselines/config.json")
    config = json.loads(config_raw)
    summary, token_hashes = [], []
    guards = 0
    for specification in config["models"]:
        name = specification["id"].split("/")[-1]
        result_path = ARCHIVE / "results" / (name + ".json")
        result = json.loads(result_path.read_bytes())
        prepared_raw = (ARCHIVE / "prepared" / (name + ".json")).read_bytes()
        prepared = json.loads(prepared_raw)
        assert result["model"] == prepared["model"] == specification
        assert prepared["revision"] == specification["revision"] and prepared["cpu_prepare_ok"]
        assert prepared["endpoint"] == "https://hf-mirror.com"
        assert result["prepared_sha256"] == digest(prepared_raw)
        assert result["config_sha256"] == prepared["config_sha256"] == digest(config_raw)
        assert json.loads(result_path.with_suffix(".sha256.json").read_text())["sha256"] == digest(result_path.read_bytes())
        assert result["data"] == prepared["data"]
        for key, expected in config["data_sha256"].items():
            assert result["data"][key]["sha256"] == expected
        for key, expected in specification.items():
            if key not in ("id", "revision"):
                assert prepared["model_config"][key] == expected
        assert prepared["model_config"]["torch_dtype"] == "bfloat16"
        assert not prepared["model_config"]["use_sliding_window"]
        assert prepared["model_config"]["sliding_window"] is None
        for file in prepared["files"]:
            assert file["bytes"] > 0 and len(file["sha256"]) == 64
            if file["upstream_lfs_sha256"]:
                assert file["sha256"] == file["upstream_lfs_sha256"]
        for file, expected in result["source"]["files_sha256"].items():
            assert digest(git_bytes("qwen3/baselines/" + file)) == expected
        assert result["environment"]["transformers"] == "4.51.3"
        validate_result(result)
        # Deliberately corrupted in-memory copies must fail; archived files are never modified.
        for kind in ("coverage", "count", "nll", "ppl", "window"):
            changed = copy.deepcopy(result)
            if kind == "coverage": changed["windows"][1]["first_target"] -= 1
            if kind == "count": changed["scored_tokens"] += 1
            if kind == "nll": changed["nll_sum"] += 1
            if kind == "ppl": changed["perplexity"] += .01
            if kind == "window": changed["windows"][0]["begin"] = 1
            try:
                validate_result(changed)
            except AssertionError:
                guards += 1
            else:
                raise AssertionError("corruption guard failed: " + kind)
        token_hashes.append(result["token_ids_int64_le_sha256"])
        summary.append({key: result[key] for key in ("model", "perplexity", "mean_nll", "nll_sum",
            "corpus_tokens", "scored_tokens", "evaluation_seconds", "peak_allocated_bytes", "peak_reserved_bytes")})
    assert len(set(token_hashes)) == 1 and guards == 10
    validation = {"status": "PASS", "scope": "byte hashes, source/config/data/model binding, exact target coverage and stored NLL aggregation; no new GPU inference",
                  "source_commit": EXECUTION, "verified_server_files": verified, "negative_guards_passed": guards,
                  "token_ids_int64_le_sha256": token_hashes[0], "models": summary}
    with (ARCHIVE / "VALIDATION.json").open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(validation, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": "PASS", "server_files": len(verified), "corruption_guards": guards, "models": summary}, indent=2))


if __name__ == "__main__":
    main()
