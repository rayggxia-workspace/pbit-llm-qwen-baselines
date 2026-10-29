#!/bin/bash
set -Ee -o pipefail
set +u
source "$HOME/.bashrc"
set -Eeu -o pipefail
exec /usr/bin/python3 -u "$P8_SOURCE/run.py"
