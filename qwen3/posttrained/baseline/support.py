"""Small provenance and scoring helpers; no model patches."""
import hashlib
import json
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def windows(length, window, stride):
    if length < 2 or not 0 < stride < window:
        raise ValueError("require length >= 2 and 0 < stride < window")
    previous_end = 0
    for begin in range(0, length, stride):
        end = min(begin + window, length)
        first = max(previous_end, begin + 1)
        yield begin, end, first
        previous_end = end
        if end == length:
            break


def check_data(config):
    result = {}
    for name, expected in config["data_sha256"].items():
        path = Path(config["data_root"]) / name
        actual = sha256(path)
        if actual != expected:
            raise ValueError(f"Corpus hash mismatch: {path}: {actual}")
        result[name] = {"path": str(path), "sha256": actual, "bytes": path.stat().st_size}
    return result


def check_config(config, specification):
    for name, value in specification.items():
        if name not in ("id", "revision"):
            assert getattr(config, name) == value, (name, getattr(config, name), value)
    assert config.model_type == "qwen3"
    assert config.tie_word_embeddings
    assert not config.attention_bias


def verify_files(manifest):
    for item in manifest["files"]:
        path = Path(manifest["local_path"]) / item["name"]
        assert path.stat().st_size == item["bytes"], str(path)
        assert sha256(path) == item["sha256"], str(path)


def verify_source(source):
    source = Path(source)
    manifest = json.loads((source / "execution.json").read_text())
    for name, expected in manifest["files_sha256"].items():
        assert sha256(source / name) == expected, name
    return manifest
