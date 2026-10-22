"""Resume only the LLM layer over a metadata-verified, existing Torch base."""
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback

HOME = Path("/home/pwmat")
ROOT = HOME / "projects/llm-env-bootstrap-20261022"
ENV = HOME / "envs/llm-qwen-py312-cu118"
WHEELHOUSE = ROOT / "wheelhouse"
ARCHIVE = ROOT / "wheelhouse_payload.tar"
EXPORT = ROOT / "wheelhouse_export.json"
RESULT = ROOT / "install_offline_result.json"


def owned(path, *, exists=False, regular=False, directory=False, final_symlink=False):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise RuntimeError("expected a normalized absolute personal path: " + str(path))
    try:
        path.relative_to(HOME)
    except ValueError:
        raise RuntimeError("path escapes the authorized home: " + str(path))
    for ancestor in reversed((path, *path.parents)):
        if ancestor == HOME or HOME in ancestor.parents:
            if ancestor.is_symlink() and not (ancestor == path and final_symlink):
                raise RuntimeError("refusing a symlink in the target path: " + str(ancestor))
            if ancestor.exists() and ancestor.lstat().st_uid != os.getuid():
                raise RuntimeError("path is not account-owned: " + str(ancestor))
    resolved = path.resolve(strict=exists)
    if not resolved.is_relative_to(HOME):
        raise RuntimeError("canonical path escapes the authorized home: " + str(path))
    if resolved != path:
        owned(resolved, exists=exists, regular=regular, directory=directory)
    if regular and not stat.S_ISREG(resolved.stat().st_mode):
        raise RuntimeError("expected a regular file: " + str(path))
    if directory and not resolved.is_dir():
        raise RuntimeError("expected a directory: " + str(path))
    return resolved


def digest(path):
    owned(path, exists=True, regular=True)
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def sha256_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RuntimeError("invalid expected SHA-256")
    return value


def save_result(report):
    owned(RESULT)
    if RESULT.exists():
        owned(RESULT, exists=True, regular=True)
    temporary = RESULT.with_name(RESULT.name + ".tmp-" + str(os.getpid()))
    owned(temporary)
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    temporary.replace(RESULT)


def verify_existing(path, expected, size):
    owned(path)
    if path.exists():
        owned(path, exists=True, regular=True)
        if path.stat().st_size != size or digest(path) != expected:
            raise RuntimeError("refusing to overwrite different existing content: " + str(path))
        return True
    return False


def install_regular(stream, destination, expected, size):
    """Reuse identical targets; publish a verified temporary file without clobbering."""
    if verify_existing(destination, expected, size):
        return
    owned(destination.parent, exists=True, directory=True)
    with tempfile.NamedTemporaryFile(prefix="offline-unpack-", dir=str(ROOT / "tmp"), delete=False) as target:
        temporary = Path(target.name)
        hasher = hashlib.sha256()
        total = 0
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            target.write(chunk)
            hasher.update(chunk)
            total += len(chunk)
    owned(temporary, exists=True, regular=True)
    if total != size or hasher.hexdigest() != expected:
        raise RuntimeError("extracted bytes failed verification; temporary retained: " + str(temporary))
    try:
        os.link(str(temporary), str(destination), follow_symlinks=False)
    except FileExistsError:
        verify_existing(destination, expected, size)
    # This exact temporary was created and verified by this process inside personal tmp.
    temporary.unlink()
    if not verify_existing(destination, expected, size):
        raise RuntimeError("extraction target disappeared after publication: " + str(destination))


