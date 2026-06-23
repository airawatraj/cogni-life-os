from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .ids import new_id, sha256_bytes, utc_now
from .markdown import note
from .path_safety import safe_join


VAULT_DIRS = [
    "00-system/audit",
    "00-system/conflicts",
    "00-system/dashboards",
    "00-system/evaluations",
    "00-system/policies",
    "00-system/quarantine",
    "00-system/tasks",
    "10-sources/text",
    "10-sources/attachments",
    "20-entities/people",
    "20-entities/orgs",
    "30-concepts",
    "40-projects",
    "50-actions",
    "60-decisions",
    "70-synthesis",
]

MAX_WRITE_BYTES = 5 * 1024 * 1024
PROTECTED_PREFIXES = ("00-system/audit/",)


@dataclass(frozen=True)
class WriteResult:
    path: Path
    pre_hash: str | None
    post_hash: str
    conflict_path: Path | None = None


class Vault:
    def __init__(self, root: Path, *, max_write_bytes: int = MAX_WRITE_BYTES):
        self.root = root
        self.max_write_bytes = max_write_bytes

    def init(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for item in VAULT_DIRS:
            safe_join(self.root, item).mkdir(parents=True, exist_ok=True)
        self.write_note(
            "00-system/policies/autonomy.md",
            {
                "id": "policy-autonomy",
                "type": "policy",
                "status": "active",
                "updated": utc_now(),
            },
            "\n".join(
                [
                    "# Autonomy Policy",
                    "",
                    "- global_pause: false",
                    "- default_level: 1",
                    "- level_2_confidence_threshold: 0.86",
                    "- level_3_requires_policy: true",
                    "- level_4_requires_confirmation: true",
                    "- quiet_hours: []",
                ]
            ),
            expected_hash=None,
            allow_existing=True,
        )
        self.write_note(
            "00-system/dashboards/traffic-light.md",
            {
                "id": "dashboard-traffic-light",
                "type": "dashboard",
                "status": "green",
                "updated": utc_now(),
            },
            "# Traffic Light Dashboard\n\n| Indicator | Status | Evidence |\n| --- | --- | --- |\n| ingestion_health | green | [[policy-autonomy]] |\n| backlog | green | no queued tasks |\n| conflicts | green | no conflicts |\n| retrieval_health | amber | index awaits first rebuild |\n| model_tool_health | amber | live contract not yet run |\n",
            expected_hash=None,
            allow_existing=True,
        )

    def read_bytes(self, relative: str | Path) -> bytes:
        return safe_join(self.root, relative).read_bytes()

    def hash_file(self, relative: str | Path) -> str | None:
        path = safe_join(self.root, relative)
        if not path.exists():
            return None
        return sha256_bytes(path.read_bytes())

    def write_note(
        self,
        relative: str | Path,
        frontmatter: dict,
        body: str,
        *,
        expected_hash: str | None,
        allow_existing: bool = False,
    ) -> WriteResult:
        content = note(frontmatter, body).encode("utf-8")
        return self.atomic_write(relative, content, expected_hash=expected_hash, allow_existing=allow_existing)

    def atomic_write(
        self,
        relative: str | Path,
        data: bytes,
        *,
        expected_hash: str | None,
        allow_existing: bool = False,
    ) -> WriteResult:
        relative_text = str(relative).replace("\\", "/")
        if len(data) > self.max_write_bytes:
            raise ValueError(f"write exceeds bounded size limit: {len(data)} > {self.max_write_bytes}")
        if any(relative_text.startswith(prefix) for prefix in PROTECTED_PREFIXES):
            raise PermissionError(f"protected path cannot be written through atomic_write: {relative}")
        target = safe_join(self.root, relative)
        if target.exists() and target.is_symlink():
            raise PermissionError(f"refusing to overwrite symlink: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        pre_hash = sha256_bytes(target.read_bytes()) if target.exists() else None
        if target.exists() and not allow_existing and expected_hash != pre_hash:
            conflict_rel = Path("00-system/conflicts") / f"{new_id('conflict')}-{target.name}"
            conflict = safe_join(self.root, conflict_rel)
            conflict.write_bytes(data)
            self.audit("conflict_created", {"target": str(relative), "conflict": str(conflict_rel), "pre_hash": pre_hash})
            return WriteResult(target, pre_hash, sha256_bytes(data), conflict)

        tmp = target.with_name(f".{target.name}.{new_id('tmp')}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)
        post_hash = sha256_bytes(target.read_bytes())
        expected_post = sha256_bytes(data)
        if post_hash != expected_post:
            raise IOError(f"read-back verification failed for {relative}")
        self.audit("write_applied", {"path": str(relative), "pre_hash": pre_hash, "post_hash": post_hash})
        return WriteResult(target, pre_hash, post_hash)

    def rollback(self, relative: str | Path, backup_relative: str | Path) -> WriteResult:
        backup = safe_join(self.root, backup_relative)
        if not backup.exists():
            raise FileNotFoundError(str(backup_relative))
        result = self.atomic_write(relative, backup.read_bytes(), expected_hash=self.hash_file(relative), allow_existing=True)
        self.audit("rollback_applied", {"path": str(relative), "backup": str(backup_relative), "post_hash": result.post_hash})
        return result

    def audit(self, event: str, data: dict) -> None:
        path = safe_join(self.root, "00-system/audit/audit.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": utc_now(), "event": event, **data}
        import json

        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def iter_markdown(self):
        for path in self.root.rglob("*.md"):
            if path.name.startswith("."):
                continue
            yield path
