from __future__ import annotations

from pathlib import Path


class PathSafetyError(ValueError):
    pass


def safe_join(root: Path, relative: str | Path) -> Path:
    if Path(relative).is_absolute():
        raise PathSafetyError(f"absolute paths are not allowed: {relative}")
    root = root.resolve()
    target = (root / relative).resolve()
    if root != target and root not in target.parents:
        raise PathSafetyError(f"path escapes vault: {relative}")
    return target


def assert_not_icloud(path: Path) -> None:
    marker = str(path).lower()
    forbidden = ("icloud", "mobile documents", "com~apple~clouddocs")
    if any(part in marker for part in forbidden):
        raise PathSafetyError(f"development vault must not be in iCloud: {path}")
