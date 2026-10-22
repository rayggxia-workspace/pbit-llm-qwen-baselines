"""Install only inside the verified personal home and a CPU Slurm allocation."""
import hashlib
import json
import os
import pathlib
import pwd
import re
import subprocess
import sys
import tarfile
import time
import traceback


HOME = pathlib.Path("/home/pwmat")
ROOT = HOME / "projects/llm-env-bootstrap-20261022"
ENV = HOME / "envs/llm-qwen-py312-cu118"
RUNTIME = HOME / "opt/cpython-3.12.3-20240415"
ARCHIVE = "cpython-3.12.3+20240415-x86_64-unknown-linux-gnu-install_only.tar.gz"
URL = "https://github.com/astral-sh/python-build-standalone/releases/download/20240415/" + ARCHIVE.replace("+", "%2B")
OFFICIAL_SHA256 = "a73ba777b5d55ca89edef709e6b8521e3f3d4289581f174c8699adfb608d09d6"


def check_path(path):
    canonical = path.resolve()
    if os.path.commonpath([str(HOME), str(canonical)]) != str(HOME):
        raise RuntimeError("Path escapes the personal home: " + str(path))
    parent = path
    while parent != HOME.parent:
        if parent.exists() and parent.stat().st_uid != os.getuid():
            raise RuntimeError("Path is not account-owned: " + str(parent))
        if parent == HOME:
            break
        parent = parent.parent
    return canonical


def save(path, value):
    check_path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


def run(argv, **kwargs):
    print("RUN " + json.dumps([str(item) for item in argv]), flush=True)
    return subprocess.run([str(item) for item in argv], check=True, **kwargs)


def download(url, path):
    check_path(path)
    if path.exists():
        return
    partial = path.with_name(path.name + ".part")
    run(["/usr/bin/curl", "--fail", "--location", "--retry", "3", "--retry-delay", "3", "--connect-timeout", "20", "--max-time", "1200", "--output", partial, url])
    os.replace(str(partial), str(path))


def main():
    account = pwd.getpwuid(os.getuid())
    if account.pw_name != "pwmat" or account.pw_dir != str(HOME) or HOME.resolve() != HOME:
        raise RuntimeError("Unexpected identity or canonical home")
    if not os.environ.get("SLURM_JOB_ID") or os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise RuntimeError("Installer requires an explicitly GPU-hidden CPU Slurm allocation")
    for path in (ROOT, ENV, RUNTIME):
        check_path(path)
    for path in (ROOT / "downloads", ROOT / "tmp", ROOT / "cache/pip", ROOT / "cache/huggingface", ROOT / "logs", ENV.parent, RUNTIME):
        check_path(path)
        path.mkdir(parents=True, exist_ok=True)
    os.environ.update({"HOME": str(HOME), "TMPDIR": str(ROOT / "tmp"), "PIP_CACHE_DIR": str(ROOT / "cache/pip"), "PIP_CONFIG_FILE": os.devnull, "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_REQUIRE_VIRTUALENV": "1", "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "HF_HOME": str(ROOT / "cache/huggingface"), "TOKENIZERS_PARALLELISM": "false", "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "NUMEXPR_NUM_THREADS": "2"})
    for variable in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PIP_USER", "PIP_TARGET", "PIP_PREFIX", "PIP_ROOT", "PIP_NO_INDEX", "PIP_FIND_LINKS"):
        os.environ.pop(variable, None)
    result = {"stage": "started", "job_id": os.environ["SLURM_JOB_ID"], "hostname": os.uname().nodename, "username": account.pw_name, "environment": str(ENV), "runtime": str(RUNTIME), "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"], "start_unix": time.time()}
    save(ROOT / "install_result.json", result)
    try:
        archive = ROOT / "downloads" / ARCHIVE
        checksum_file = archive.with_name(ARCHIVE + ".sha256")
        download(URL + ".sha256", checksum_file)
        expected_hash = re.search(r"\b[0-9a-fA-F]{64}\b", checksum_file.read_text(encoding="utf-8")).group(0).lower()
        if expected_hash != OFFICIAL_SHA256:
            raise RuntimeError("Published checksum differs from the independently verified official checksum")
        download(URL, archive)
        actual_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise RuntimeError("Official Python archive SHA-256 mismatch")
        result["python_archive_sha256"] = actual_hash
        interpreter = RUNTIME / "python/bin/python3"
        if not interpreter.exists():
            with tarfile.open(str(archive), "r:gz") as bundle:
                members = bundle.getmembers()
                for member in members:
                    destination = RUNTIME / member.name
                    if member.name.startswith("/") or os.path.commonpath([str(RUNTIME), os.path.abspath(str(destination))]) != str(RUNTIME):
                        raise RuntimeError("Archive member escapes runtime root")
                    if member.issym() or member.islnk():
                        link = destination.parent / member.linkname if member.issym() else RUNTIME / member.linkname
                        if member.linkname.startswith("/") or os.path.commonpath([str(RUNTIME), os.path.abspath(str(link))]) != str(RUNTIME):
                            raise RuntimeError("Archive link escapes runtime root")
                bundle.extractall(str(RUNTIME))
        run([interpreter, "-I", "-B", "-c", "import ssl,sqlite3,sys; assert sys.version_info[:3] == (3,12,3); print(sys.version); print(ssl.OPENSSL_VERSION); print(sqlite3.sqlite_version)"])
        if not (ENV / "bin/python").exists():
            if ENV.exists():
                raise RuntimeError("Environment target exists without a Python interpreter; preserve it for inspection")
            run([interpreter, "-I", "-B", "-m", "venv", ENV])
        python = ENV / "bin/python"
        pip = [python, "-I", "-B", "-m", "pip"]
        run(pip + ["install", "--index-url", "https://pypi.org/simple", "--only-binary=:all:", "pip==24.3.1", "setuptools==75.6.0", "wheel==0.45.1"])
        common = ["--index-url", "https://pypi.org/simple", "--extra-index-url", "https://download.pytorch.org/whl/cu118", "--constraint", str(ROOT / "constraints.txt"), "--timeout", "60", "--retries", "3"]
        run(pip + ["install"] + common + ["--only-binary=:all:", "--report", str(ROOT / "logs/pip-torch-report.json"), "torch==2.6.0+cu118"])
        run(pip + ["install"] + common + ["--only-binary=:all:", "--no-binary=rouge-score,sqlitedict,word2number", "--report", str(ROOT / "logs/pip-llm-report.json"), "--requirement", str(ROOT / "requirements-llm.txt")])
        run(pip + ["check"])
        freeze = run(pip + ["freeze", "--all"], stdout=subprocess.PIPE, universal_newlines=True).stdout
        (ROOT / "pip_freeze.txt").write_text(freeze, encoding="utf-8")
        run([python, "-I", "-B", ROOT / "cpu_check.py", "--output", ROOT / "cpu_check.json"])
        result.update({"stage": "completed", "end_unix": time.time(), "pip_check": "passed", "cpu_check": str(ROOT / "cpu_check.json"), "pip_freeze_sha256": hashlib.sha256(freeze.encode("utf-8")).hexdigest()})
        save(ROOT / "install_result.json", result)
    except BaseException as exc:
        result.update({"stage": "failed", "end_unix": time.time(), "error": type(exc).__name__ + ": " + str(exc), "traceback": traceback.format_exc()})
        save(ROOT / "install_result.json", result)
        raise


if __name__ == "__main__":
    main()
