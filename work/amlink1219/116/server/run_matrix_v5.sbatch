#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=8
#SBATCH --mem=20G
#SBATCH --time=01:20:00
#SBATCH --output=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/matrix-v5-%j.out
#SBATCH --error=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/matrix-v5-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONIOENCODING=utf-8
root=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023
py=/home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/.venv/bin/python
stage=preflight
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$SLURM_JOB_ID" "$stage" "$rc" > "$root/matrix-v5-terminal.json"' EXIT
test "$(id -un)" = Weican_Chen
test "$(realpath "$root")" = "$root"
test -n "$SLURM_JOB_ID"
cd "$root"
printf 'f6c596f3d772dee19bea1d85badb25fe0088aefaaae70ab959555b68daf96cbf  cycle-source-v5.tar.gz\n' | sha256sum -c -
mkdir source-v5
tar -xzf cycle-source-v5.tar.gz -C source-v5
cd source-v5
"$py" - <<'PY'
from pathlib import Path
import hashlib,json,os,platform
manifest=json.loads(Path('../matrix_source_v5.json').read_text())
for name,expected in manifest['files'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==expected,name
Path('../matrix-v5-execution.json').write_text(json.dumps(dict(source=manifest,job_id=os.environ['SLURM_JOB_ID'],python=platform.python_version(),cuda_visible=os.environ['CUDA_VISIBLE_DEVICES']),indent=2)+'\n')
PY
stage=smoke_matrix
"$py" -m architecture_tlm.cycle_v1.matrix --suite smoke --workers 4 --output "$root/matrix-smoke-v5"
stage=real_matrix
set +e
"$py" -m architecture_tlm.cycle_v1.matrix --suite real --fixture-dir "$root/real_fixtures_v1" --workers 4 --output "$root/matrix-real-v5"
result_rc=$?
set -e
stage=archive
cd "$root"
tar -czf matrix-v5-results.tar.gz matrix-smoke-v5 matrix-real-v5 matrix-v5-execution.json
sha256sum matrix-v5-results.tar.gz > matrix-v5-results.tar.gz.sha256
stage=done
exit "$result_rc"