def torch_metadata():
    """Read distribution/version files; do not import Torch or call CUDA helpers."""
    site = owned(ENV / "lib/python3.12/site-packages", exists=True, directory=True)
    matches = [item for item in importlib.metadata.distributions(path=[str(site)])
               if item.metadata.get("Name", "").lower() == "torch"]
    if len(matches) != 1 or matches[0].version != "2.6.0+cu118":
        raise RuntimeError("existing environment must contain exactly Torch 2.6.0+cu118 metadata")
    version_file = site / "torch/version.py"
    owned(version_file, exists=True, regular=True)
    fields = {}
    for node in ast.parse(version_file.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        else:
            continue
        if "cuda" in names:
            fields["cuda"] = ast.literal_eval(node.value)
    if fields.get("cuda") != "11.8" or "torch" in sys.modules:
        raise RuntimeError("Torch CUDA build metadata mismatch or unexpected Torch import")
    return {"version": matches[0].version, "cuda_build": fields["cuda"],
            "version_file": str(version_file), "version_file_sha256": digest(version_file),
            "torch_imported": False}


def verify_and_extract(export):
    if export.get("stage") != "completed" or export.get("fresh_torch_environment_closure") is not False:
        raise RuntimeError("export must be completed and explicitly scoped to the installed Torch base")
    if export.get("archive") != str(ARCHIVE) or export.get("manifest") != str(WHEELHOUSE / "manifest.json"):
        raise RuntimeError("unexpected export archive/manifest paths")
    owned(ARCHIVE, exists=True, regular=True)
    if ARCHIVE.stat().st_size != export.get("archive_bytes") or digest(ARCHIVE) != sha256_value(export.get("archive_sha256")):
        raise RuntimeError("payload archive size or SHA-256 mismatch")
    count = export.get("wheel_count")
    if type(count) is not int or not 1 <= count <= 1000 or len(export.get("wheels", [])) != count:
        raise RuntimeError("invalid export wheel count")
    with tarfile.open(str(ARCHIVE), "r:") as bundle:
        members = bundle.getmembers()
        if len(members) != count + 1:
            raise RuntimeError("archive must contain exactly the declared wheels plus one manifest")
        by_name = {}
        for member in members:
            parts = PurePosixPath(member.name).parts
            if not member.isfile() or "\\" in member.name or len(parts) != 2 or parts[0] != "wheelhouse" or \
                    member.name != "wheelhouse/" + parts[-1] or member.name in by_name:
                raise RuntimeError("archive contains a non-regular, duplicate or unexpected member: " + member.name)
            filename = parts[-1]
            if filename != "manifest.json" and not re.fullmatch(r"[A-Za-z0-9_.+!-]+\.whl", filename):
                raise RuntimeError("archive member is not an explicit wheel or manifest: " + member.name)
            by_name[member.name] = member
        manifest_member = by_name.get("wheelhouse/manifest.json")
        if manifest_member is None or manifest_member.size > 5 * 1024 * 1024:
            raise RuntimeError("missing or oversized payload manifest")
        with bundle.extractfile(manifest_member) as stream:
            manifest_bytes = stream.read()
        if hashlib.sha256(manifest_bytes).hexdigest() != sha256_value(export.get("manifest_sha256")):
            raise RuntimeError("payload manifest hash differs from the completed export receipt")
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        records = manifest.get("wheels", [])
        if manifest.get("fresh_torch_environment_closure") is not False or len(records) != count or \
                manifest.get("pip_report_sha256") != sha256_value(export.get("pip_report_sha256")):
            raise RuntimeError("manifest scope, source report hash or wheel count mismatch")
        if sorted(records, key=lambda item: item["filename"]) != sorted(export["wheels"], key=lambda item: item["filename"]):
            raise RuntimeError("manifest wheel records differ from the completed export receipt")
        expected = {"wheelhouse/manifest.json": (sha256_value(export["manifest_sha256"]), len(manifest_bytes))}
        total = 0
        for item in records:
            filename = item.get("filename", "")
            name = re.sub(r"[-_.]+", "-", item.get("name", "")).lower()
            if not re.fullmatch(r"[A-Za-z0-9_.+!-]+\.whl", filename) or \
                    name in {"torch", "torchvision", "torchaudio", "triton"} or name.startswith("nvidia-"):
                raise RuntimeError("unexpected or forbidden Torch-base wheel: " + filename)
            key = "wheelhouse/" + filename
            if key in expected or key not in by_name:
                raise RuntimeError("duplicate or missing wheel: " + filename)
            size = item.get("bytes")
            if type(size) is not int or size <= 0 or by_name[key].size != size:
                raise RuntimeError("wheel size differs from manifest: " + filename)
            expected[key] = (sha256_value(item.get("sha256")), size)
            total += size
        if set(expected) != set(by_name) or total != export.get("wheel_bytes"):
            raise RuntimeError("archive member set or aggregate wheel size mismatch")
        # Verify all archived content and every pre-existing target before any extraction.
        owned(WHEELHOUSE)
        if WHEELHOUSE.exists():
            owned(WHEELHOUSE, exists=True, directory=True)
            allowed = {PurePosixPath(name).name for name in expected}
            if any(path.name not in allowed for path in WHEELHOUSE.iterdir()):
                raise RuntimeError("existing wheelhouse contains undeclared files; preserve them for inspection")
        for name, (expected_hash, size) in expected.items():
            hasher = hashlib.sha256()
            with bundle.extractfile(by_name[name]) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(chunk)
            if hasher.hexdigest() != expected_hash:
                raise RuntimeError("archived wheel/manifest failed SHA-256: " + name)
            verify_existing(ROOT / name, expected_hash, size)
        if not WHEELHOUSE.exists():
            WHEELHOUSE.mkdir(mode=0o700)
        owned(WHEELHOUSE, exists=True, directory=True)
        for name, (expected_hash, size) in expected.items():
            with bundle.extractfile(by_name[name]) as stream:
                install_regular(stream, ROOT / name, expected_hash, size)
        return records


def main():
    identity = pwd.getpwuid(os.getuid())
    if identity.pw_name != "pwmat" or identity.pw_dir != str(HOME) or HOME.resolve(strict=True) != HOME:
        raise RuntimeError("unexpected identity or canonical personal home")
    if not os.environ.get("SLURM_JOB_ID") or not os.environ.get("SLURM_JOB_NODELIST") or os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise RuntimeError("offline installation requires an allocated, explicitly GPU-hidden CPU Slurm job")
    for path in (HOME, ROOT, ENV, ROOT / "tmp", ROOT / "logs", ROOT / "cache/pip", ROOT / "cache/huggingface"):
        owned(path, exists=True, directory=True)
    owned(ENV / "bin/python", exists=True, regular=True, final_symlink=True)
    inputs = [ROOT / name for name in ("constraints.txt", "requirements-llm.txt", "compat_runtime.py", "cpu_check.py")]
    input_hashes = {str(path): digest(path) for path in inputs}
    owned(EXPORT, exists=True, regular=True)
    job = os.environ["SLURM_JOB_ID"]
    if not re.fullmatch(r"[0-9]+", job):
        raise RuntimeError("unexpected Slurm job identity")
    report = {"status": "started", "job_id": job, "hostname": os.uname().nodename,
              "scope": "Offline LLM extension over installed Torch 2.6.0+cu118; no GPU",
              "cuda_visible_devices": "", "start_unix": time.time(), "input_sha256": input_hashes}
    save_result(report)
    try:
        report["torch_base_metadata"] = torch_metadata()
        save_result(report)
        export = json.loads(EXPORT.read_text(encoding="utf-8"))
        records = verify_and_extract(export)
        report.update({"archive_sha256": export["archive_sha256"], "manifest_sha256": export["manifest_sha256"], "wheel_count": len(records)})
        save_result(report)
        env = dict(os.environ)
        for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PIP_TARGET", "PIP_PREFIX", "PIP_ROOT", "PIP_USER", "PIP_NO_INDEX", "PIP_FIND_LINKS", "PIP_EXTRA_INDEX_URL", "PIP_INDEX_URL"):
            env.pop(key, None)
        env.update({"CUDA_VISIBLE_DEVICES": "", "TMPDIR": str(ROOT / "tmp"), "PIP_CONFIG_FILE": os.devnull,
                    "PIP_CACHE_DIR": str(ROOT / "cache/pip"), "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                    "PIP_REQUIRE_VIRTUALENV": "1", "HF_HOME": str(ROOT / "cache/huggingface"),
                    "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                    "OPENBLAS_NUM_THREADS": "2", "NUMEXPR_NUM_THREADS": "2", "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"})
        # Preserve the venv invocation path and its pyvenv.cfg after validating its target.
        pip = [str(ENV / "bin/python"), "-I", "-B", "-m", "pip"]
        closure_report = ROOT / "logs" / ("offline-closure-" + job + ".json")
        install_report = ROOT / "logs" / ("pip-offline-" + job + ".json")
        for path in (closure_report, install_report):
            owned(path)
            if path.exists():
                raise RuntimeError("refusing to replace a previous pip execution report: " + str(path))
        common = ["--no-index", "--find-links", str(WHEELHOUSE), "--constraint", str(ROOT / "constraints.txt"),
                  "--requirement", str(ROOT / "requirements-llm.txt"), "--only-binary=:all:"]
        subprocess.run(pip + ["install", "--dry-run", "--report", str(closure_report)] + common, env=env, check=True)
        report.update({"offline_closure": "verified against installed fixed Torch base", "closure_report": str(closure_report),
                       "closure_report_sha256": digest(closure_report)})
        save_result(report)
        subprocess.run(pip + ["install", "--report", str(install_report)] + common, env=env, check=True)
        subprocess.run(pip + ["check"], env=env, check=True)
        report["torch_base_metadata_after"] = torch_metadata()
        if report["torch_base_metadata_after"] != report["torch_base_metadata"]:
            raise RuntimeError("fixed Torch base metadata changed during the LLM-only installation")
        freeze = subprocess.run(pip + ["freeze", "--all"], env=env, check=True, stdout=subprocess.PIPE, universal_newlines=True).stdout
        freeze_bytes = freeze.encode("utf-8")
        freeze_path = ROOT / ("pip_freeze-offline-" + job + ".txt")
        owned(freeze_path)
        if freeze_path.exists():
            if freeze_path.read_bytes() != freeze_bytes:
                raise RuntimeError("refusing to replace a different existing freeze record")
        else:
            with freeze_path.open("xb") as stream:
                stream.write(freeze_bytes)
        report.update({"pip_freeze": str(freeze_path), "pip_freeze_sha256": digest(freeze_path)})
        for path in inputs:
            if digest(path) != input_hashes[str(path)]:
                raise RuntimeError("original execution input changed during installation: " + str(path))
        subprocess.run([str(ENV / "bin/python"), "-I", "-B", str(ROOT / "compat_runtime.py")], env=env, check=True)
        for path in inputs:
            if digest(path) != input_hashes[str(path)]:
                raise RuntimeError("original execution input changed during CPU validation: " + str(path))
        report.update({"status": "passed", "pip_check": "passed", "install_report": str(install_report),
                       "install_report_sha256": digest(install_report), "original_inputs_preserved": True})
    except BaseException as exc:
        report.update({"status": "failed", "end_unix": time.time(), "error": type(exc).__name__ + ": " + str(exc), "traceback": traceback.format_exc()})
        save_result(report)
        raise
    report["end_unix"] = time.time()
    save_result(report)
    print(json.dumps({"status": report["status"], "wheel_count": report["wheel_count"]}))


if __name__ == "__main__":
    main()
