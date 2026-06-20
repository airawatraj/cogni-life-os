from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    vault_path: Path = PROJECT_ROOT / "local_test_vault"
    runtime_path: Path = PROJECT_ROOT / ".cogni" / "runtime"
    backup_path: Path = PROJECT_ROOT / ".cogni" / "backups"
    evidence_path: Path = PROJECT_ROOT / ".cogni" / "evaluation-evidence"
    model_base_url: str = os.environ.get("COGNI_MODEL_BASE_URL", "http://127.0.0.1:8000/v1")
    model_api_key: str = os.environ.get("COGNI_MODEL_API_KEY", "local")
    model_name: str = os.environ.get("COGNI_MODEL_NAME", "Cogni-Brain")
    service_token: str = os.environ.get("COGNI_SERVICE_TOKEN", "dev-local-change-me")
    max_upload_bytes: int = int(os.environ.get("COGNI_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
    max_agent_steps: int = int(os.environ.get("COGNI_MAX_AGENT_STEPS", "8"))
    model_timeout_seconds: float = float(os.environ.get("COGNI_MODEL_TIMEOUT_SECONDS", "30"))
    tool_timeout_seconds: float = float(os.environ.get("COGNI_TOOL_TIMEOUT_SECONDS", "10"))


def settings() -> Settings:
    return Settings()
