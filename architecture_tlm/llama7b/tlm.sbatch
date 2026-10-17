#!/bin/bash
#SBATCH --job-name=llama7b-tlm
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=04:00:00
#SBATCH --output=logs/tlm-%A_%a.log
set -euo pipefail
project=${SLURM_SUBMIT_DIR}
backend=${TLM_BACKEND:-link}
python_bin=/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python
bridge=/home/Hongjie_Zeng/projects/pbit-pv-stream-v6-20261016/build/pbit_dram_bridge_sg_v6_audit
args=(--backend "$backend" --index "$SLURM_ARRAY_TASK_ID"
 --trace-dir "$project/outputs/traces"
 --output "$project/outputs/$backend")
if [[ "$backend" == dramsys ]]; then
 args+=(--bridge "$bridge" --dram-config "$project/architecture_tlm/llama7b/dram/configs/ddr4_2ch_2rank_Staggered_core_limits.json")
fi
"$python_bin" "$project/architecture_tlm/llama7b/verify_snapshot.py"
"$python_bin" "$project/architecture_tlm/llama7b/sweep.py" "${args[@]}"
