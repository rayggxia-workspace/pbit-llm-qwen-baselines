"""Pure-Python identity and sliding-window contract; no CUDA imports."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


CORPUS_SHA256 = "173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08"
EXPECTED_SHAPE = {
    "model_type": "llama", "hidden_size": 4096, "intermediate_size": 11008,
    "num_hidden_layers": 32, "num_attention_heads": 32,
    "num_key_value_heads": 32, "max_position_embeddings": 4096,
    "vocab_size": 32000, "rms_norm_eps": 1e-5, "rope_theta": 10000.0,
    "tie_word_embeddings": False,
}
LOADER_METADATA = (
    "config.json", "generation_config.json", "tokenizer.json", "tokenizer.model",
    "tokenizer_config.json", "special_tokens_map.json", "added_tokens.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    with Path(path).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, allow_nan=False, indent=2)
        handle.write("\n")


def verified_child(root: Path, name: str) -> Path:
    if not isinstance(name, str) or "\\" in name or Path(name).is_absolute():
        raise ValueError(f"Invalid manifest file name: {name!r}")
    path = (root / name).resolve()
    if path == root or root not in path.parents:
        raise ValueError(f"Manifest path escapes model directory: {name!r}")
    return path


def verify_identity(model: Path, manifest_path: Path) -> dict:
    """Verify local artifact bytes before any Transformers loading occurs.

    Symlinks are permitted only within the verified directory. A caller with a
    shared HF cache must first materialize its snapshot into a personal model
    directory; a bare revision label is insufficient evidence of file identity.
    """
    model = model.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("repository") != "meta-llama/Llama-2-7b-hf":
        raise ValueError("Requires the official Llama-2-7b-hf base repository")
    if not re.fullmatch(r"[0-9a-f]{40}", manifest.get("revision", "")):
        raise ValueError("Identity manifest must contain a pinned 40-hex HF revision")
    records = manifest.get("files", {})
    required = {"config.json", "tokenizer.json", "tokenizer.model", "tokenizer_config.json"}
    if not required.issubset(records):
        raise ValueError(f"Missing required manifest entries: {sorted(required - records.keys())}")
    if not records:
        raise ValueError("Identity manifest has no files")
    verified = {}
    for name, record in records.items():
        path = verified_child(model, name)
        if not re.fullmatch(r"[0-9a-f]{64}", record.get("sha256", "")):
            raise ValueError(f"Invalid SHA-256: {name}")
        if path.stat().st_size != record.get("bytes"):
            raise ValueError(f"Model byte-size mismatch: {name}")
        actual = sha256(path)
        if actual != record["sha256"]:
            raise ValueError(f"Model SHA-256 mismatch: {name}")
        verified[name] = {"sha256": actual, "bytes": path.stat().st_size}
    for name in LOADER_METADATA:
        if (model / name).exists() and name not in verified:
            raise ValueError(f"Present loader metadata is not identity-verified: {name}")
    for pattern in ("model*.safetensors", "model.safetensors.index.json",
                    "pytorch_model*.bin", "pytorch_model.bin.index.json"):
        for path in model.glob(pattern):
            if path.name not in verified:
                raise ValueError(f"Present checkpoint file is not identity-verified: {path.name}")
    use_safetensors = None
    for safe, index_name, single_name in (
        (True, "model.safetensors.index.json", "model.safetensors"),
        (False, "pytorch_model.bin.index.json", "pytorch_model.bin"),
    ):
        if index_name in verified:
            index = json.loads((model / index_name).read_text(encoding="utf-8"))
            shards = set(index.get("weight_map", {}).values())
            if not shards or not shards.issubset(verified):
                raise ValueError(f"Unverified weight shards in {index_name}")
            use_safetensors = safe
            break
        if single_name in verified:
            use_safetensors = safe
            break
    if use_safetensors is None:
        raise ValueError("No complete verified local weight checkpoint")
    config = json.loads((model / "config.json").read_text(encoding="utf-8"))
    shape = dict(config)
    shape.setdefault("num_key_value_heads", shape.get("num_attention_heads"))
    shape.setdefault("rope_theta", 10000.0)
    shape.setdefault("tie_word_embeddings", False)
    for key, expected in EXPECTED_SHAPE.items():
        if shape.get(key) != expected:
            raise ValueError(f"Llama-2-7B configuration mismatch: {key}={shape.get(key)!r}")
        if manifest.get("model_shape", {}).get(key, expected) != expected:
            raise ValueError(f"Identity manifest model_shape mismatch: {key}")
    if shape.get("attention_bias", False) or shape.get("mlp_bias", False):
        raise ValueError("Llama-2-7B reference has no QKV/MLP biases")
    if shape.get("hidden_act", "silu") != "silu":
        raise ValueError("Llama-2-7B reference requires SwiGLU/SiLU")
    if shape.get("rope_scaling") is not None:
        raise ValueError("Native-context baseline must not apply RoPE scaling")
    return {"repository": manifest["repository"], "revision": manifest["revision"],
            "files": verified, "model_shape": EXPECTED_SHAPE,
            "manifest_sha256": sha256(manifest_path),
            "use_safetensors": use_safetensors}


@dataclass(frozen=True)
class Window:
    begin: int
    end: int
    score_start: int

    @property
    def count(self) -> int:
        return self.end - self.score_start

    @property
    def logits_start(self) -> int:
        # Input local offset i predicts target local offset i+1.
        return self.score_start - self.begin - 1

    def record(self) -> dict:
        return {**asdict(self), "count": self.count, "logits_start": self.logits_start}


def windows(sequence_tokens: int, window: int, stride: int):
    """Score every corpus target 1..N-1 once, with no synthetic BOS/EOS.

    First window scores positions 1..window-1. Each following window retains
    overlap as context and scores only the newly reached positions. A final
    short stride is permitted. Position zero is the sole unscored token.
    """
    if sequence_tokens < 2 or window < 2 or not 0 < stride < window:
        raise ValueError("Require N>=2 and 0<stride<window")
    previous_end = 1
    for begin in range(0, sequence_tokens, stride):
        end = min(begin + window, sequence_tokens)
        start = max(previous_end, begin + 1)
        if start >= end:
            raise AssertionError("Sliding window has no newly scored targets")
        yield Window(begin, end, start)
        previous_end = end
        if end == sequence_tokens:
            break
