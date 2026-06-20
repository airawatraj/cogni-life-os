#!/usr/bin/env sh
set -eu
if [ -z "${COGNI_SERVICE_TOKEN:-}" ]; then
  COGNI_SERVICE_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  export COGNI_SERVICE_TOKEN
fi
python3 -m cogni_life_os start --host "${COGNI_HOST:-127.0.0.1}" --port "${COGNI_PORT:-8765}"
