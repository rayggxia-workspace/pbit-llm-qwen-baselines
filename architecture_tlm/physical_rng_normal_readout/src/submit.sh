#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
export STUDY_PYTHON="${STUDY_PYTHON:-/usr/bin/python3}" PYTHONDONTWRITEBYTECODE=1
"$STUDY_PYTHON" -B run_normal.py --verify
"$STUDY_PYTHON" -B -m unittest discover -s . -p test_normal.py -v
root=$(pwd -P)
mkdir -p submissions results logs
exec 9>"$root/.submit.lock"
flock -n 9 || { printf 'Submission already in progress\n' >&2; exit 2; }
if compgen -G "$root/logs/submission-*.txt" >/dev/null; then printf 'Existing run: inspect it before requesting another study\n' >&2; exit 2; fi
snapshot=$(mktemp -d "$root/submissions/normal-XXXXXXXX")/source
"$STUDY_PYTHON" -B run_normal.py --snapshot "$snapshot"
chmod -R a-w "$snapshot"
export STUDY_ROOT="$root" STUDY_SOURCE="$snapshot" STUDY_WORKERS=8 STUDY_MAX_HOURS=6
export NORMAL_SOURCE_COMMIT="${NORMAL_SOURCE_COMMIT:-MANIFEST_ONLY}"
job=$(sbatch --parsable -p "${STUDY_PARTITION:-v6_384}" -N 1 --ntasks=1 --cpus-per-task=8 --mem=16G --time=06:15:00 \
    --job-name=normal_rng --chdir="$root" --output="$root/logs/study-%j.out" --error="$root/logs/study-%j.err" --export=ALL "$snapshot/run_job.sh")
job="${job%%;*}"
printf 'JOB=%s\nSOURCE=%s\nRESULTS=%s/results/%s\nARCHIVE=%s/normal_readout_%s.tar.gz\nCPUS=8 WORKERS=8 APS_THREADS_PER_CASE=1 COMPUTE_BUDGET_HOURS=6\n' \
    "$job" "$snapshot" "$root" "$job" "$root" "$job" | tee "$root/logs/submission-$job.txt"
