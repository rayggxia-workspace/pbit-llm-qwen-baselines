#!/bin/bash
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=01:30:00
set -euo pipefail
cd /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/resource_b01058f7/source
/usr/bin/python3 -B -u architecture_tlm/unified_v6/probes/resource_pipeline_gate.py --bridge /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/hbm_43b7b1ff/build/pbit_hbm_bridge --output /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/resource_b01058f7/gate
