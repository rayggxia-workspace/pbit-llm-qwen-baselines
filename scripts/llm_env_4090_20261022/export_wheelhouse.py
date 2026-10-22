"""Export the recorded LLM-stage pip cache, without networking or Torch base wheels.

This is a recovery payload for the matching environment with Torch already
installed.  It is not a complete wheel closure for a fresh Torch installation.
"""

import email.parser
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import tarfile
import time
import traceback
from urllib.parse import unquote, urlsplit
import zipfile


HOME = Path("/home/pwmat")
ROOT = HOME / "projects/llm-env-bootstrap-20261022"
ENV = HOME / "envs/llm-qwen-py312-cu118"
CACHE = ROOT / "cache/pip"
REPORT = ROOT / "logs/pip-llm-report.json"
WHEELHOUSE = ROOT / "wheelhouse"
ARCHIVE = ROOT / "wheelhouse_payload.tar"
RESULT = ROOT / "wheelhouse_export.json"
PURE_SOURCE_PACKAGES = {"rouge-score": "0.1.2", "sqlitedict": "2.1.0", "word2number": "1.1"}


def canonical_name(value):
    return re.sub(r"[-_.]+", "-", value).lower()


def check_path(path, *, exists=False, regular=False):
    path = Path(path)
    resolved = path.resolve(strict=exists)
    if not resolved.is_relative_to(HOME):
        raise RuntimeError("path escapes the verified personal home: " + str(path))
    for ancestor in (resolved, *resolved.parents):
        if ancestor == HOME.parent:
            break
        if ancestor.exists() and ancestor.stat().st_uid != os.getuid():
            raise RuntimeError("path is not account-owned: " + str(ancestor))
    if regular and (path.is_symlink() or not stat.S_ISREG(path.stat().st_mode)):
        raise RuntimeError("an explicit regular file is required: " + str(path))
    return resolved


def digest(path):
    check_path(path, exists=True, regular=True)
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def save(path, value):
    check_path(path)
    temporary = Path(path).with_name(Path(path).name + f".tmp-{os.getpid()}")
    check_path(temporary)
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def source_info(item):
    download = item["download_info"]
    url = download["url"]
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "files.pythonhosted.org" or parsed.username or parsed.password:
        raise RuntimeError("LLM payload only accepts recorded official PyPI file URLs")
    filename = unquote(parsed.path.rsplit("/", 1)[-1])
    if not filename or Path(filename).name != filename or not re.fullmatch(r"[A-Za-z0-9_.+!-]+", filename):
        raise RuntimeError("unsafe source archive basename: " + filename)
    expected = download["archive_info"]["hashes"]["sha256"].lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RuntimeError("source report has no valid SHA-256 for " + filename)
    return url, filename, expected


def cached_wheel_body(cache, url):
    from pip._vendor.cachecontrol.controller import CacheController
    for key in dict.fromkeys((CacheController.cache_url(url), url)):
        metadata = Path(cache._get_cache_path(key))
        body = metadata.with_name(metadata.name + ".body")
        if metadata.exists() and body.exists():
            check_path(metadata, exists=True, regular=True)
            check_path(body, exists=True, regular=True)
            stream = cache.get_body(key)
            if stream is not None:
                return stream, body
    raise FileNotFoundError("the recorded official wheel is absent from the personal pip HTTP cache: " + url)


def copy_verified(source_stream, destination, expected):
    check_path(destination)
    if destination.exists():
        if digest(destination) != expected:
            raise RuntimeError("existing wheel differs; preserve it for diagnosis: " + str(destination))
        return
    partial = destination.with_name(destination.name + f".part-{os.getpid()}")
    check_path(partial)
    hasher = hashlib.sha256()
    with partial.open("xb") as target:
        for chunk in iter(lambda: source_stream.read(1024 * 1024), b""):
            target.write(chunk)
            hasher.update(chunk)
    if hasher.hexdigest() != expected:
        raise RuntimeError("cached wheel SHA-256 differs from the pip report: " + destination.name)
    partial.replace(destination)


