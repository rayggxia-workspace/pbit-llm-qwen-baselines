#!/bin/bash
#SBATCH --job-name=pbit186-integrate
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -euo pipefail
cd /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/full_bab9721d/source
exec /usr/bin/python3 -B -u architecture_tlm/unified_v6/probes/schedule_integration_gate.py --bridge /home/Hongjie_Zeng/projects/pbit-pv-stream-v6-20261016/build/pbit_dram_bridge_sg_v6_audit --output /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/full_bab9721d/gate
