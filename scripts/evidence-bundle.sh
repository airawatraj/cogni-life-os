#!/usr/bin/env sh
set -eu
OUT="${1:-codex_local_candidate_review_v4.zip}"
rm -f "$OUT"
zip -qr "$OUT" \
  cogni_life_os \
  tests \
  scripts \
  docs \
  README.md \
  pyproject.toml \
  COGNI_LIFE_OS_FINAL_PRODUCTION_REQUIREMENTS.md \
  .cogni/local-candidate-evidence-v4 \
  -x '*.pyc' '*/__pycache__/*' '.cogni/runtime/*' '.cogni/backups/*'
printf '%s\n' "$OUT"
