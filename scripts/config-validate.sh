#!/usr/bin/env sh
set -eu
python3 - <<'PY'
from cogni_life_os.config import settings
from cogni_life_os.path_safety import assert_not_icloud
cfg = settings()
assert_not_icloud(cfg.vault_path)
assert cfg.vault_path.name == "local_test_vault"
assert cfg.service_token != "", "service token must not be empty"
print({"status": "pass", "vault": str(cfg.vault_path), "model": cfg.model_base_url})
PY
