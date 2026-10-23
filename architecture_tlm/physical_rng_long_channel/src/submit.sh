#!/usr/bin/env bash
set -eo pipefail
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")"
root=$(pwd -P)
stage="${1:-pilot}"
parent="${2:-}"
case "$stage" in
    pilot) if [[ -n "$parent" ]]; then printf 'pilot takes no parent\n' >&2; exit 2; fi ;;
    calibrate|long) if [[ ! -d "$parent" ]]; then printf 'Use: bash submit.sh %s /absolute/previous/results/JOB_STAGE\n' "$stage" >&2; exit 2; fi
        parent=$(cd "$parent" && pwd -P) ;;
    *) printf 'Use: bash submit.sh pilot | calibrate PARENT | long PARENT\n' >&2; exit 2 ;;
esac
workers="${STUDY_WORKERS:-8}"
case "$workers" in [1-8]) ;; *) printf 'STUDY_WORKERS must be 1..8\n' >&2; exit 2 ;; esac
effective="${STUDY_EFFECTIVE_SECONDS:-1}"
case "$effective" in 1|4) ;; *) printf 'STUDY_EFFECTIVE_SECONDS must be 1 or 4\n' >&2; exit 2 ;; esac
python3 -B "$root/run_long.py" --verify
python3 -B -m unittest discover -s "$root" -p 'test_long.py' -v
if [[ "$stage" != pilot ]]; then python3 -B "$root/run_long.py" --validate-parent --stage "$stage" --parent "$parent"; fi
mkdir -p submissions logs results
submission=$(mktemp -d "$root/submissions/longchannel-XXXXXXXX")
snapshot="$submission/source"
python3 -B "$root/run_long.py" --snapshot-source "$snapshot"
python3 -B "$snapshot/run_long.py" --verify
chmod -R a-w "$snapshot"
export STUDY_ROOT="$root" STUDY_SOURCE="$snapshot" STUDY_STAGE="$stage" STUDY_PARENT="$parent"
export STUDY_WORKERS="$workers" STUDY_EFFECTIVE_SECONDS="$effective"
export STUDY_WALLTIME="${STUDY_WALLTIME:-3-00:00:00}"
job=$(sbatch --parsable -p "${STUDY_PARTITION:-v6_384}" -N 1 --ntasks=1 \
    --cpus-per-task="$workers" --mem="${STUDY_MEMORY:-16G}" --time="$STUDY_WALLTIME" \
    --job-name="longch_${stage}" --chdir="$root" --output="$root/logs/${stage}-%j.out" \
    --error="$root/logs/${stage}-%j.err" --export=ALL "$snapshot/run_job.sh")
job="${job%%;*}"
printf 'JOB=%s\nSTAGE=%s\nCPUS=%s\nSOURCE=%s\nPARENT=%s\nRESULTS=%s/results/%s_%s\nARCHIVE=%s/long_channel_%s_%s.tar.gz\n' \
    "$job" "$stage" "$workers" "$snapshot" "$parent" "$root" "$job" "$stage" "$root" "$job" "$stage" \
    | tee "$root/logs/submission-${job}.txt"
printf 'No automatic downstream job submitted. Review measured cost and gates before next stage.\n'
