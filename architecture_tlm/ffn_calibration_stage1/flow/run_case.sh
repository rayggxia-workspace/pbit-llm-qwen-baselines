#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 2 || $1 != --env ]]; then
  echo 'Usage: bash flow/run_case.sh --env /absolute/env.sh --case-id ID --corner ss|tt --output-root /absolute/new-runs [--with-pt-sta]' >&2
  exit 2
fi
environment_file=$2
shift 2
[[ -f "$environment_file" ]] || { echo 'Missing environment setup file' >&2; exit 2; }
environment_file=$(cd -- "$(dirname -- "$environment_file")" && printf '%s/%s' "$PWD" "$(basename -- "$environment_file")")
# The user owns this setup script; it may source their licensed tool setup.
source "$environment_file"
export FLOW_ENV_FILE="$environment_file"
: "${STD_DB:?Set STD_DB to one SS or TT .db in the environment file}"
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "${PYTHON:-python3}" "$script_dir/run_case.py" "$@"
