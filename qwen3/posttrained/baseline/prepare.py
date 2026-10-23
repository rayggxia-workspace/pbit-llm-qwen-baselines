"""Download pinned public weights through the requested mirror and verify bytes."""
import argparse
import hashlib
import json
import os
import http.client
import time
from pathlib import Path

from support import check_config, check_data, save, sha256, verify_source


def network_retry(call):
    import requests
    for attempt in range(3):
        try:
            return call()
        except (requests.exceptions.RequestException, http.client.RemoteDisconnected,
                ConnectionError, TimeoutError) as error:
            print(f'NETWORK_ATTEMPT_FAILED {attempt + 1}/3 {type(error).__name__}: {error}', flush=True)
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--index", type=int, required=True)
    args = parser.parse_args()
    root = Path(args.project).resolve()
    verify_source(Path(__file__).parent)
    config = json.loads(Path(__file__).with_name("config.json").read_text())
    os.environ["HF_ENDPOINT"] = config["endpoint"]
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    from huggingface_hub import HfApi, snapshot_download
    from transformers import AutoConfig, AutoTokenizer
    specification = config["models"][args.index]
    name = specification["id"].split("/")[-1]
    destination = root / "models" / name
    api = HfApi(endpoint=config["endpoint"], token=False)
    info = network_retry(lambda: api.model_info(specification["id"], revision=specification["revision"], files_metadata=True))
    assert info.sha == specification["revision"]
    allowed = [f.rfilename for f in info.siblings if f.rfilename.endswith((".json", ".safetensors", ".model")) or f.rfilename in ("merges.txt", "vocab.txt")]
    assert any(name.endswith(".safetensors") for name in allowed)
    print(f"Downloading {specification['id']} @ {info.sha} via {config['endpoint']}", flush=True)
    network_retry(lambda: snapshot_download(specification["id"], revision=info.sha, local_dir=str(destination),
                      allow_patterns=allowed, max_workers=2, token=False, endpoint=config["endpoint"]))
    files = []
    for metadata in info.siblings:
        if metadata.rfilename not in allowed:
            continue
        path = destination / metadata.rfilename
        digest = sha256(path)
        assert path.stat().st_size == metadata.size, str(path)
        if metadata.lfs:
            assert digest == metadata.lfs.sha256, str(path)
        else:
            raw = path.read_bytes()
            git_blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
            assert git_blob == metadata.blob_id, str(path)
        files.append({"name": metadata.rfilename, "bytes": path.stat().st_size,
                      "sha256": digest, "upstream_git_blob": metadata.blob_id,
                      "upstream_lfs_sha256": metadata.lfs.sha256 if metadata.lfs else None})
    model_config = AutoConfig.from_pretrained(destination, local_files_only=True, trust_remote_code=False)
    check_config(model_config, specification)
    tokenizer = AutoTokenizer.from_pretrained(destination, local_files_only=True, trust_remote_code=False)
    token_ids = tokenizer("Qwen3 baseline smoke test.", add_special_tokens=False).input_ids
    assert len(token_ids) > 1
    assert specification['id'] == 'Qwen/Qwen3-4B'
    assert specification['revision'] == '1cfa9a7208912126459214e8b04321603b3df60c'
    # Derive the token binding from THIS tokenizer, never inherit Base token hashes.
    import struct
    data = check_data(config)
    test_ids = tokenizer(Path(data['wiki.test.raw']['path']).read_bytes().decode('utf-8'),
                         add_special_tokens=False).input_ids
    token_sha = hashlib.sha256(b''.join(struct.pack('<q', x) for x in test_ids)).hexdigest()
    save(root / "prepared" / f"{name}.json", {
        "model": specification, "endpoint": config["endpoint"], "revision": info.sha,
        "local_path": str(destination), "files": files, "data": data,
        "test_token_ids_sha256_le_int64": token_sha, "test_corpus_tokens": len(test_ids),
        "chat_template_used_for_ppl": False, "thinking_generation": False,
        "config_sha256": sha256(Path(__file__).with_name("config.json")),
        "tokenizer_class": type(tokenizer).__name__, "tokenizer_smoke_ids": token_ids,
        "model_config": model_config.to_dict(), "cpu_prepare_ok": True,
    })
    print(f"PREPARED {name}: {len(files)} verified files", flush=True)


if __name__ == "__main__":
    main()
