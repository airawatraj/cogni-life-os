#!/usr/bin/env sh
set -eu
./scripts/config-validate.sh
./scripts/test.sh
./scripts/evaluate.sh
./scripts/real-multimodal-tests.sh
COGNI_RETRIEVAL_SIZES="${COGNI_RETRIEVAL_SIZES:-10000,50000,100000}" ./scripts/retrieval-eval.sh
COGNI_SOAK_SECONDS="${COGNI_SOAK_SECONDS:-120}" COGNI_SOAK_OPERATIONS="${COGNI_SOAK_OPERATIONS:-200000}" ./scripts/soak-test.sh
./scripts/live-model-test.sh
./scripts/integrity.sh
