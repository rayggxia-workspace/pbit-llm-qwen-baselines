#!/bin/bash
set -Ee -o pipefail
set +u
source "$HOME/.bashrc"
set -Eeu -o pipefail
: "${AC_SNAPSHOT:?}" "${AC_RUN_ROOT:?}" "${AC_TARGET_DB:?}"
export AC_PYTHON=/usr/bin/python3
exec "$AC_PYTHON" -u "$AC_SNAPSHOT/runner.py" "${AC_STAGE:-dc}" "${SLURM_ARRAY_TASK_ID:-2}"
