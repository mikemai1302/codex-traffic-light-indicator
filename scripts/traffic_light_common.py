from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


DEFAULT_LANGUAGE = "zh"
SUPPORTED_LANGUAGES = {"zh", "en"}
DEFAULT_UI_SIZE = "medium"
SUPPORTED_UI_SIZES = {"small", "medium", "large"}

# 这里集中定义所有会显示在悬浮窗上的状态文字。
# 其他脚本只保存 status/language，不需要自己拼中文或英文。
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
    # 状态文件可能被手动编辑或旧版本写入，所以读取时统一做兜底。
    if isinstance(language, str):
        normalized = language.lower().strip()
        if normalized in SUPPORTED_LANGUAGES:
            return normalized
    return DEFAULT_LANGUAGE


def normalize_ui_size(ui_size: object) -> str:
    # 只允许三档大小，非法值自动回到中等大小，避免窗口布局异常。
    if isinstance(ui_size, str):
        normalized = ui_size.lower().strip()
        if normalized in SUPPORTED_UI_SIZES:
            return normalized
    return DEFAULT_UI_SIZE


def status_label(status: str, language: object = DEFAULT_LANGUAGE) -> str:
    # 根据当前语言返回灯色对应的短文字。
    normalized_status = status.lower().strip()
    normalized_language = normalize_language(language)
    return STATUS_LABELS_BY_LANGUAGE[normalized_language].get(
        normalized_status,
        STATUS_LABELS_BY_LANGUAGE[normalized_language]["green"],
    )


def status_path() -> Path:
    # CODEX_TRAFFIC_LIGHT_STATUS 可用于测试或自定义安装目录。
    # 没有环境变量时默认写到 D 盘安装目录。
    configured = os.environ.get("CODEX_TRAFFIC_LIGHT_STATUS")
    if configured:
        return Path(configured)
    return Path("D:/codex\u7ea2\u7eff\u706f\u63d0\u793a\u706f/state/status.json")


def default_status() -> dict[str, Any]:
    # 状态文件不存在或损坏时使用这份默认值。
    now = time.time()
    return {
        "status": "green",
        "message": status_label("green"),
        "language": DEFAULT_LANGUAGE,
        "ui_size": DEFAULT_UI_SIZE,
        "codex_connected": False,
        "last_mcp_heartbeat": 0,
        "updated_at": now,
    }


def read_status() -> dict[str, Any]:
    # 读取共享状态文件，并把缺失字段、非法字段修正成安全值。
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
    merged["ui_size"] = normalize_ui_size(merged.get("ui_size"))
    return merged


def write_status(
    status: str | None = None,
    message: str | None = None,
    *,
    language: str | None = None,
    ui_size: str | None = None,
    codex_connected: bool | None = None,
    heartbeat: bool = False,
) -> dict[str, Any]:
    # 所有状态写入都走这里，保证 JSON 原子替换，减少写到一半被读取的概率。
    data = read_status()
    if language is not None:
        data["language"] = normalize_language(language)
    if ui_size is not None:
        data["ui_size"] = normalize_ui_size(ui_size)
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
