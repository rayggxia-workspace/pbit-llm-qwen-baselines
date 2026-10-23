#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/gqa_validation_v1/validation-%j.out
#SBATCH --error=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/gqa_validation_v1/validation-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=''
export PYTHONIOENCODING=utf-8
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
task_root=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/gqa_validation_v1
python=/home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/.venv/bin/python
fixture=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/gqa_capture_v1/private_fixture/qwen_layer12_gqa7_context64.json
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"exit_code\":%d,\"gpu_requested\":false}\n" "$SLURM_JOB_ID" "$rc" > "$task_root/terminal.json"' EXIT
cd "$task_root/source"
"$python" -P -X utf8 "$task_root/verify_staged_source.py" "$task_root"
for mode in exact pv winner rejection; do
  "$python" -X utf8 -m architecture_tlm.cycle_v1.run_gqa \
    --fixture "$fixture" --mode "$mode" --samples 32 --seed 0 \
    --output "$task_root/private_runs/$mode" --public-report
done
"$python" -X utf8 -m architecture_tlm.cycle_v1.run_gqa \
  --fixture "$fixture" --mode exact --samples 32 --seed 0 \
  --k-slots 1 --v-slots 1 --operand-slots 1 --memory-window 1 \
  --output "$task_root/private_runs/exact_narrow" --public-report
"$python" -X utf8 -m architecture_tlm.cycle_v1.audit.verify_gqa_fixture \
  --fixture "$fixture" \
  --expected-fixture-sha256 ee5722b38a1acb94daf4d09e49651c9a4610dbc9a9b0ac444b29bb1ef2280080 \
  --private-trace-dir "$task_root/private_audit" --output "$task_root/public_audit.json"
