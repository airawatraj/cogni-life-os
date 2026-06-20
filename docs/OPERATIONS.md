# Operations

## Install

No third-party packages are required for the current scaffold.

```bash
./scripts/install.sh
```

## Start

```bash
./scripts/start.sh
```

Open `http://127.0.0.1:8765` and enter the token.

## Test And Evaluate

```bash
./scripts/test.sh
./scripts/evaluate.sh
python3 -m cogni_life_os model-contract
```

Use `python3 -m cogni_life_os evaluate --live-model` only when the DGX Spark endpoint is reachable.
