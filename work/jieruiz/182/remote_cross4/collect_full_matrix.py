"""Verify all Issue182 full-model artifacts and package only small evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tarfile
import time


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_bytes((json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--job", type=Path, required=True)
    p.add_argument("--array", required=True)
    a = p.parse_args()
    out = a.job/("collection_" + os.environ["SLURM_JOB_ID"])
    out.mkdir(exist_ok=False)
    submission = json.loads((a.job/"ARRAY_SUBMISSION.json").read_text())
    manifest = json.loads((a.job/"source/work/jieruiz/182/SOURCE_MANIFEST.json").read_text())
    changed = [rel for rel,e in manifest["files"].items()
               if sha(a.job/"source"/rel) != e["sha256"]]
    rows, errors, raw, small = [], [], [], []
    for i, case in enumerate(submission["cases"]):
        directory = a.job/"results"/(a.array+"_"+str(i)+"_"+case)
        entry = dict(case=case, array_task=a.array+"_"+str(i), remote_directory=str(directory))
        for suffix in ("out", "err"):
            log = a.job/"logs"/("full-"+a.array+"_"+str(i)+"."+suffix)
            if log.exists():
                small.append(log)
                if suffix == "err" and log.stat().st_size:
                    entry["stderr"] = log.read_text()[-8000:]
        try:
            m = json.loads((directory/"MANIFEST.json").read_text())
            assert m["status"] == "completed" and m["case"] == case
            for name, expected in m["files"].items():
                f = directory/name
                assert f.stat().st_size == expected["bytes"] and sha(f) == expected["sha256"], name
                raw.append(dict(path=str(f), bytes=f.stat().st_size, sha256=expected["sha256"], case=case))
            result = json.loads((directory/"RESULT.json").read_text())
            d = result["DRAM"]["details"]
            bursts = sum(v for k,v in result["DRAM"]["traffic"].items() if k.endswith("_bursts"))
            assert result["DRAM"]["backend"] == "dramsys" and d["status"] == "finished"
            assert bursts == d["burst_count"] == d["read_bursts"] + d["write_bursts"]
            assert result["model"]["num_hidden_layers"] == 36
            assert result["config"]["random"]["backend"] == "integrated_service"
            assert result["config"]["digital_weight_chunk_bytes"] == 65536
            assert result["execution_commit"] == manifest["commit"]
            assert d["configuration_sha256"] == "ddbdd1aee7f20d5e3eaf12d73b7e300894ad3ab5cc50ae2a8aa5fd121b2fa419"
            assert result["metrics"]["full_physical_energy_J"] is None
            if result["config"]["ffn"]["mode"] == "sc":
                assert result["FFN_activity"]["SC_64x64_tiles"] == 656640
                expected_cross = ((result["model"]["hidden_size"]//64-1)+(result["model"]["intermediate_size"]//64-1))*result["model"]["num_hidden_layers"]
                assert result["FFN_contract"]["weight_pipeline"]["counts"]["cross_input_group_prefetches"] == expected_cross
                assert not result["FFN_contract"]["weight_pipeline"]["pending"]
            entry.update(status="verified", manifest_sha256=sha(directory/"MANIFEST.json"),
                result_sha256=sha(directory/"RESULT.json"), files_verified=len(m["files"]),
                wall_seconds=result["wall_seconds"], metrics=result["metrics"],
                phase_ns=result["phase_ns"], energy_J=result["energy_J"],
                DRAM_traffic=result["DRAM"]["traffic"], DRAM_burst_count=bursts,
                DRAM_peak_pending=d["peak_pending"], SRAM=result["SRAM"],
                FFN_activity=result["FFN_activity"], weight_pipeline=result["FFN_contract"]["weight_pipeline"], unpriced_actions=result["unpriced_actions"],
                ff_mode=result["config"]["ffn"]["mode"], ff_engines=result["config"]["ffn"]["engines"],
                attention_mode=result["config"]["attention"]["mode"],
                double_buffer=result["config"]["double_buffer"],
                digital_weight_chunk_bytes=result["config"]["digital_weight_chunk_bytes"],
                sc_weight_chunk_bytes=result["config"]["weight_chunk_bytes"])
            small += [directory/"RESULT.json", directory/"EXECUTION.json", directory/"MANIFEST.json"]
        except Exception as e:
            entry.update(status="incomplete_or_failed", error=type(e).__name__+": "+str(e))
            errors.append(dict(case=case, error=entry["error"]))
            for name in ("EXECUTION.json", "RESULT.json", "MANIFEST.json"):
                if (directory/name).exists():small.append(directory/name)
        rows.append(entry)
    save(out/"SUMMARY.json", rows)
    save(out/"RAW_REMOTE_INDEX.json", raw)
    verification = dict(source_commit=manifest["commit"], source_files_checked=len(manifest["files"]),
        changed_source_files=changed, expected=len(submission["cases"]),
        verified=sum(r["status"]=="verified" for r in rows), errors=errors,
        array_job=a.array, collector_job=os.environ["SLURM_JOB_ID"],
        completed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        accounting="sacct unavailable: accounting storage disabled; completion verified from result artifacts",
        raw_trace_policy="request JSONL gzip remains at exact remote paths in RAW_REMOTE_INDEX.json",
        scientific_boundary="full 36-layer synthetic decode TLM with actual DRAMSys; no PPL/RTL/STA/physical chip measurement")
    save(out/"VERIFICATION.json", verification)
    small += [a.job/"ARRAY_SUBMISSION.json", a.job/"SMOKE_SUBMISSION.json",
              a.job/"RUNTIME_PROVENANCE.json", a.job/"full_matrix.sbatch", a.job/"smoke.sbatch",
              a.job/"smoke_full_decode.py", a.job/"collect_full_matrix.py", a.job/"COLLECTOR_SUBMISSION.json",
              a.job/"source/work/jieruiz/182/SOURCE_MANIFEST.json",
              a.job/"smoke/2930/SUMMARY.json", a.job/"smoke/2930/MANIFEST.json",
              out/"SUMMARY.json", out/"RAW_REMOTE_INDEX.json", out/"VERIFICATION.json"]
    small += [a.job/n for n in ("RESOURCE_CHECK.json", "SOURCE_DELTA_FROM_FIRST_ROUND.json", "REMOTE_EXECUTION_ENVIRONMENT.json", "EXECUTION_COMMANDS.json")]
    index = {str(f.relative_to(a.job)): dict(bytes=f.stat().st_size, sha256=sha(f), remote_path=str(f))
             for f in small}
    save(out/"SMALL_EVIDENCE_INDEX.json", index)
    small.append(out/"SMALL_EVIDENCE_INDEX.json")
    package = out/"SMALL_EVIDENCE.tar.gz"
    with tarfile.open(package, "w:gz") as tf:
        for f in small:tf.add(f, arcname=str(f.relative_to(a.job)), recursive=False)
    receipt = dict(package=str(package), bytes=package.stat().st_size, sha256=sha(package),
                   verified=verification["verified"], expected=verification["expected"],
                   source_changed=bool(changed), collector_job=os.environ["SLURM_JOB_ID"])
    save(out/"PACKAGE_RECEIPT.json", receipt)
    print(json.dumps(receipt), flush=True)
    if changed or errors:raise SystemExit(2)


if __name__ == "__main__":
    main()
