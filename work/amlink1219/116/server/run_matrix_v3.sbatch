#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=8
#SBATCH --mem=20G
#SBATCH --time=01:20:00
#SBATCH --output=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/matrix-v3-%j.out
#SBATCH --error=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/matrix-v3-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONIOENCODING=utf-8
root=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023
py=/home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/.venv/bin/python
stage=preflight
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$SLURM_JOB_ID" "$stage" "$rc" > "$root/matrix-v3-terminal.json"' EXIT
test "$(id -un)" = Weican_Chen
test "$(realpath "$root")" = "$root"
test -n "$SLURM_JOB_ID"
cd "$root"
printf 'f333fd849e347d73e456a459b5878260f6ae2aa91d79f5e1f7dce7c2b95937be  cycle-source-v3.tar.gz\n' | sha256sum -c -
mkdir source-v3
tar -xzf cycle-source-v3.tar.gz -C source-v3
cd source-v3
"$py" - <<'PY'
from pathlib import Path
import hashlib,json,os,platform
manifest=json.loads(Path('../matrix_source_v3.json').read_text())
for name,expected in manifest['files'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==expected,name
Path('../matrix-v3-execution.json').write_text(json.dumps(dict(source=manifest,job_id=os.environ['SLURM_JOB_ID'],python=platform.python_version(),cuda_visible=os.environ['CUDA_VISIBLE_DEVICES']),indent=2)+'\n')
PY
stage=smoke_matrix
"$py" -m architecture_tlm.cycle_v3.matrix --suite smoke --workers 4 --output "$root/matrix-smoke-v3"
stage=real_matrix
set +e
"$py" -m architecture_tlm.cycle_v3.matrix --suite real --fixture-dir "$root/real_fixtures_v1" --workers 4 --output "$root/matrix-real-v3"
result_rc=$?
set -e
stage=archive
cd "$root"
tar -czf matrix-v3-results.tar.gz matrix-smoke-v3 matrix-real-v3 matrix-v3-execution.json
sha256sum matrix-v3-results.tar.gz > matrix-v3-results.tar.gz.sha256
stage=done
exit "$result_rc"
