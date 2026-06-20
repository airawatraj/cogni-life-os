from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
import re

from .ids import sha256_bytes, utc_now
from .markdown import parse_frontmatter
from .vault import Vault


SCHEMA = """
create table if not exists notes (
  path text primary key,
  title text,
  kind text,
  note_id text,
  tags text,
  body text,
  sha256 text,
  updated text
);
create virtual table if not exists notes_fts using fts5(path, title, body);
"""


class Index:
    active_connections = 0

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        type(self).active_connections += 1
        conn.executescript(SCHEMA)
        return conn

    def close(self, conn) -> None:
        try:
            conn.close()
        finally:
            type(self).active_connections -= 1

    @contextmanager
    def connection(self):
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.close(conn)

    def rebuild(self, vault: Vault) -> int:
        with self.connection() as conn:
            conn.execute("delete from notes")
            conn.execute("delete from notes_fts")
            count = 0
            for path in vault.iter_markdown():
                rel = str(path.relative_to(vault.root))
                raw = path.read_text(encoding="utf-8")
                fm, body = parse_frontmatter(raw)
                title = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), path.stem)
                conn.execute(
                    "insert into notes(path,title,kind,note_id,tags,body,sha256,updated) values(?,?,?,?,?,?,?,?)",
                    (
                        rel,
                        title,
                        fm.get("type", ""),
                        fm.get("id", ""),
                        _frontmatter_text(fm.get("tags", "")),
                        body,
                        sha256_bytes(raw.encode("utf-8")),
                        utc_now(),
                    ),
                )
                conn.execute("insert into notes_fts(path,title,body) values(?,?,?)", (rel, title, body))
                count += 1
        vault.audit("index_rebuilt", {"count": count, "db": str(self.db_path)})
        return count

    def update_note(self, vault: Vault, relative: str) -> None:
        path = vault.root / relative
        raw = path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(raw)
        title = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), path.stem)
        with self.connection() as conn:
            conn.execute("delete from notes where path = ?", (relative,))
            conn.execute("delete from notes_fts where path = ?", (relative,))
            conn.execute(
                "insert into notes(path,title,kind,note_id,tags,body,sha256,updated) values(?,?,?,?,?,?,?,?)",
                (
                    relative,
                    title,
                    fm.get("type", ""),
                    fm.get("id", ""),
                    _frontmatter_text(fm.get("tags", "")),
                    body,
                    sha256_bytes(raw.encode("utf-8")),
                    utc_now(),
                ),
            )
            conn.execute("insert into notes_fts(path,title,body) values(?,?,?)", (relative, title, body))

    def search(self, query: str, *, limit: int = 10) -> list[dict]:
        return self.search_layered(query, limit=limit)

    def search_layered(self, query: str, *, limit: int = 10, candidate_limit: int = 200) -> list[dict]:
        if query.count('"') % 2:
            raise ValueError("unterminated quoted search phrase")
        terms = _terms(query)
        expanded_terms = _expanded_terms(terms)
        phrase = " ".join(terms)
        with self.connection() as conn:
            rows = conn.execute(
                "select notes.path, notes.title, notes.kind, notes.note_id, notes.body, bm25(notes_fts) as rank from notes_fts join notes using(path) where notes_fts match ? order by rank limit ?",
                (_fts_query(expanded_terms), candidate_limit),
            ).fetchall()
        scored = []
        seen = set()
        for row in rows:
            path, title, kind, note_id, body, rank = row
            if path in seen:
                continue
            seen.add(path)
            score, reasons = _score(query, terms, expanded_terms, phrase, title or "", body or "", float(rank or 0))
            scored.append((score, {"path": path, "title": title, "type": kind, "id": note_id, "score": round(score, 4), "reasons": reasons}))
        scored.sort(key=lambda item: item[0], reverse=True)
        if len(terms) > 1 and scored:
            threshold = max(8.0, scored[0][0] * 0.7)
            scored = [item for item in scored if item[0] >= threshold]
        return [item for _score_value, item in scored[:limit]]

    def health(self) -> dict:
        with self.connection() as conn:
            count = conn.execute("select count(*) from notes").fetchone()[0]
        return {"note_count": count, "db_path": str(self.db_path), "checked": utc_now()}


def _terms(query: str) -> list[str]:
    return [term for term in re.findall(r"[a-z0-9]+", query.lower()) if term not in {"the", "a", "an", "and", "or", "for", "to", "of"}]


def _frontmatter_text(value) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _expanded_terms(terms: list[str]) -> list[str]:
    expansions = {
        "boundary": ["scope", "domain"],
        "car": ["vehicle", "auto"],
        "conflicting": ["contradiction", "conflict"],
        "connect": ["comparison", "relationship"],
        "cover": ["protection", "policy"],
        "customer": ["client"],
        "doctor": ["health", "medical"],
        "external": ["outside", "public"],
        "job": ["work", "client"],
        "old": ["ancient"],
        "new": ["modern"],
        "private": ["personal", "confidential"],
        "release": ["publish", "external"],
        "renew": ["renewal", "rollover"],
        "renewal": ["renew", "rollover"],
        "safe": ["risk"],
        "schedule": ["calendar", "date"],
        "workplace": ["work", "client"],
    }
    expanded: list[str] = []
    for term in terms:
        if term not in expanded:
            expanded.append(term)
        for extra in expansions.get(term, []):
            if extra not in expanded:
                expanded.append(extra)
    return expanded


def _fts_query(terms: list[str]) -> str:
    if not terms:
        return '""'
    return " OR ".join(f'"{term}"' for term in terms)


def _score(query: str, terms: list[str], expanded_terms: list[str], phrase: str, title: str, body: str, bm25_rank: float) -> tuple[float, list[str]]:
    title_l = title.lower()
    body_l = body.lower()
    reasons: list[str] = []
    score = -bm25_rank
    if phrase and phrase in title_l:
        score += 25
        reasons.append("exact_title_phrase")
    if phrase and phrase in body_l:
        score += 12
        reasons.append("exact_body_phrase")
    title_hits = sum(1 for term in terms if term in title_l)
    body_hits = sum(1 for term in terms if term in body_l)
    semantic_hits = sum(1 for term in expanded_terms if term not in terms and term in f"{title_l}\n{body_l}")
    if terms and title_hits == len(terms):
        score += 12
        reasons.append("all_terms_in_title")
    score += title_hits * 4
    score += body_hits * 1.5
    if semantic_hits:
        score += semantic_hits * 1.2
        reasons.append("semantic_term_match")
    if "alias:" in body_l and any(term in body_l.split("alias:", 1)[1][:160] for term in terms):
        score += 8
        reasons.append("alias_match")
    if phrase and re.search(rf"\bnot\b[^.?!\n]{{0,80}}\b{re.escape(phrase)}\b", body_l):
        score -= 18
        reasons.append("negated_phrase")
    for term in terms:
        if f"not {term}" in body_l or f"not {term}" in title_l:
            score -= 10
            reasons.append(f"negated_{term}")
    if "distractor" in title_l:
        score -= 8
        reasons.append("distractor_penalty")
    if "stale claim" in body_l and any(term in {"current", "latest", "renewal"} for term in terms):
        score += 2
        reasons.append("current_fact_context")
    return score, reasons
