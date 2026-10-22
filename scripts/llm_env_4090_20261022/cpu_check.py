"""Offline CPU import checks; never call CUDA helpers in this process."""

import argparse
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import pwd
import sys
import time
import traceback


def checked_output(value):
    identity = pwd.getpwuid(os.getuid())
    if identity.pw_name != "pwmat":
        raise RuntimeError("expected the authorized pwmat account")
    home = Path(identity.pw_dir).resolve(strict=True)
    if home != Path("/home/pwmat") or Path.home().resolve(strict=True) != home:
        raise RuntimeError("canonical account home differs from /home/pwmat")
    task = (home / "projects/llm-env-bootstrap-20261022").resolve(strict=True)
    if not task.is_relative_to(home) or task.stat().st_uid != os.getuid():
        raise RuntimeError("task root is not inside the authorized owned home")
    output = Path(value).expanduser().resolve()
    if output.parent != task or output.suffix != ".json":
        raise RuntimeError("output must be a JSON file directly in the verified task root")
    if output.exists() and output.stat().st_uid != os.getuid():
        raise RuntimeError("existing output is not owned by this account")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = checked_output(args.output)
    report = {
        "purpose": "offline CPU imports only; no GPU or model-quality validation",
        "status": "running", "started_unix": time.time(),
        "python": sys.version, "executable": sys.executable,
        "prefix": sys.prefix, "platform": platform.platform(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"), "checks": [],
    }

    def save():
        temporary = output.with_name(output.name + f".tmp-{os.getpid()}")
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
        temporary.replace(output)

    def record(name, details):
        report["checks"].append({"name": name, "status": "passed", "details": details})
        save()

    save()
    try:
        if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
            raise RuntimeError("CPU check requires explicitly empty CUDA_VISIBLE_DEVICES")
        if not os.environ.get("SLURM_JOB_ID"):
            raise RuntimeError("CPU check requires an allocated Slurm job")
        prefix = Path(sys.prefix).resolve(strict=True)
        if sys.prefix == sys.base_prefix or not prefix.is_relative_to(Path("/home/pwmat")):
            raise RuntimeError("an isolated environment under the verified personal home is required")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"
        record("CPU allocation and isolation", {"cuda_visible_devices": "", "prefix": str(prefix)})

        packages = [
            ("torch", "torch", "2.6.0+cu118"),
            ("transformers", "transformers", "4.45.2"),
            ("tokenizers", "tokenizers", "0.20.3"),
            ("safetensors", "safetensors", "0.4.5"),
            ("huggingface_hub", "huggingface-hub", "0.26.5"),
            ("accelerate", "accelerate", "1.0.1"),
            ("datasets", "datasets", "3.6.0"),
            ("pyarrow", "pyarrow", "17.0.0"),
            ("pandas", "pandas", "2.2.3"),
            ("scipy", "scipy", "1.13.1"),
            ("sklearn", "scikit-learn", "1.5.2"),
            ("numpy", "numpy", "1.26.4"),
            ("sentencepiece", "sentencepiece", "0.2.0"),
            ("numexpr", "numexpr", "2.10.0"),
            ("peft", "peft", "0.13.2"),
            ("evaluate", "evaluate", "0.4.3"),
            ("lm_eval.models.huggingface", "lm_eval", "0.4.8"),
        ]
        for module_name, distribution, expected in packages:
            report["active_check"] = module_name
            save()
            module = importlib.import_module(module_name)
            actual = importlib.metadata.version(distribution)
            path = Path(module.__file__).resolve(strict=True)
            if actual != expected:
                raise RuntimeError(f"{distribution}: expected {expected}, got {actual}")
            if not path.is_relative_to(prefix):
                raise RuntimeError(f"{module_name} imports from outside this isolated environment: {path}")
            record(module_name, {"version": actual, "file": str(path)})

        # torch.version.cuda is build metadata; this does not probe or initialize CUDA.
        import torch
        if torch.version.cuda != "11.8":
            raise RuntimeError(f"expected CUDA 11.8 build metadata, got {torch.version.cuda}")
        record("Torch build metadata", {"cuda_build": torch.version.cuda})
        report["status"] = "passed"
        report.pop("active_check", None)
    except BaseException as error:
        report["status"] = "failed"
        report["error"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
        report["finished_unix"] = time.time()
        save()
        raise
    report["finished_unix"] = time.time()
    save()
    print(json.dumps({"status": report["status"], "report": str(output), "checks": len(report["checks"])}))


if __name__ == "__main__":
    main()