def wheel_metadata(path):
    check_path(path, exists=True, regular=True)
    with zipfile.ZipFile(path) as wheel:
        names = wheel.namelist()
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        wheel_names = [name for name in names if name.endswith(".dist-info/WHEEL")]
        if len(metadata_names) != 1 or len(wheel_names) != 1:
            raise RuntimeError("built wheel has ambiguous metadata: " + str(path))
        metadata = email.parser.Parser().parsestr(wheel.read(metadata_names[0]).decode("utf-8"))
        wheel_info = email.parser.Parser().parsestr(wheel.read(wheel_names[0]).decode("utf-8"))
        if wheel_info.get("Root-Is-Purelib", "").lower() != "true" or \
                any(name.lower().endswith((".so", ".pyd", ".dll", ".dylib")) for name in names):
            raise RuntimeError("a source-built payload wheel is not pure Python: " + str(path))
        if not wheel_info.get_all("Tag") or any(not tag.endswith("-none-any") for tag in wheel_info.get_all("Tag")):
            raise RuntimeError("source-built wheel is not platform independent: " + str(path))
        return canonical_name(metadata["Name"]), metadata["Version"]


def find_built_wheel(item, url, source_hash):
    name = canonical_name(item["metadata"]["name"])
    version = item["metadata"]["version"]
    if PURE_SOURCE_PACKAGES.get(name) != version:
        raise RuntimeError("unapproved source-built package in LLM report: " + name)
    candidates = []
    wheel_cache = check_path(CACHE / "wheels", exists=True)
    entries = list(wheel_cache.rglob("*.whl"))
    if len(entries) > 2000:
        raise RuntimeError("personal wheel cache exceeds the bounded inspection budget")
    for path in entries:
        # Select by name/version before reading ZIP contents of unrelated wheels.
        if not path.name.startswith(name.replace("-", "_") + "-" + version + "-"):
            continue
        check_path(path, exists=True, regular=True)
        origin_path = path.parent / "origin.json"
        if not origin_path.exists():
            continue
        check_path(origin_path, exists=True, regular=True)
        origin = json.loads(origin_path.read_text(encoding="utf-8"))
        origin_hash = origin.get("archive_info", {}).get("hashes", {}).get("sha256")
        if origin_hash is None:
            legacy = origin.get("archive_info", {}).get("hash", "")
            origin_hash = legacy.partition("=")[2] if legacy.startswith("sha256=") else None
        if origin_hash != source_hash or origin.get("url") != url:
            continue
        if wheel_metadata(path) != (name, version):
            continue
        candidates.append((path, origin_path))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one source-hash-matched built wheel for {name}=={version}, found {len(candidates)}")
    return candidates[0]


