from __future__ import annotations

import json
import tarfile
import time
from pathlib import Path

from .indexer import Index
from .ids import new_id, sha256_bytes, utc_now
from .integrity import scan
from .path_safety import PathSafetyError
from .vault import Vault


def create_backup(vault: Vault, backup_root: Path) -> dict:
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_id = new_id("backup")
    archive = backup_root / f"{backup_id}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(vault.root, arcname=vault.root.name)
    digest = sha256_bytes(archive.read_bytes())
    manifest = {
        "id": backup_id,
        "created": utc_now(),
        "archive": str(archive),
        "sha256": digest,
        "rpo": "last successful backup",
        "rto": "restore archive and rebuild index",
    }
    (backup_root / f"{backup_id}.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    vault.audit("backup_created", manifest)
    return manifest


def verify_backup(manifest_path: Path) -> bool:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archive = Path(manifest["archive"])
    return archive.exists() and sha256_bytes(archive.read_bytes()) == manifest["sha256"]


def file_hashes(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): sha256_bytes(path.read_bytes()) for path in root.rglob("*") if path.is_file()}


def restore_backup(manifest_path: Path, target: Path, index_path: Path | None = None) -> dict:
    started = time.monotonic()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archive = Path(manifest["archive"])
    if not verify_backup(manifest_path):
        raise ValueError("backup archive hash does not match manifest")
    if target.exists() and any(target.iterdir()):
        raise FileExistsError("restore target must be empty")
    target.mkdir(parents=True, exist_ok=True)
    target_root = target.resolve()
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            destination = (target / member.name).resolve()
            if target_root != destination and target_root not in destination.parents:
                raise PathSafetyError(f"archive member escapes restore target: {member.name}")
        tar.extractall(target)
    restored_dirs = [path for path in target.iterdir() if path.is_dir()]
    if len(restored_dirs) != 1:
        raise ValueError("backup archive must contain exactly one vault directory")
    restored_vault = Vault(restored_dirs[0])
    hashes_before_verification = file_hashes(restored_vault.root)
    integrity = scan(restored_vault)
    rebuilt = None
    if index_path is not None:
        rebuilt = Index(index_path).rebuild(restored_vault)
    return {
        "restored_vault": str(restored_vault.root),
        "integrity": integrity,
        "index_rebuilt_count": rebuilt,
        "hashes": hashes_before_verification,
        "hashes_after_verification": file_hashes(restored_vault.root),
        "duration_seconds": round(time.monotonic() - started, 4),
    }
