from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .ids import sha256_bytes, stable_id, utc_now
from .markdown import parse_frontmatter
from .vault import Vault


PHASES = {"queued", "model_request_pending", "tool_intent_persisted", "tool_executed", "completed", "quarantined", "failed"}


@dataclass(frozen=True)
class DurableAgentState:
    task_id: str
    source_id: str
    phase: str
    step: int
    attempts: int
    lease_owner: str | None
    lease_expiry: str | None
    last_checkpoint: str | None
    pending_model_request: dict[str, Any] | None
    model_response_status: str | None
    deterministic_operation_id: str | None
    canonical_tool_arguments: dict[str, Any] | None
    operation_state: str | None
    proposal_state: str | None
    write_plan_state: str | None
    expected_hashes: dict[str, str | None]
    completed_side_effects: list[dict[str, Any]]
    retry_state: dict[str, Any]
    error_history: list[dict[str, Any]]
    final_status: str | None
    quarantine_reason: str | None
    created: str
    updated: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def deterministic_operation_id(task_id: str, source_id: str, tool_name: str, canonical_arguments: dict[str, Any], action_scope: str) -> str:
    return stable_id("op", task_id, source_id, tool_name, canonical_json(canonical_arguments), action_scope)


class DurableAgentStore:
    def __init__(self, vault: Vault):
        self.vault = vault

    def path(self, task_id: str) -> str:
        return f"00-system/tasks/{task_id}.md"

    def create(self, task_id: str, source_id: str) -> DurableAgentState:
        now = utc_now()
        state = DurableAgentState(
            task_id=task_id,
            source_id=source_id,
            phase="queued",
            step=0,
            attempts=0,
            lease_owner=None,
            lease_expiry=None,
            last_checkpoint=None,
            pending_model_request=None,
            model_response_status=None,
            deterministic_operation_id=None,
            canonical_tool_arguments=None,
            operation_state=None,
            proposal_state=None,
            write_plan_state=None,
            expected_hashes={},
            completed_side_effects=[],
            retry_state={"retries": 0},
            error_history=[],
            final_status=None,
            quarantine_reason=None,
            created=now,
            updated=now,
        )
        self.save(state, expected_hash=self.vault.hash_file(self.path(task_id)))
        return state

    def load(self, task_id: str) -> DurableAgentState:
        raw = self.vault.read_bytes(self.path(task_id)).decode("utf-8")
        _fm, body = parse_frontmatter(raw)
        start = body.find("```json")
        end = body.find("```", start + 7)
        if start == -1 or end == -1:
            raise ValueError("malformed durable task record")
        data = json.loads(body[start + 7 : end].strip())
        if data.get("phase") not in PHASES:
            raise ValueError("invalid durable task phase")
        return DurableAgentState(**data)

    def save(self, state: DurableAgentState, *, expected_hash: str | None) -> None:
        if state.phase not in PHASES:
            raise ValueError("invalid durable task phase")
        data = state.to_dict()
        data["updated"] = utc_now()
        body = "# Durable Task State\n\n```json\n" + json.dumps(data, indent=2, sort_keys=True) + "\n```\n"
        self.vault.write_note(
            self.path(state.task_id),
            {"id": state.task_id, "type": "task", "source": state.source_id, "phase": state.phase, "updated": data["updated"]},
            body,
            expected_hash=expected_hash,
            allow_existing=True,
        )

    def acquire_lease(self, task_id: str, owner: str, seconds: int = 60) -> DurableAgentState:
        state = self.load(task_id)
        if state.lease_expiry and _parse_ts(state.lease_expiry) > datetime.now(timezone.utc) and state.lease_owner != owner:
            raise RuntimeError("task lease is held by another worker")
        updated = _replace(state, lease_owner=owner, lease_expiry=(datetime.now(timezone.utc) + timedelta(seconds=seconds)).replace(microsecond=0).isoformat().replace("+00:00", "Z"))
        self.save(updated, expected_hash=self.vault.hash_file(self.path(task_id)))
        return updated

    def persist_model_request(self, state: DurableAgentState, request: dict[str, Any]) -> DurableAgentState:
        updated = _replace(state, phase="model_request_pending", step=state.step + 1, attempts=state.attempts + 1, pending_model_request=_redact(request), model_response_status="pending", last_checkpoint="model_request_persisted")
        self.save(updated, expected_hash=self.vault.hash_file(self.path(state.task_id)))
        return updated

    def persist_tool_intent(self, state: DurableAgentState, tool_name: str, args: dict[str, Any], action_scope: str, expected_hashes: dict[str, str | None]) -> DurableAgentState:
        op_id = deterministic_operation_id(state.task_id, state.source_id, tool_name, args, action_scope)
        updated = _replace(
            state,
            phase="tool_intent_persisted",
            deterministic_operation_id=op_id,
            canonical_tool_arguments=json.loads(canonical_json({"tool": tool_name, "args": args, "scope": action_scope})),
            operation_state="intent_persisted",
            expected_hashes=expected_hashes,
            last_checkpoint="tool_intent_persisted",
        )
        self.save(updated, expected_hash=self.vault.hash_file(self.path(state.task_id)))
        return updated

    def mark_side_effect(self, state: DurableAgentState, side_effect: dict[str, Any]) -> DurableAgentState:
        effects = list(state.completed_side_effects)
        effect_id = sha256_bytes(canonical_json(side_effect).encode("utf-8"))
        if not any(item.get("effect_id") == effect_id for item in effects):
            effects.append({"effect_id": effect_id, **side_effect})
        updated = _replace(state, phase="tool_executed", operation_state="verified", completed_side_effects=effects, last_checkpoint="side_effect_verified")
        self.save(updated, expected_hash=self.vault.hash_file(self.path(state.task_id)))
        return updated

    def complete(self, state: DurableAgentState, status: str = "completed") -> DurableAgentState:
        if state.final_status == status and state.phase == "completed":
            return state
        updated = _replace(state, phase="completed", final_status=status, last_checkpoint="completed")
        self.save(updated, expected_hash=self.vault.hash_file(self.path(state.task_id)))
        return updated

    def quarantine(self, task_id: str, reason: str) -> DurableAgentState:
        try:
            state = self.load(task_id)
        except Exception:
            state = self.create(task_id, "unknown-source")
        updated = _replace(state, phase="quarantined", final_status="quarantined", quarantine_reason=reason, error_history=state.error_history + [{"ts": utc_now(), "reason": reason}])
        self.save(updated, expected_hash=self.vault.hash_file(self.path(task_id)))
        return updated

    def recover(self, task_id: str, owner: str) -> DurableAgentState:
        try:
            state = self.acquire_lease(task_id, owner)
        except ValueError as exc:
            return self.quarantine(task_id, f"malformed task record: {exc}")
        if state.phase == "model_request_pending":
            return _replace(state, model_response_status="unknown_after_restart", last_checkpoint="recover_model_request")
        if state.phase == "tool_intent_persisted":
            return _replace(state, operation_state="ready_to_execute_after_restart", last_checkpoint="recover_before_tool")
        if state.phase == "tool_executed":
            return self.complete(state)
        return state


def _replace(state: DurableAgentState, **changes: Any) -> DurableAgentState:
    data = state.to_dict()
    data.update(changes)
    data["updated"] = utc_now()
    return DurableAgentState(**data)


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _redact(request: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(json.dumps(request))
    for key in ("api_key", "authorization", "Authorization"):
        if key in redacted:
            redacted[key] = "[REDACTED]"
    return redacted
