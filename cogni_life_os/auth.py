from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from .ids import sha256_bytes, utc_now


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    subject: str | None
    error: str | None


class TokenStore:
    def __init__(self, path: Path, *, now=time.time):
        self.path = path
        self.now = now
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self.path.exists():
            return {"tokens": {}, "revoked": {}, "rate": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def issue(self, subject: str, ttl_seconds: int = 3600) -> str:
        token = secrets.token_urlsafe(32)
        digest = sha256_bytes(token.encode("utf-8"))
        data = self._load()
        data["tokens"][digest] = {"subject": subject, "expires": self.now() + ttl_seconds, "created": utc_now()}
        self._save(data)
        return token

    def add_existing(self, token: str, subject: str, ttl_seconds: int = 3600) -> None:
        digest = sha256_bytes(token.encode("utf-8"))
        data = self._load()
        data["tokens"][digest] = {"subject": subject, "expires": self.now() + ttl_seconds, "created": utc_now()}
        self._save(data)

    def verify(self, token: str | None) -> AuthResult:
        if not token:
            return AuthResult(False, None, "missing_token")
        digest = sha256_bytes(token.encode("utf-8"))
        data = self._load()
        if digest in data.get("revoked", {}):
            return AuthResult(False, None, "revoked_token")
        record = data.get("tokens", {}).get(digest)
        if not record:
            return AuthResult(False, None, "invalid_token")
        if record["expires"] < self.now():
            return AuthResult(False, None, "expired_token")
        return AuthResult(True, record["subject"], None)

    def revoke(self, token: str) -> None:
        digest = sha256_bytes(token.encode("utf-8"))
        data = self._load()
        data.setdefault("revoked", {})[digest] = {"revoked": utc_now()}
        data.get("tokens", {}).pop(digest, None)
        self._save(data)

    def rotate(self, old_token: str, subject: str, ttl_seconds: int = 3600) -> str:
        self.revoke(old_token)
        return self.issue(subject, ttl_seconds)

    def rate_limit(self, subject: str, client: str, *, limit: int = 120, window_seconds: int = 60) -> bool:
        data = self._load()
        key = f"{subject}:{client}"
        now = self.now()
        bucket = [ts for ts in data.setdefault("rate", {}).get(key, []) if now - ts < window_seconds]
        if len(bucket) >= limit:
            data["rate"][key] = bucket[-limit:]
            self._save(data)
            return False
        bucket.append(now)
        data["rate"][key] = bucket[-limit:]
        self._save(data)
        return True
