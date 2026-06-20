from __future__ import annotations

import json
import platform
import tempfile
from pathlib import Path

from .backup import create_backup, file_hashes, restore_backup, verify_backup
from .config import Settings
from .ids import new_id, utc_now
from .indexer import Index
from .ingest import capture_text
from .integrity import scan
from .model_contract import run_probes
from .path_safety import PathSafetyError, safe_join
from .vault import Vault


def record(settings: Settings, result: dict) -> Path:
    settings.evidence_path.mkdir(parents=True, exist_ok=True)
    path = settings.evidence_path / f"{result['evaluation_id']}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return path


def run(settings: Settings, *, live_model: bool = False) -> dict:
    vault = Vault(settings.vault_path)
    vault.init()
    index = Index(settings.runtime_path / "index.sqlite3")
    results: list[dict] = []

    def add(requirement_id: str, name: str, severity: str, passed: bool, actual: object, expected: str, status: str | None = None) -> None:
        item_status = status or ("PASS" if passed else "FAIL")
        item = {
            "evaluation_id": new_id("eval"),
            "requirement_id": requirement_id,
            "test_name": name,
            "severity": severity,
            "test_data": "synthetic local development vault",
            "expected_result": expected,
            "actual_result": actual,
            "pass": passed,
            "status": item_status,
            "logs": [],
            "evidence_path": "",
            "timestamp": utc_now(),
            "model_version": settings.model_name,
            "code_version": "0.1.0",
            "environment": {"python": platform.python_version(), "platform": platform.platform()},
        }
        item["evidence_path"] = str(record(settings, item))
        results.append(item)

    cap = capture_text(vault, "Synthetic insurance renewal commitment for evaluation.")
    add("9", "source preservation", "critical", bool(cap.source_id), cap.__dict__, "source and task records created")

    count = index.rebuild(vault)
    add("16", "index rebuild", "critical", count > 0, {"count": count}, "index contains vault notes")

    integrity = scan(vault)
    add("7", "integrity scan", "critical", integrity["status"] == "pass", integrity, "no duplicate IDs, corrupt notes, or broken links")

    try:
        safe_join(vault.root, "../escape.md")
        path_passed = False
    except PathSafetyError:
        path_passed = True
    add("8.2", "path traversal defense", "critical", path_passed, {"blocked": path_passed}, "path escape rejected")

    pre_backup_hashes = file_hashes(vault.root)
    manifest = create_backup(vault, settings.backup_path)
    manifest_path = Path(manifest["archive"]).with_suffix("").with_suffix(".json")
    with tempfile.TemporaryDirectory() as tmp:
        restored = restore_backup(manifest_path, Path(tmp) / "restore", Path(tmp) / "restore-index.sqlite3")
    restored["hashes_match"] = pre_backup_hashes == restored["hashes"]
    verified = verify_backup(manifest_path) and restored["integrity"]["status"] == "pass" and restored["hashes_match"]
    add("22", "backup restore rehearsal", "critical", verified, restored, "backup verifies, restores, hashes match, integrity passes, index rebuilds")

    if live_model:
        probes = run_probes(settings)
        passed = all(item["status"] == "pass" for item in probes["results"])
        add("2", "live Cogni-Brain contract", "high", passed, probes, "all live probes pass")
    else:
        add("2", "live Cogni-Brain contract", "high", False, {"status": "UNVERIFIED", "reason": "live model not requested"}, "repeated live probes pass", status="UNVERIFIED")

    summary = {
        "run_id": new_id("eval-run"),
        "timestamp": utc_now(),
        "total": len(results),
        "passed": sum(1 for r in results if r["pass"]),
        "failed": [r for r in results if r["status"] == "FAIL"],
        "unverified": [r for r in results if r["status"] == "UNVERIFIED"],
        "results": results,
    }
    summary_path = settings.evidence_path / f"{summary['run_id']}.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    vault.write_note(
        f"00-system/evaluations/{summary['run_id']}.md",
        {"id": summary["run_id"], "type": "evaluation_run", "created": summary["timestamp"], "status": "pass" if not summary["failed"] else "fail"},
        f"# Evaluation {summary['run_id']}\n\nPassed {summary['passed']} of {summary['total']} checks.\n\nEvidence: `{summary_path}`\n",
        expected_hash=None,
    )
    return summary
