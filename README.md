# Cogni Life OS

Local-first Life OS backed by an Obsidian-compatible Markdown vault.

This branch uses only the fresh local disposable vault at `local_test_vault`.
iCloud, production vault activation, physical iPhone validation, remote private transport, and cross-device conflict testing remain deferred gates.

## Commands

```bash
./scripts/install.sh
./scripts/start.sh
./scripts/test.sh
./scripts/evaluate.sh
./scripts/index-rebuild.sh
./scripts/integrity.sh
python3 -m cogni_life_os capture-text "Remember to renew insurance next week"
```

## Configuration

Defaults are in `cogni_life_os/config.py`.

- Development vault: `local_test_vault`
- Runtime cache/indexes: `.cogni/runtime`
- Backups: `.cogni/backups`
- Model endpoint: `http://192.168.20.91:8000/v1`
- Model API key: `local`

The local PWA/API binds to loopback by default and requires `COGNI_SERVICE_TOKEN` or an issued local token.