def main():
    identity = pwd.getpwuid(os.getuid())
    if identity.pw_name != "pwmat" or Path(identity.pw_dir).resolve(strict=True) != HOME or HOME.resolve(strict=True) != HOME:
        raise RuntimeError("unexpected identity or canonical home")
    if not os.environ.get("SLURM_JOB_ID") or os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise RuntimeError("export requires an explicitly GPU-hidden CPU Slurm allocation")
    if Path(sys.prefix).resolve(strict=True) != ENV or sys.prefix == sys.base_prefix:
        raise RuntimeError("export must use the verified personal LLM environment Python")
    for path in (ROOT, ENV, CACHE, REPORT):
        check_path(path, exists=True, regular=path == REPORT)
    if os.environ.get("PIP_CACHE_DIR") != str(CACHE):
        raise RuntimeError("export requires the original personal PIP_CACHE_DIR")
    check_path(WHEELHOUSE)
    WHEELHOUSE.mkdir(exist_ok=True)
    result = {
        "stage": "started", "job_id": os.environ["SLURM_JOB_ID"],
        "hostname": os.uname().nodename, "username": identity.pw_name,
        "environment": str(ENV), "cuda_visible_devices": "", "start_unix": time.time(),
        "scope": "recorded LLM-stage wheels; matching Torch base must already be installed",
        "fresh_torch_environment_closure": False, "pip_report": str(REPORT),
        "pip_report_sha256": digest(REPORT), "wheels": [],
    }
    save(RESULT, result)
    try:
        from pip._internal.network.cache import SafeFileCache
        cache_root = check_path(CACHE / "http-v2", exists=True)
        cache = SafeFileCache(str(cache_root))
        install_report = json.loads(REPORT.read_text(encoding="utf-8"))
        items = install_report.get("install", [])
        if not items:
            raise RuntimeError("LLM install report has no recorded installation entries")
        seen = set()
        for item in items:
            name = canonical_name(item["metadata"]["name"])
            version = item["metadata"]["version"]
            if name in {"torch", "torchvision", "torchaudio", "triton"} or name.startswith("nvidia-"):
                raise RuntimeError("LLM report unexpectedly contains a Torch/CUDA base package; refuse to export it: " + name)
            url, filename, source_hash = source_info(item)
            result["active_package"] = name + "==" + version
            save(RESULT, result)
            if filename.endswith(".whl"):
                stream, cache_path = cached_wheel_body(cache, url)
                destination = WHEELHOUSE / filename
                with stream:
                    copy_verified(stream, destination, source_hash)
                record = {
                    "name": name, "version": version, "filename": filename,
                    "kind": "official_pypi_wheel", "source_url": url,
                    "source_archive_sha256": source_hash, "wheel_sha256": source_hash,
                    "cache_body": str(cache_path),
                }
            else:
                built, origin_path = find_built_wheel(item, url, source_hash)
                wheel_hash = digest(built)
                destination = WHEELHOUSE / built.name
                with built.open("rb") as stream:
                    copy_verified(stream, destination, wheel_hash)
                record = {
                    "name": name, "version": version, "filename": built.name,
                    "kind": "locally_built_pure_python_wheel", "source_url": url,
                    "source_archive_sha256": source_hash, "wheel_sha256": wheel_hash,
                    "origin_json": str(origin_path), "origin_json_sha256": digest(origin_path),
                    "cache_wheel": str(built), "wheel_hash_is_official_pypi_hash": False,
                }
            if destination.name in seen:
                raise RuntimeError("duplicate wheel filename in report: " + destination.name)
            seen.add(destination.name)
            record["sha256"] = record["wheel_sha256"]
            record["bytes"] = destination.stat().st_size
            if digest(destination) != record["wheel_sha256"]:
                raise RuntimeError("exported wheel failed independent hash readback: " + destination.name)
            result["wheels"].append(record)
            save(RESULT, result)

        manifest = {
            "scope": result["scope"], "fresh_torch_environment_closure": False,
            "pip_report_sha256": result["pip_report_sha256"],
            "wheels": sorted(result["wheels"], key=lambda item: item["filename"]),
        }
        manifest_path = WHEELHOUSE / "manifest.json"
        save(manifest_path, manifest)
        explicit_files = [WHEELHOUSE / item["filename"] for item in manifest["wheels"]] + [manifest_path]
        temporary_archive = ARCHIVE.with_name(ARCHIVE.name + f".tmp-{os.getpid()}")
        check_path(temporary_archive)
        if ARCHIVE.exists():
            check_path(ARCHIVE, exists=True, regular=True)
        with tarfile.open(temporary_archive, "w", format=tarfile.PAX_FORMAT) as bundle:
            for path in explicit_files:
                check_path(path, exists=True, regular=True)
                bundle.add(path, arcname="wheelhouse/" + path.name, recursive=False)
        expected_hashes = {"wheelhouse/" + item["filename"]: item["wheel_sha256"] for item in manifest["wheels"]}
        expected_hashes["wheelhouse/manifest.json"] = digest(manifest_path)
        with tarfile.open(temporary_archive, "r:") as bundle:
            members = bundle.getmembers()
            if len(members) != len(expected_hashes) or {member.name for member in members} != set(expected_hashes):
                raise RuntimeError("payload archive members differ from the explicit regular-file manifest")
            for member in members:
                if not member.isfile():
                    raise RuntimeError("payload archive contains a non-regular member: " + member.name)
                hasher = hashlib.sha256()
                with bundle.extractfile(member) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        hasher.update(chunk)
                if hasher.hexdigest() != expected_hashes[member.name]:
                    raise RuntimeError("payload archive member hash mismatch: " + member.name)
        temporary_archive.replace(ARCHIVE)
        result.update({
            "stage": "completed", "finish_unix": time.time(), "wheel_count": len(result["wheels"]),
            "wheel_bytes": sum(item["bytes"] for item in result["wheels"]),
            "manifest": str(manifest_path), "manifest_sha256": digest(manifest_path),
            "archive": str(ARCHIVE), "archive_bytes": ARCHIVE.stat().st_size,
            "archive_sha256": digest(ARCHIVE),
        })
        result.pop("active_package", None)
        save(RESULT, result)
        print(json.dumps({key: result[key] for key in ("stage", "wheel_count", "archive", "archive_bytes", "archive_sha256")}))
    except BaseException as error:
        result.update({"stage": "failed", "finish_unix": time.time(), "error": type(error).__name__ + ": " + str(error), "traceback": traceback.format_exc()})
        save(RESULT, result)
        raise


if __name__ == "__main__":
    main()
