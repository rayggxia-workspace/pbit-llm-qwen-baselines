"""Process-local OpenMP compatibility for old glibc; no system changes."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import shlex
import subprocess
import time
import traceback


HOME = Path("/home/pwmat")
ROOT = HOME / "projects/llm-env-bootstrap-20261022"
ENV = HOME / "envs/llm-qwen-py312-cu118"


def safe(path):
    assert os.path.commonpath([str(HOME), str(path.resolve())]) == str(HOME)
    assert path.parent.stat().st_uid == os.getuid()
    if path.exists():
        assert path.stat().st_uid == os.getuid()


def save(path, value):
    safe(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


def main():
    account = pwd.getpwuid(os.getuid())
    assert account.pw_name == "pwmat" and account.pw_dir == str(HOME) and HOME.resolve() == HOME
    assert os.environ.get("SLURM_JOB_ID") and os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    safe(ROOT)
    safe(ENV)
    assert ENV.is_dir() and (ENV / "bin/python").is_file()
    libraries = sorted({path.resolve() for path in (ENV / "lib/python3.12/site-packages/scikit_learn.libs").glob("libgomp*.so*")})
    assert len(libraries) == 1, "Expected exactly one personal sklearn OpenMP library"
    for library in libraries:
        safe(library)
        assert os.path.commonpath([str(ENV), str(library)]) == str(ENV)
    wrapper = ENV / "bin/llm-python"
    preload = ":".join(str(path) for path in libraries)
    contents = "#!/bin/bash\nset -euo pipefail\nexport LD_PRELOAD=" + shlex.quote(preload) + "\nexport OMP_NUM_THREADS=\"${SLURM_CPUS_PER_TASK:-2}\"\nexport MKL_NUM_THREADS=\"${SLURM_CPUS_PER_TASK:-2}\"\nexport OPENBLAS_NUM_THREADS=\"${SLURM_CPUS_PER_TASK:-2}\"\nexport NUMEXPR_NUM_THREADS=\"${SLURM_CPUS_PER_TASK:-2}\"\nexec " + shlex.quote(str(ENV / "bin/python")) + " \"$@\"\n"
    safe(wrapper)
    if wrapper.exists():
        assert wrapper.read_text(encoding="utf-8") == contents, "Refusing to replace a different existing wrapper"
    else:
        with wrapper.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(contents)
        wrapper.chmod(0o700)
    subprocess.run(["/bin/bash", "-n", str(wrapper)], check=True)
    report = {"status": "started", "job_id": os.environ["SLURM_JOB_ID"], "hostname": os.uname().nodename, "wrapper": str(wrapper), "wrapper_sha256": hashlib.sha256(wrapper.read_bytes()).hexdigest(), "preloaded_libraries": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in libraries], "scope": "Only this environment's llm-python process; no system/profile/shared-library changes", "start_unix": time.time()}
    save(ROOT / "compat_runtime.json", report)
    try:
        env = dict(os.environ)
        env.update({"TMPDIR": str(ROOT / "tmp"), "HF_HOME": str(ROOT / "cache/huggingface"), "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "PYTHONNOUSERSITE": "1"})
        for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
            env.pop(key, None)
        subprocess.run([str(wrapper), "-I", "-B", str(ROOT / "cpu_check.py"), "--output", str(ROOT / "cpu_check_compat.json")], env=env, check=True)
        check = "import json,pathlib,torch,sklearn,threadpoolctl; from sklearn.metrics import accuracy_score; assert accuracy_score([0,1,1],[0,1,1])==1.0; print(json.dumps({\"threadpools\":threadpoolctl.threadpool_info(),\"openmp_maps\":[line for line in pathlib.Path(\"/proc/self/maps\").read_text().splitlines() if \"libgomp\" in line]}))"
        result = subprocess.run([str(wrapper), "-I", "-B", "-c", check], env=env, check=True, stdout=subprocess.PIPE, universal_newlines=True)
        report["threadpools"] = json.loads(result.stdout)
        report["status"] = "passed"
        report["cpu_check"] = str(ROOT / "cpu_check_compat.json")
    except BaseException as exc:
        report.update({"status": "failed", "error": type(exc).__name__ + ": " + str(exc), "traceback": traceback.format_exc()})
        save(ROOT / "compat_runtime.json", report)
        raise
    report["end_unix"] = time.time()
    save(ROOT / "compat_runtime.json", report)
    print(json.dumps({"status": report["status"], "wrapper": str(wrapper), "preload": preload}))


if __name__ == "__main__":
    main()
