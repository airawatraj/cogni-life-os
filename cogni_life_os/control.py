from __future__ import annotations

import json

from .ids import utc_now
from .vault import Vault


def set_control(vault: Vault, *, paused: bool | None = None, killed: bool | None = None) -> dict:
    path = "00-system/policies/runtime-control.md"
    current = {"paused": False, "killed": False}
    try:
        text = vault.read_bytes(path).decode("utf-8")
        current["paused"] = "paused: true" in text
        current["killed"] = "killed: true" in text
    except FileNotFoundError:
        pass
    if paused is not None:
        current["paused"] = paused
    if killed is not None:
        current["killed"] = killed
    vault.write_note(
        path,
        {"id": "policy-runtime-control", "type": "policy", "updated": utc_now(), **current},
        f"# Runtime Control\n\n```json\n{json.dumps(current, indent=2, sort_keys=True)}\n```\n",
        expected_hash=vault.hash_file(path),
        allow_existing=True,
    )
    vault.audit("runtime_control_updated", current)
    return current
