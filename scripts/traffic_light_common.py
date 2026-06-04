from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


DEFAULT_LANGUAGE = "zh"
SUPPORTED_LANGUAGES = {"zh", "en"}

STATUS_LABELS_BY_LANGUAGE = {
    "zh": {
        "red": "Codex \u6b63\u5728\u5e72\u6d3b",
        "yellow": "Codex \u7b49\u5f85\u6388\u6743",
        "green": "Codex \u7a7a\u95f2\u4e2d",
    },
    "en": {
        "red": "Codex working",
        "yellow": "Awaiting approval",
        "green": "Codex idle",
    },
}

STATUS_LABELS = STATUS_LABELS_BY_LANGUAGE[DEFAULT_LANGUAGE]
VALID_STATUSES = set(STATUS_LABELS)


def normalize_language(language: object) -> str:
    if isinstance(language, str):
        normalized = language.lower().strip()
        if normalized in SUPPORTED_LANGUAGES:
            return normalized
    return DEFAULT_LANGUAGE


def status_label(status: str, language: object = DEFAULT_LANGUAGE) -> str:
    normalized_status = status.lower().strip()
    normalized_language = normalize_language(language)
    return STATUS_LABELS_BY_LANGUAGE[normalized_language].get(
        normalized_status,
        STATUS_LABELS_BY_LANGUAGE[normalized_language]["green"],
    )


def status_path() -> Path:
    configured = os.environ.get("CODEX_TRAFFIC_LIGHT_STATUS")
    if configured:
        return Path(configured)
    return Path("D:/codex\u7ea2\u7eff\u706f\u63d0\u793a\u706f/state/status.json")


def default_status() -> dict[str, Any]:
    now = time.time()
    return {
        "status": "green",
        "message": status_label("green"),
        "language": DEFAULT_LANGUAGE,
        "codex_connected": False,
        "last_mcp_heartbeat": 0,
        "updated_at": now,
    }


def read_status() -> dict[str, Any]:
    path = status_path()
    if not path.exists():
        return default_status()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default_status()
    merged = default_status()
    merged.update(data if isinstance(data, dict) else {})
    if merged.get("status") not in VALID_STATUSES:
        merged["status"] = "green"
    merged["language"] = normalize_language(merged.get("language"))
    return merged


def write_status(
    status: str | None = None,
    message: str | None = None,
    *,
    language: str | None = None,
    codex_connected: bool | None = None,
    heartbeat: bool = False,
) -> dict[str, Any]:
    data = read_status()
    if language is not None:
        data["language"] = normalize_language(language)
    if status is not None:
        normalized = status.lower().strip()
        if normalized not in VALID_STATUSES:
            raise ValueError(f"Unsupported status: {status}")
        data["status"] = normalized
        data["message"] = message or status_label(normalized, data.get("language"))
    elif message is not None:
        data["message"] = message
    elif language is not None:
        data["message"] = status_label(str(data.get("status") or "green"), data.get("language"))

    now = time.time()
    if codex_connected is not None:
        data["codex_connected"] = bool(codex_connected)
    if heartbeat:
        data["codex_connected"] = True
        data["last_mcp_heartbeat"] = now
    data["updated_at"] = now

    path = status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return data
