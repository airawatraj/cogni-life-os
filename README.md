# Cogni Life OS

Local-first Life OS scaffold backed by an Obsidian-compatible Markdown vault.

This session uses only the fresh local development vault at `vaults/dev-vault`.
iCloud and production vaults are intentionally out of scope until production gates pass.

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

- Development vault: `vaults/dev-vault`
- Runtime cache/indexes: `.cogni/runtime`
- Backups: `.cogni/backups`
- Model endpoint: `http://192.168.20.91:8000/v1`
- Model API key: `local`

The PWA is private and local by default. It requires the service token printed at startup or set with `COGNI_SERVICE_TOKEN`.
