"""Verify independently recorded E0/E1 input hashes before loading any weights.

Expected JSON schema (paths are absolute, SHA-256 hashes are lowercase hex)::

    {"schema": "attention-e01-input-manifest-v1",
     "model_id": "Qwen/Qwen2.5-0.5B",
     "model_revision": "060db6499f32faf8b98477b0a26969ef7d8b9987",
     "provenance": {"reference": "location/version of the recorded source manifest"},
     "files": [{"role": "model", "path": "/home/Weican_Chen/.../config.json",
                "sha256": "...64 hex characters...", "bytes": 681},
               {"role": "tokenizer", "path": "/home/Weican_Chen/.../tokenizer.json",
                "sha256": "..."},
               {"role": "testtext", "path": "/home/Weican_Chen/.../wiki.test.raw",
                "sha256": "..."}]}

Include every relevant local model/tokenizer file, not only these examples.
The manifest must come from recorded upstream provenance; generating expected
hashes from arbitrary current files would not establish the model revision.
Both the original 681-byte config and the previously verified 709-byte server
config are explicitly recognized and reported as different byte variants; the
original weight and raw WT2 test hashes remain fixed. This byte distinction
does not establish a different model revision.
No download, modification of inputs, or expensive model execution occurs here.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path


SCHEMA = "attention-e01-input-manifest-v1"
REPORT_SCHEMA = "attention-e01-input-verification-v1"
MODEL_ID = "Qwen/Qwen2.5-0.5B"
MODEL_REVISION = "060db6499f32faf8b98477b0a26969ef7d8b9987"
CONFIG_SHA256 = "479dcf0c5286339e41ad3992cd08ae88a467c4187587936248e2b7c96283484b"
KNOWN_CONFIG_SHA256 = {
    CONFIG_SHA256: "original_upstream_681_bytes",
    "ce7908dfd631cd1f713a65cbea3591d32acaab58d438127d70c5dfc5ce1fc1f0": "prior_verified_server_snapshot_709_bytes",
}
WEIGHTS_SHA256 = "88c142557820ccad55bb59756bfcfcf891de9cc6202816bd346445188a0ed342"
TESTTEXT_SHA256 = "173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08"
DEFAULT_PERSONAL_ROOT = "/home/Weican_Chen"
EXPECTED_CONFIG = {
    "model_type": "qwen2", "num_hidden_layers": 24,
    "num_attention_heads": 14, "num_key_value_heads": 2,
    "hidden_size": 896, "vocab_size": 151936,
}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def owned_path(value, personal_root, *, exists=True):
    """Containment is a scope guard; caller must verify server user/root owner."""
    root = Path(personal_root).expanduser()
    candidate = Path(value).expanduser()
    if not root.is_absolute() or not candidate.is_absolute():
        raise ValueError("personal root and all artifact paths must be absolute")
    root = root.resolve(strict=True)
    candidate = candidate.resolve(strict=exists)
    if not candidate.is_relative_to(root):
        raise ValueError(f"path escapes the explicit personal root: {candidate}")
    return candidate


def relevant_role(path):
    """Files that can alter local Transformers weights/config/tokenization."""
    name = path.name.lower()
    if (name.startswith(("tokenizer", "vocab", "merges", "special_tokens"))
            or name.endswith((".model", ".tiktoken"))
            or name == "added_tokens.json"):
        return "tokenizer"
    if (name.startswith("config") or name == "generation_config.json"
            or name.endswith((".safetensors", ".index.json", ".bin", ".pt", ".pth"))):
        return "model"
    return None


def validate_config(config):
    for key, expected in EXPECTED_CONFIG.items():
        if config.get(key) != expected:
            raise ValueError(f"config {key}: expected {expected!r}, got {config.get(key)!r}")
    if config["hidden_size"] // config["num_attention_heads"] != 64:
        raise ValueError("expected 64-dimensional attention heads")
    if config.get("use_sliding_window", False):
        raise ValueError("capture requires full causal attention without sliding windows")


def verify(model, text, manifest_path, personal_root=DEFAULT_PERSONAL_ROOT):
    model = owned_path(model, personal_root)
    text = owned_path(text, personal_root)
    manifest_path = owned_path(manifest_path, personal_root)
    if not model.is_dir() or not text.is_file() or not manifest_path.is_file():
        raise ValueError("model must be a directory and text/manifest must be files")
    if (model / "adapter_config.json").exists():
        raise ValueError("adapter auto-loading is outside the unchanged baseline input contract")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ValueError(f"expected manifest schema {SCHEMA}")
    if (manifest.get("model_id"), manifest.get("model_revision")) != (MODEL_ID, MODEL_REVISION):
        raise ValueError("manifest does not pin the repository's original Qwen model revision")
    provenance = manifest.get("provenance")
    reference = provenance.get("reference") if isinstance(provenance, dict) else None
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("manifest must identify the independent recorded hash source")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("manifest files must be a nonempty list")
    actual = {}
    for path in model.rglob("*"):
        if path.is_symlink() and path.is_dir():
            raise ValueError(f"nested symlink directories require an explicit flat snapshot: {path}")
        role = relevant_role(path)
        if role is not None and path.is_file():
            resolved = owned_path(path, personal_root)
            if resolved in actual:
                raise ValueError(f"aliased model paths are ambiguous: {path}")
            actual[resolved] = role
    if text in actual:
        raise ValueError("test text must be separate from model/tokenizer files")
    actual[text] = "testtext"
    if not (model / "config.json").is_file() or not (model / "tokenizer_config.json").is_file():
        raise ValueError("missing config.json or tokenizer_config.json")
    if not ((model / "tokenizer.json").is_file()
            or ((model / "vocab.json").is_file() and (model / "merges.txt").is_file())):
        raise ValueError("missing complete tokenizer vocabulary")
    weights_path = owned_path(model / "model.safetensors", personal_root)
    if weights_path not in actual:
        raise ValueError("expected original model.safetensors; unsafe fallback is not permitted")
    verified = []
    checked_hashes = {}
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each manifest file must be an object")
        path = owned_path(entry.get("path", ""), personal_root)
        if path in seen:
            raise ValueError(f"duplicate manifest path: {path}")
        seen.add(path)
        if path not in actual or entry.get("role") != actual[path]:
            raise ValueError(f"unexpected path/role in manifest: {path}")
        expected_hash = entry.get("sha256", "")
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise ValueError(f"missing or malformed expected SHA-256: {path}")
        size = path.stat().st_size
        if "bytes" in entry and (type(entry["bytes"]) is not int or entry["bytes"] != size):
            raise ValueError(f"byte size mismatch: {path}")
        digest = sha256_file(path)
        if digest != expected_hash:
            raise ValueError(f"SHA-256 mismatch: {path}")
        checked_hashes[path] = digest
        verified.append({"role": actual[path], "path": str(path), "sha256": digest, "bytes": size})
    if seen != actual.keys():
        missing = sorted(str(path) for path in actual.keys() - seen)
        raise ValueError(f"manifest omits relevant inputs: {missing}")
    for path in actual:
        if path.name.endswith(".index.json"):
            index = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(index.get("weight_map"), dict):
                raise ValueError(f"invalid model weight index: {path}")
            for shard in set(index["weight_map"].values()):
                shard_path = owned_path(model / shard, personal_root)
                if shard_path not in actual or actual[shard_path] != "model":
                    raise ValueError(f"unverified weight shard referenced by {path}: {shard}")
    config_path = owned_path(model / "config.json", personal_root)
    config_sha = checked_hashes[config_path]
    if config_sha not in KNOWN_CONFIG_SHA256:
        raise ValueError("config hash differs from original pinned or prior verified server configuration")
    if checked_hashes[weights_path] != WEIGHTS_SHA256:
        raise ValueError("weights hash differs from previously verified original Qwen checkpoint")
    if checked_hashes[text] != TESTTEXT_SHA256:
        raise ValueError("test text hash differs from previously verified original WT2 raw corpus")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_config(config)
    return {
        "schema": REPORT_SCHEMA, "passed": True, "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION, "model": str(model), "text": str(text),
        "personal_root": str(Path(personal_root).resolve()),
        "expected_manifest": str(manifest_path),
        "expected_manifest_sha256": sha256_file(manifest_path),
        "provenance": manifest["provenance"], "files": verified,
        "config": config, "config_sha256": config_sha,
        "config_variant": KNOWN_CONFIG_SHA256[config_sha],
        "scope": "file provenance and exact-byte verification; no PPL or hardware validation",
    }


def recheck_report(report_path, model, text, personal_root):
    report_path = owned_path(report_path, personal_root)
    previous = json.loads(report_path.read_text(encoding="utf-8"))
    if previous.get("schema") != REPORT_SCHEMA or previous.get("passed") is not True:
        raise ValueError("capture requires a passing input-verification report")
    if previous.get("personal_root") != str(Path(personal_root).resolve()):
        raise ValueError("verification personal root differs from capture personal root")
    current = verify(model, text, previous["expected_manifest"], personal_root)
    for key in ("model", "text", "expected_manifest_sha256", "files", "config_sha256"):
        if previous.get(key) != current[key]:
            raise ValueError(f"inputs changed after verification: {key}")
    return current


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--expected-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--personal-root", default=DEFAULT_PERSONAL_ROOT)
    args = parser.parse_args()
    output = owned_path(args.output, args.personal_root, exists=False)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite verification result: {output}")
    try:
        result = verify(args.model, args.text, args.expected_manifest, args.personal_root)
    except (OSError, ValueError, KeyError) as exc:
        result = {"schema": REPORT_SCHEMA, "passed": False, "error": str(exc)}
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        raise SystemExit(str(exc)) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "files": len(result["files"]), "output": str(output)}))


if __name__ == "__main__":
    main()
