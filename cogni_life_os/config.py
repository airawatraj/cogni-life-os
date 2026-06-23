from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


LOCAL_CONFIG_PATH = PROJECT_ROOT / ".cogni" / "config.json"


def _local_config() -> dict:
    if not LOCAL_CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def configured_vault_path() -> Path:
    value = os.environ.get("COGNI_VAULT_PATH") or _local_config().get("COGNI_VAULT_PATH")
    return Path(value).expanduser() if value else PROJECT_ROOT / "local_test_vault"


def local_config_value(name: str, default: str = "") -> str:
    return str(os.environ.get(name) or _local_config().get(name) or default)


def local_config_int(name: str, default: int) -> int:
    try:
        return int(local_config_value(name, str(default)))
    except ValueError:
        return default


def persist_local_config(values: dict, config_path: Path = LOCAL_CONFIG_PATH) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.update(values)
    config_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def persist_vault_path(path: Path, config_path: Path = LOCAL_CONFIG_PATH) -> None:
    persist_local_config({"COGNI_VAULT_PATH": str(path)}, config_path)


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    vault_path: Path = configured_vault_path()
    runtime_path: Path = PROJECT_ROOT / ".cogni" / "runtime"
    backup_path: Path = PROJECT_ROOT / ".cogni" / "backups"
    evidence_path: Path = PROJECT_ROOT / ".cogni" / "evaluation-evidence"
    local_config_path: Path = LOCAL_CONFIG_PATH
    bind_host: str = local_config_value("COGNI_BIND_HOST", "127.0.0.1")
    port: int = local_config_int("COGNI_PORT", 8765)
    public_base_url: str = local_config_value("COGNI_PUBLIC_BASE_URL", "")
    access_mode: str = local_config_value("COGNI_ACCESS_MODE", "this-device")
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
