from __future__ import annotations

import argparse
import json
from pathlib import Path

from .backup import create_backup, restore_backup
from .auth import TokenStore
from .config import settings
from .control import set_control
from .evaluation import run as run_eval
from .indexer import Index
from .ingest import capture_text
from .integrity import scan
from .model_contract import run_probes
from .retrieval_eval import run as run_retrieval_eval
from .server import serve
from .soak import run as run_soak
from .vault import Vault


def main(argv: list[str] | None = None) -> None:
    cfg = settings()
    parser = argparse.ArgumentParser(prog="cogni")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-vault")
    start = sub.add_parser("start")
    start.add_argument("--host", default=cfg.bind_host)
    start.add_argument("--port", type=int, default=cfg.port)
    cap = sub.add_parser("capture-text")
    cap.add_argument("text")
    sub.add_parser("index-rebuild")
    sub.add_parser("integrity")
    sub.add_parser("backup")
    restore = sub.add_parser("restore")
    restore.add_argument("manifest")
    restore.add_argument("target")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--live-model", action="store_true")
    sub.add_parser("model-contract")
    sub.add_parser("pause")
    sub.add_parser("resume")
    sub.add_parser("kill-switch")
    retrieval = sub.add_parser("retrieval-eval")
    retrieval.add_argument("--sizes", default="10000")
    soak = sub.add_parser("soak")
    soak.add_argument("--duration", type=float, default=2.0)
    soak.add_argument("--operations", type=int, default=200)
    issue = sub.add_parser("issue-token")
    issue.add_argument("--subject", default="local-user")
    issue.add_argument("--ttl", type=int, default=3600)

    args = parser.parse_args(argv)
    vault = Vault(cfg.vault_path)
    index = Index(cfg.runtime_path / "index.sqlite3")

    if args.cmd == "init-vault":
        vault.init()
        print(json.dumps({"vault": str(cfg.vault_path), "status": "initialized"}, indent=2))
    elif args.cmd == "start":
        serve(cfg, args.host, args.port)
    elif args.cmd == "capture-text":
        vault.init()
        result = capture_text(vault, args.text)
        index.rebuild(vault)
        print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    elif args.cmd == "index-rebuild":
        vault.init()
        print(json.dumps({"count": index.rebuild(vault)}, indent=2))
    elif args.cmd == "integrity":
        vault.init()
        print(json.dumps(scan(vault), indent=2, sort_keys=True))
    elif args.cmd == "backup":
        vault.init()
        print(json.dumps(create_backup(vault, cfg.backup_path), indent=2, sort_keys=True))
    elif args.cmd == "restore":
        print(json.dumps(restore_backup(Path(args.manifest), Path(args.target), cfg.runtime_path / "restored-index.sqlite3"), indent=2, sort_keys=True))
    elif args.cmd == "evaluate":
        print(json.dumps(run_eval(cfg, live_model=args.live_model), indent=2, sort_keys=True))
    elif args.cmd == "model-contract":
        print(json.dumps(run_probes(cfg), indent=2, sort_keys=True))
    elif args.cmd == "pause":
        vault.init()
        print(json.dumps(set_control(vault, paused=True), indent=2, sort_keys=True))
    elif args.cmd == "resume":
        vault.init()
        print(json.dumps(set_control(vault, paused=False, killed=False), indent=2, sort_keys=True))
    elif args.cmd == "kill-switch":
        vault.init()
        print(json.dumps(set_control(vault, paused=True, killed=True), indent=2, sort_keys=True))
    elif args.cmd == "retrieval-eval":
        sizes = [int(part) for part in args.sizes.split(",") if part]
        print(json.dumps(run_retrieval_eval(sizes), indent=2, sort_keys=True))
    elif args.cmd == "soak":
        print(json.dumps(run_soak(args.duration, args.operations), indent=2, sort_keys=True))
    elif args.cmd == "issue-token":
        print(TokenStore(cfg.runtime_path / "tokens.json").issue(args.subject, args.ttl))
