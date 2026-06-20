#!/usr/bin/env sh
set -eu
python3 -m cogni_life_os soak --duration "${COGNI_SOAK_SECONDS:-2}" --operations "${COGNI_SOAK_OPERATIONS:-200}"
