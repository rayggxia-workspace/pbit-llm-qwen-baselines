#!/bin/bash
#SBATCH --job-name=pbit186-sg
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:10:00
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
cd /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/sg_gate_d3a79d95/source
/usr/bin/python3 -B -c 'import json,hashlib,pathlib;m=json.loads(pathlib.Path("work/jieruiz/186/SG_SOURCE.json").read_text());assert all(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==v["sha256"] for p,v in m["files"].items())'
exec /usr/bin/python3 -B -u architecture_tlm/unified_v6/probes/dram_sg_probe.py --bridge /home/Hongjie_Zeng/projects/pbit-pv-stream-v6-20261016/build/pbit_dram_bridge_sg_v6_audit --config architecture_tlm/unified_v6/configs/dramsys/ddr4_2ch_2rank_NoPowerDown_core_limits.json --output /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/sg_gate_d3a79d95/results --commit d3a79d95af6c8b252aa2f4856a746a9f87146da4
