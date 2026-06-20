#!/usr/bin/env sh
set -eu
python3 -m cogni_life_os retrieval-eval --sizes "${COGNI_RETRIEVAL_SIZES:-10000}"
