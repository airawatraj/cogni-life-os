from __future__ import annotations

from dataclasses import dataclass

from pathlib import Path

from .ids import sha256_bytes, stable_id, utc_now
from .media import extract, sanitize_filename
from .vault import Vault


@dataclass(frozen=True)
class CaptureResult:
    source_id: str
    task_id: str
    source_path: str
    task_path: str
    duplicate: bool


def capture_text(vault: Vault, text: str, *, channel: str = "manual", sender: str = "user") -> CaptureResult:
    data = text.encode("utf-8")
    digest = sha256_bytes(data)
    source_id = stable_id("source", channel, sender, digest)
    task_id = stable_id("task", source_id, "ingest")
    source_path = f"10-sources/text/{source_id}.md"
    task_path = f"00-system/tasks/{task_id}.md"
    duplicate = vault.hash_file(source_path) is not None
    if not duplicate:
        vault.write_note(
            source_path,
            {
                "id": source_id,
                "type": "raw_source",
                "channel": channel,
                "sender": sender,
                "received": utc_now(),
                "mime_type": "text/plain",
                "sha256": digest,
                "extraction_status": "complete",
                "extraction_method": "direct_text",
                "confidence": "1.0",
                "history": [{"ts": utc_now(), "event": "captured"}],
            },
            f"# Source {source_id}\n\n## Original Text\n\n{text}\n",
            expected_hash=None,
        )
        vault.write_note(
            task_path,
            {
                "id": task_id,
                "type": "task",
                "source": source_id,
                "status": "queued",
                "created": utc_now(),
                "updated": utc_now(),
                "max_steps": 8,
            },
            f"# Task {task_id}\n\n- Source: [[{source_id}]]\n- Status: queued\n",
            expected_hash=None,
        )
    vault.audit("source_captured", {"source_id": source_id, "task_id": task_id, "duplicate": duplicate})
    return CaptureResult(source_id, task_id, source_path, task_path, duplicate)


def capture_binary(vault: Vault, data: bytes, original_filename: str, *, channel: str = "upload", sender: str = "user") -> dict:
    digest = sha256_bytes(data)
    safe_name = sanitize_filename(original_filename)
    source_id = stable_id("source", channel, sender, digest)
    task_id = stable_id("task", source_id, "ingest")
    extraction = extract(data, safe_name)
    suffix = Path(safe_name).suffix or ".bin"
    storage_name = f"{source_id}{suffix}"
    attachment_path = f"10-sources/attachments/{storage_name}"
    source_path = f"10-sources/text/{source_id}.md"
    task_path = f"00-system/tasks/{task_id}.md"
    duplicate = vault.hash_file(source_path) is not None
    if not duplicate:
        vault.atomic_write(attachment_path, data, expected_hash=None)
        vault.write_note(
            source_path,
            {
                "id": source_id,
                "type": "raw_source",
                "channel": channel,
                "sender": sender,
                "received": utc_now(),
                "original_filename": original_filename,
                "display_filename": safe_name,
                "storage_filename": storage_name,
                "mime_type": extraction.detected_mime,
                "size": len(data),
                "sha256": digest,
                "attachment": attachment_path,
                "extraction_status": extraction.status,
                "extraction_method": extraction.extractor,
                "warnings": extraction.warnings,
                "errors": extraction.error_code,
                "derived_records": [],
            },
            "\n".join(
                [
                    f"# Source {source_id}",
                    "",
                    f"- Attachment: [[{attachment_path}]]",
                    f"- Original filename: `{safe_name}`",
                    "",
                    "## Extracted Text",
                    "",
                    extraction.extracted_text,
                ]
            ),
            expected_hash=None,
        )
        vault.write_note(
            task_path,
            {"id": task_id, "type": "task", "source": source_id, "status": "queued", "created": utc_now(), "updated": utc_now(), "max_steps": 8},
            f"# Task {task_id}\n\n- Source: [[{source_id}]]\n- Status: queued\n",
            expected_hash=None,
        )
    vault.audit("binary_source_captured", {"source_id": source_id, "task_id": task_id, "duplicate": duplicate, "mime": extraction.detected_mime})
    return {
        "source_id": source_id,
        "task_id": task_id,
        "source_path": source_path,
        "task_path": task_path,
        "attachment_path": attachment_path,
        "sha256": digest,
        "duplicate": duplicate,
        "extraction": extraction.to_dict(),
    }
