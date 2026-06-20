from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .ids import new_id, utc_now
from .indexer import Index
from .model_contract import chat
from .tools import ToolError, registry
from .vault import Vault


@dataclass(frozen=True)
class AgentResult:
    task_id: str
    status: str
    steps: int
    path: str


SYSTEM_PROMPT = """You are the bounded Cogni Life OS agent.
Return JSON only.
Choose exactly one of:
{"tool": {"name": "...", "input": {...}}}
{"final": {"status": "completed|needs_clarification|quarantined", "summary": "...", "evidence": []}}
Never fabricate evidence. Prefer quarantine or clarification for ambiguity."""


def run_agent(settings: Settings, task_id: str, user_text: str) -> AgentResult:
    vault = Vault(settings.vault_path)
    vault.init()
    index = Index(settings.runtime_path / "index.sqlite3")
    tools = registry(vault, index)
    observations: list[dict[str, Any]] = []
    op_id = new_id("agent-op")

    for step in range(1, settings.max_agent_steps + 1):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"task_id": task_id, "input": user_text, "observations": observations[-4:]})},
        ]
        try:
            raw = chat(settings, messages)
            content = raw.get("choices", [{}])[0].get("message", {}).get("content")
            request = json.loads((content or "").strip())
        except Exception as exc:
            observations.append({"step": step, "error": "model_parse_failed", "detail": str(exc)})
            break

        if "final" in request:
            final = request["final"]
            path = f"00-system/tasks/{task_id}-result.md"
            vault.write_note(
                path,
                {"id": f"{task_id}-result", "type": "task_result", "task": task_id, "operation": op_id, "status": final.get("status", "completed"), "updated": utc_now()},
                f"# Task Result\n\n{final.get('summary', '')}\n\nEvidence: {final.get('evidence', [])}\n",
                expected_hash=None,
            )
            return AgentResult(task_id, final.get("status", "completed"), step, path)

        tool = request.get("tool", {})
        name = tool.get("name")
        payload = tool.get("input", {})
        if name not in tools:
            observations.append({"step": step, "error": "unknown_tool", "tool": name})
            continue
        try:
            observation = tools[name].run(payload)
        except ToolError as exc:
            observation = {"error": "tool_validation_failed", "detail": str(exc)}
        observations.append({"step": step, "tool": name, "observation": observation})

    qid = new_id("quarantine")
    path = f"00-system/quarantine/{qid}.md"
    vault.write_note(
        path,
        {"id": qid, "type": "quarantine_record", "task": task_id, "operation": op_id, "status": "quarantined", "created": utc_now()},
        f"# Quarantined Task\n\nTask: {task_id}\n\n```json\n{json.dumps(observations, indent=2)}\n```\n",
        expected_hash=None,
    )
    return AgentResult(task_id, "quarantined", len(observations), path)
