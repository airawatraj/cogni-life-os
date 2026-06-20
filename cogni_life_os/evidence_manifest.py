from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .model_contract import validate_evidence_schema


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(evidence_dir: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    repo_root = Path.cwd()
    files = []
    for path in sorted(evidence_dir.rglob("*")):
        if path.is_file():
            display_path = str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else str(path)
            files.append({"path": display_path, "sha256": file_sha256(path), "size_bytes": path.stat().st_size})
    display_dir = str(evidence_dir.relative_to(repo_root)) if evidence_dir.is_relative_to(repo_root) else str(evidence_dir)
    manifest = {"schema_version": 1, "evidence_dir": display_dir, "files": files}
    target = manifest_path or evidence_dir / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def validate_matrix_evidence(matrix_path: Path, repo_root: Path) -> dict[str, Any]:
    rows = _matrix_rows(matrix_path)
    errors: list[str] = []
    checked = []
    for row in rows:
        status = row.get("Status", "")
        evidence_cell = row.get("Evidence", "")
        paths = [part.strip(" `") for part in evidence_cell.split(",") if ".cogni/" in part]
        if status == "PASS" and not paths:
            errors.append(f"{row.get('Requirement ID')} PASS row has no concrete evidence path")
        for rel in paths:
            path = repo_root / rel
            if not path.exists():
                errors.append(f"missing evidence path: {rel}")
                continue
            checked.append(rel)
            if path.suffix == ".json":
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    errors.append(f"unparseable evidence JSON {rel}: {exc}")
                    continue
                if "live-model" in path.name or row.get("Requirement ID") == "20":
                    schema_errors = validate_evidence_schema(data)
                    if schema_errors:
                        errors.extend(f"{rel}: {err}" for err in schema_errors)
                    if data.get("scenario_count") != len(data.get("results", [])):
                        errors.append(f"{rel}: hidden or mismatched live scenarios")
                    if data.get("failed", 0) and status == "PASS":
                        errors.append(f"{rel}: PASS row hides failed live scenarios")
                elif path.name != "matrix-validation.json" and status == "PASS" and data.get("passed") is False:
                    errors.append(f"{rel}: PASS row contradicts raw evidence")
    return {"checked_paths": checked, "errors": errors, "passed": not errors}


def _matrix_rows(matrix_path: Path) -> list[dict[str, str]]:
    lines = [line.strip() for line in matrix_path.read_text(encoding="utf-8").splitlines() if line.strip().startswith("|")]
    if len(lines) < 3:
        return []
    headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows
