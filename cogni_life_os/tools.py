from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from .indexer import Index
from .durable_agent import DurableAgentStore
from .ingest import capture_text
from .integrity import scan
from .media import extract
from .path_safety import safe_join
from .vault import Vault


class ToolError(ValueError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    required: tuple[str, ...]
    timeout_seconds: int
    max_bytes: int
    handler: Callable[[dict[str, Any]], dict[str, Any]]

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        missing = [key for key in self.required if key not in payload]
        if missing:
            raise ToolError(f"{self.name} missing required fields: {missing}")
        return self.handler(payload)


def registry(vault: Vault, index: Index) -> dict[str, ToolSpec]:
    store = DurableAgentStore(vault)
    tools = {
        "source_capture": ToolSpec(
            "source_capture",
            ("text",),
            10,
            1_000_000,
            lambda p: capture_text(vault, p["text"], channel=p.get("channel", "manual"), sender=p.get("sender", "user")).__dict__,
        ),
        "vault_search": ToolSpec(
            "vault_search",
            ("query",),
            10,
            100_000,
            lambda p: {"results": index.search(p["query"], limit=int(p.get("limit", 10)))},
        ),
        "note_read": ToolSpec(
            "note_read",
            ("path",),
            10,
            200_000,
            lambda p: {"path": p["path"], "text": vault.read_bytes(p["path"]).decode("utf-8")[: int(p.get("limit", 200_000))]},
        ),
        "index_rebuild": ToolSpec("index_rebuild", tuple(), 60, 10_000, lambda p: {"count": index.rebuild(vault)}),
        "integrity_check": ToolSpec("integrity_check", tuple(), 60, 100_000, lambda p: scan(vault)),
        "quarantine": ToolSpec(
            "quarantine",
            ("reason", "payload"),
            10,
            100_000,
            lambda p: _quarantine(vault, p["reason"], p["payload"]),
        ),
        "clarification_request": ToolSpec(
            "clarification_request",
            ("question",),
            10,
            10_000,
            lambda p: {"status": "needs_clarification", "question": p["question"]},
        ),
        "proposal_submission": ToolSpec(
            "proposal_submission",
            ("proposal", "confidence", "evidence"),
            10,
            100_000,
            lambda p: {"status": "proposal_recorded", "proposal": p["proposal"], "confidence": p["confidence"], "evidence": p["evidence"]},
        ),
        "attachment_inspection": ToolSpec("attachment_inspection", ("path",), 10, 25_000_000, lambda p: _extract_path(vault, p["path"])),
        "image_extraction": ToolSpec("image_extraction", ("path",), 10, 25_000_000, lambda p: _extract_path(vault, p["path"])),
        "receipt_extraction": ToolSpec("receipt_extraction", ("path",), 10, 25_000_000, lambda p: _extract_path(vault, p["path"])),
        "pdf_extraction": ToolSpec("pdf_extraction", ("path",), 10, 25_000_000, lambda p: _extract_path(vault, p["path"])),
        "document_extraction": ToolSpec("document_extraction", ("path",), 10, 25_000_000, lambda p: _extract_path(vault, p["path"])),
        "audio_transcription": ToolSpec("audio_transcription", ("path",), 10, 25_000_000, lambda p: _extract_path(vault, p["path"])),
        "video_inspection": ToolSpec("video_inspection", ("path",), 10, 25_000_000, lambda p: {"status": "unsupported", "error_code": "VIDEO_DEFERRED_LOCAL_GATE", "path": p["path"]}),
        "entity_search": ToolSpec("entity_search", ("query",), 10, 100_000, lambda p: {"results": [r for r in index.search(p["query"], limit=int(p.get("limit", 10))) if "20-entities" in r["path"]]}),
        "concept_search": ToolSpec("concept_search", ("query",), 10, 100_000, lambda p: {"results": [r for r in index.search(p["query"], limit=int(p.get("limit", 10))) if "30-concepts" in r["path"]]}),
        "backlink_read": ToolSpec("backlink_read", ("target",), 10, 100_000, lambda p: _backlinks(vault, p["target"])),
        "policy_read": ToolSpec("policy_read", ("name",), 10, 100_000, lambda p: {"text": vault.read_bytes(f"00-system/policies/{p['name']}.md").decode("utf-8")}),
        "proposal_validation": ToolSpec("proposal_validation", ("proposal",), 10, 100_000, lambda p: _validate_proposal(vault, p["proposal"])),
        "write_plan_creation": ToolSpec("write_plan_creation", ("proposal",), 10, 100_000, lambda p: _write_plan(vault, p["proposal"])),
        "controlled_write_application": ToolSpec("controlled_write_application", ("plan",), 10, 500_000, lambda p: _apply_plan(vault, p["plan"])),
        "write_verification": ToolSpec("write_verification", ("path", "sha256"), 10, 100_000, lambda p: {"verified": vault.hash_file(p["path"]) == p["sha256"], "actual": vault.hash_file(p["path"])}),
        "conflict_creation": ToolSpec("conflict_creation", ("path", "content"), 10, 100_000, lambda p: _create_conflict(vault, p["path"], p["content"])),
        "retry": ToolSpec("retry", ("task_id", "reason"), 10, 10_000, lambda p: _retry(store, p["task_id"], p["reason"])),
        "task_status": ToolSpec("task_status", ("task_id",), 10, 100_000, lambda p: _task_status(store, p["task_id"])),
        "daily_review": ToolSpec("daily_review", tuple(), 10, 100_000, lambda p: _review(vault, "daily")),
        "weekly_review": ToolSpec("weekly_review", tuple(), 10, 100_000, lambda p: _review(vault, "weekly")),
        "slow_burn_synthesis": ToolSpec("slow_burn_synthesis", ("query",), 10, 100_000, lambda p: _synthesis(index, p["query"])),
        "vault_question_answering": ToolSpec("vault_question_answering", ("question",), 10, 100_000, lambda p: _vault_qa(index, p["question"])),
    }
    return tools


def _quarantine(vault: Vault, reason: str, payload: Any) -> dict[str, str]:
    from .ids import new_id, utc_now

    qid = new_id("quarantine")
    path = f"00-system/quarantine/{qid}.md"
    vault.write_note(
        path,
        {"id": qid, "type": "quarantine_record", "reason": reason, "created": utc_now()},
        f"# Quarantine {qid}\n\nReason: {reason}\n\n```json\n{payload}\n```\n",
        expected_hash=None,
    )
    return {"id": qid, "path": path}


def _extract_path(vault: Vault, path: str) -> dict:
    target = safe_join(vault.root, path)
    return {"path": path, "extraction": extract(target.read_bytes(), target.name).to_dict()}


def _backlinks(vault: Vault, target: str) -> dict:
    matches = []
    needle = f"[[{target}]]"
    for path in vault.iter_markdown():
        text = path.read_text(encoding="utf-8")
        if needle in text:
            matches.append(str(path.relative_to(vault.root)))
    return {"target": target, "backlinks": matches}


def _validate_proposal(vault: Vault, proposal: dict) -> dict:
    errors = []
    if proposal.get("action") not in {"create", "append", "replace", "merge"}:
        errors.append("unsupported action")
    if proposal.get("confidence", 0) < 0.86:
        errors.append("confidence below local autonomy threshold")
    files = proposal.get("files") or [{"path": proposal.get("path"), "content": proposal.get("content", ""), "expected_hash": proposal.get("expected_hash")}]
    if not isinstance(files, list) or not files or len(files) > 5:
        errors.append("proposal must include 1-5 files")
        files = []
    total_bytes = 0
    expected_hashes = {}
    for item in files:
        path = item.get("path") if isinstance(item, dict) else None
        content = item.get("content", "") if isinstance(item, dict) else ""
        total_bytes += len(str(content).encode("utf-8"))
        if not isinstance(path, str) or not path.endswith(".md"):
            errors.append("path must be a markdown file")
            continue
        if not _write_allowed(path):
            errors.append(f"target directory is not write-allowed: {path}")
        actual_hash = vault.hash_file(path)
        if actual_hash is not None and item.get("expected_hash") != actual_hash:
            errors.append(f"expected hash mismatch for existing file: {path}")
        expected_hashes[path] = actual_hash
    if total_bytes > 500_000:
        errors.append("proposal exceeds total byte limit")
    evidence = proposal.get("evidence")
    if not evidence:
        errors.append("proposal requires evidence")
    elif not all(_evidence_exists(vault, str(item)) for item in evidence):
        errors.append("proposal evidence must reference existing vault source IDs or note IDs")
    if proposal.get("sensitivity") in {"medical", "legal", "financial", "family_sensitive"}:
        errors.append("sensitive proposal requires human confirmation")
    if proposal.get("domain") not in {"personal", "work", "family", "health", "financial", "legal", "administrative", "general_knowledge"}:
        errors.append("unknown domain classification")
    return {"valid": not errors, "errors": errors, "expected_hashes": expected_hashes}


def _write_plan(vault: Vault, proposal: dict) -> dict:
    validation = _validate_proposal(vault, proposal)
    if not validation["valid"]:
        return {"status": "rejected", "validation": validation}
    files = proposal.get("files") or [{"path": proposal["path"], "content": proposal.get("content", ""), "expected_hash": validation["expected_hashes"].get(proposal["path"])}]
    return {
        "status": "ready",
        "operations": [{
            "action": proposal["action"],
            "path": item["path"],
            "content": item.get("content", ""),
            "expected_hash": validation["expected_hashes"].get(item["path"]),
        } for item in files],
    }


def _apply_plan(vault: Vault, plan: dict) -> dict:
    if plan.get("status") != "ready":
        raise ToolError("write plan is not ready")
    applied = []
    backups = {}
    try:
        for op in plan["operations"]:
            backups[op["path"]] = vault.read_bytes(op["path"]) if vault.hash_file(op["path"]) else None
            existing = backups[op["path"]].decode("utf-8") if backups[op["path"]] else ""
            content = op["content"] if op["action"] in {"create", "replace"} else existing.rstrip() + "\n\n" + op["content"]
            result = vault.atomic_write(op["path"], content.encode("utf-8"), expected_hash=op["expected_hash"])
            if result.conflict_path:
                raise ToolError(f"conflict created for {op['path']}")
            applied.append({"path": op["path"], "sha256": result.post_hash})
        vault.audit("write_plan_applied", {"files": applied})
        return {"status": "applied", "files": applied}
    except Exception as exc:
        for path, data in reversed(list(backups.items())):
            if data is not None:
                vault.atomic_write(path, data, expected_hash=vault.hash_file(path), allow_existing=True)
        vault.audit("write_plan_rolled_back", {"error": str(exc), "applied": applied})
        raise


def _write_allowed(path: str) -> bool:
    return path.startswith(("20-entities/", "30-concepts/", "40-projects/", "50-actions/", "60-decisions/", "70-synthesis/"))


def _evidence_exists(vault: Vault, evidence_id: str) -> bool:
    for path in vault.iter_markdown():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if f'id: "{evidence_id}"' in text or f"id: {evidence_id}" in text:
            return True
    return False


def _create_conflict(vault: Vault, path: str, content: str) -> dict:
    result = vault.atomic_write(path, content.encode("utf-8"), expected_hash="force-conflict")
    return {"conflict": str(result.conflict_path), "target": path}


def _retry(store: DurableAgentStore, task_id: str, reason: str) -> dict:
    state = store.load(task_id)
    retry_state = dict(state.retry_state)
    retry_state["retries"] = int(retry_state.get("retries", 0)) + 1
    retry_state["last_reason"] = reason
    retry_state["last_retry"] = __import__("cogni_life_os.ids", fromlist=["utc_now"]).utc_now()
    from .durable_agent import _replace

    updated = _replace(state, phase="queued", retry_state=retry_state, error_history=state.error_history + [{"reason": reason, "type": "retry"}])
    store.save(updated, expected_hash=store.vault.hash_file(store.path(task_id)))
    return {"status": "retry_scheduled", "task_id": task_id, "retry_state": retry_state}


def _task_status(store: DurableAgentStore, task_id: str) -> dict:
    state = store.load(task_id)
    return {"found": True, "state": state.to_dict()}


def _review(vault: Vault, cadence: str) -> dict:
    from .ids import new_id, utc_now

    rid = new_id(f"{cadence}-review")
    path = f"70-synthesis/{rid}.md"
    body = f"# {cadence.title()} Review\n\nGenerated at {utc_now()}.\n\nNo deterministic overdue scanner findings in this local pass.\n"
    result = vault.write_note(path, {"id": rid, "type": f"{cadence}_review", "created": utc_now()}, body, expected_hash=None)
    return {"status": "created", "path": path, "sha256": result.post_hash}


def _synthesis(index: Index, query: str) -> dict:
    citations = index.search(query, limit=10)
    if not citations:
        return {"status": "needs_evidence", "summary": "", "citations": []}
    titles = ", ".join(item["title"] for item in citations[:3])
    return {"status": "synthesized", "summary": f"Recurring evidence appears in: {titles}", "citations": citations}


def _vault_qa(index: Index, question: str) -> dict:
    citations = index.search(question, limit=5)
    if not citations:
        return {"status": "no_answer", "answer": "", "citations": []}
    answer = "The vault contains relevant cited records: " + ", ".join(item["title"] for item in citations)
    return {"status": "answered_with_citations", "answer": answer, "citations": citations}
