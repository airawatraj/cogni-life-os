from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

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
                        fm.get("tags", ""),
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
                    fm.get("tags", ""),
                    body,
                    sha256_bytes(raw.encode("utf-8")),
                    utc_now(),
                ),
            )
            conn.execute("insert into notes_fts(path,title,body) values(?,?,?)", (relative, title, body))

    def search(self, query: str, *, limit: int = 10) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "select notes.path, notes.title, notes.kind, notes.note_id from notes_fts join notes using(path) where notes_fts match ? limit ?",
                (query, limit),
            ).fetchall()
        return [{"path": row[0], "title": row[1], "type": row[2], "id": row[3]} for row in rows]

    def health(self) -> dict:
        with self.connection() as conn:
            count = conn.execute("select count(*) from notes").fetchone()[0]
        return {"note_count": count, "db_path": str(self.db_path), "checked": utc_now()}
