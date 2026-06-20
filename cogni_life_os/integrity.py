from __future__ import annotations

import re

from .ids import utc_now
from .markdown import FrontmatterError, parse_frontmatter
from .vault import Vault


WIKI_LINK = re.compile(r"\[\[([^\]|#]+)")


def scan(vault: Vault) -> dict:
    ids: dict[str, str] = {}
    aliases: dict[str, str] = {}
    duplicate_ids: list[dict] = []
    broken_links: list[dict] = []
    missing_attachments: list[dict] = []
    corrupt_notes: list[str] = []
    malformed_frontmatter: list[str] = []
    notes: list[tuple[str, dict, str]] = []
    markdown_paths = list(vault.iter_markdown())
    names = {path.stem: str(path.relative_to(vault.root)) for path in markdown_paths}
    relative_files = {str(path.relative_to(vault.root)) for path in vault.root.rglob("*") if path.is_file()}

    for path in markdown_paths:
        rel = str(path.relative_to(vault.root))
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            corrupt_notes.append(rel)
            continue
        try:
            fm, body = parse_frontmatter(text)
        except (FrontmatterError, ValueError, SyntaxError):
            malformed_frontmatter.append(rel)
            continue
        notes.append((rel, fm, body))
        note_id = fm.get("id")
        if isinstance(note_id, str) and note_id:
            if note_id in ids:
                duplicate_ids.append({"id": note_id, "first": ids[note_id], "second": rel})
            else:
                ids[note_id] = rel
        raw_aliases = fm.get("aliases", [])
        if isinstance(raw_aliases, str):
            raw_aliases = [raw_aliases]
        if isinstance(raw_aliases, list):
            for alias in raw_aliases:
                if isinstance(alias, str) and alias:
                    aliases[alias] = rel

    valid_targets = set(ids) | set(names) | set(aliases)

    for rel, _fm, body in notes:
        for raw_link in WIKI_LINK.findall(body):
            link = raw_link.strip()
            if "/" in link or "." in link:
                if link not in relative_files:
                    missing_attachments.append({"from": rel, "to": link})
                continue
            if link not in valid_targets:
                broken_links.append({"from": rel, "to": link})

    status = "pass" if not duplicate_ids and not broken_links and not corrupt_notes and not malformed_frontmatter and not missing_attachments else "fail"
    result = {
        "status": status,
        "checked": utc_now(),
        "duplicate_ids": duplicate_ids,
        "broken_links": broken_links,
        "missing_attachments": missing_attachments,
        "corrupt_notes": corrupt_notes,
        "malformed_frontmatter": malformed_frontmatter,
        "note_count": len(markdown_paths),
    }
    vault.audit("integrity_scan", result)
    return result
