"""Issue182: real persistent DRAMSys DMA throughput and runtime smoke matrix.

Only synthetic contiguous reads; no Qwen model/PPL or chip measurement claim.
The existing bridge drains at each DMA boundary. Every case uses one process,
preserving DRAM state across all of that case's requests.
"""
import argparse
import hashlib
import json
import os
import platform
import resource
import subprocess
import time
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_bytes((json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def run_case(args, case, output):
    name, dma_bytes, total_bytes, policy = case
    config = args.source / ("ddr4_2ch_2rank_" + policy + "_core_limits.json")
    folder = output / name
    folder.mkdir()
    log = (folder / "bridge.log").open("w", encoding="utf-8", newline="\n")
    trace = (folder / "requests.jsonl").open("w", encoding="utf-8", newline="\n")
    begin = time.perf_counter()
    proc = subprocess.Popen([str(args.bridge), str(config), "32"], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=log, text=True, bufsize=1)

    def read():
        while True:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("bridge exited early: " + name)
            if line.lstrip().startswith("{"):
                return json.loads(line)
            log.write(line)

    try:
        ready = read()
        launch_wall = time.perf_counter() - begin
        assert ready["status"] == "ready"
        assert ready["memory_bytes"] == 16 * 1024**3
        done = 0.0
        access_start = time.perf_counter()
        count = total_bytes // dma_bytes
        assert count * dma_bytes == total_bytes
        for i in range(count):
            request = dict(op="access", id=i+1, ready_ns=done, address=65536+i*dma_bytes,
                           bytes=dma_bytes, write=False)
            proc.stdin.write(json.dumps(request) + "\n")
            proc.stdin.flush()
            response = read()
            assert response["id"] == i+1
            assert response["burst_count"] == dma_bytes // 64
            assert response["done_ns"] >= done
            trace.write(json.dumps(dict(request=request, response=response)) + "\n")
            done = response["done_ns"]
        access_wall = time.perf_counter() - access_start
        finish_start = time.perf_counter()
        end_ns = done + 1000.0
        proc.stdin.write(json.dumps(dict(op="finish", end_ns=end_ns)) + "\n")
        proc.stdin.flush()
        final = read()
        status = proc.wait(timeout=60)
        assert status == 0 and final["status"] == "finished"
        assert final["burst_count"] == total_bytes // 64
        assert final["read_bursts"] == total_bytes // 64 and final["write_bursts"] == 0
        finish_wall = time.perf_counter() - finish_start
        core = sum(ch["core_J"] for ch in final["power_at_system_end"].values())
        interface = sum(ch["interface_J"] for ch in final["power_at_system_end"].values())
        result = dict(case=name, dma_bytes=dma_bytes, total_bytes=total_bytes, macro_requests=count,
            bursts=total_bytes//64, simulated_access_ns=done, simulated_end_ns=final["end_ns"],
            simulated_GBps=total_bytes/done, launch_wall_seconds=launch_wall,
            access_wall_seconds=access_wall, finish_wall_seconds=finish_wall,
            total_wall_seconds=time.perf_counter()-begin,
            simulator_bursts_per_wall_second=(total_bytes//64)/access_wall,
            simulator_payload_bytes_per_wall_second=total_bytes/access_wall,
            core_J=core, uncalibrated_interface_J=interface, core_pJ_per_byte=core/total_bytes*1e12,
            peak_pending=final["peak_pending"], ready=ready, policy=policy,
            bridge_path=str(args.bridge), bridge_sha256=sha(args.bridge),
            configuration_path=str(config), configuration_sha256=sha(config), max_pending=32,
            traffic="synthetic contiguous read only, no compute gaps, no model evaluation",
            energy_scope="source-backed Micron current-limit core scenario; not measured typical power; IO/PHY uncalibrated",
            queue_policy="existing persistent bridge; each macro DMA drains; 1ns issue frontend",
            final=final)
        save(folder / "result.json", result)
        print(json.dumps({k: result[k] for k in ("case", "total_bytes", "simulated_GBps", "access_wall_seconds", "core_J", "peak_pending")}), flush=True)
        return result
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        trace.close()
        log.close()
        proc.stdin.close()
        proc.stdout.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--bridge", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((args.source / "source_manifest.json").read_text())
    for name, expected in manifest["files"].items():
        assert sha(args.source / name) == expected, "source changed: " + name
    cpu = next((line.strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")), "unavailable")
    save(args.output / "execution.json", dict(source_manifest=manifest,
         source_manifest_sha256=sha(args.source / "source_manifest.json"),
         argv=os.sys.argv, hostname=platform.node(), python=platform.python_version(),
         platform=platform.platform(), cpu=cpu, slurm_job_id=os.getenv("SLURM_JOB_ID"),
         source_script_sha256=sha(__file__), started_unix=time.time()))
    cases = [("single_32KiB", 32768, 32768, "Staggered"),
             ("single_64KiB", 65536, 65536, "Staggered"),
             ("single_128KiB", 131072, 131072, "Staggered"),
             ("dma32KiB_total64MiB", 32768, 64*1024**2, "Staggered"),
             ("dma64KiB_total64MiB", 65536, 64*1024**2, "Staggered"),
             ("dma128KiB_total64MiB", 131072, 64*1024**2, "Staggered"),
             ("contiguous512MiB", 512*1024**2, 512*1024**2, "Staggered"),
             ("no_pd_contiguous64MiB", 64*1024**2, 64*1024**2, "NoPowerDown")]
    rows = []
    for case in cases:
        rows.append(run_case(args, case, args.output))
        save(args.output / "progress.json", dict(completed=[r["case"] for r in rows], planned=len(cases)))
    summary = [{k: r[k] for k in r if k != "final"} for r in rows]
    save(args.output / "summary.json", summary)
    hashes = {str(f.relative_to(args.output)): dict(bytes=f.stat().st_size, sha256=sha(f))
              for f in sorted(args.output.rglob("*")) if f.is_file()}
    save(args.output / "manifest.json", dict(files=hashes, completed=len(rows), expected=len(cases),
         finished_unix=time.time(), max_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))


if __name__ == "__main__":
    main()
