#!/bin/bash
#SBATCH --job-name=pbit-sram-cal
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
#SBATCH --output=calibration-%j.log
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
: "${CACTI_SOURCE:?Set CACTI_SOURCE to the directory containing cache.cfg and cacti}"
python3 sram_cacti_calibration_v1.py run-cacti --reference "${CALIBRATION_REFERENCE:-results/sram_calibration_v1_20261016/reference_points.json}" \
 --source "$CACTI_SOURCE" --output "${CALIBRATION_RAW_OUTPUT:-results/sram_calibration_v1_20261016/rerun_raw}"
