from __future__ import annotations

import json
import sys
import traceback
from typing import Any

from traffic_light_common import VALID_STATUSES, read_status, status_label, write_status


SERVER_INFO = {"name": "codex-traffic-light", "version": "0.1.0"}

if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def respond(message_id: Any, result: Any = None, error: Any = None) -> None:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": message_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def tool_result(text: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    if data is not None:
        text = f"{text}\n{json.dumps(data, ensure_ascii=False, indent=2)}"
    return {"content": [{"type": "text", "text": text}]}


def list_tools() -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": "set_codex_light",
                "description": "Set the floating Codex traffic light status.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": sorted(VALID_STATUSES),
                            "description": "red=working, yellow=waiting for authorization, green=idle",
                        },
                        "message": {
                            "type": "string",
                            "description": "Optional short text shown in the status file.",
                        },
                    },
                    "required": ["status"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_codex_light_status",
                "description": "Read the floating Codex traffic light status and refresh the Codex connection heartbeat.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            {
                "name": "ping_codex_traffic_light",
                "description": "Refresh the Codex connection heartbeat for the floating traffic light.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        ]
    }


def call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    arguments = arguments or {}
    if name == "set_codex_light":
        status = str(arguments.get("status", "")).lower().strip()
        if status not in VALID_STATUSES:
            raise ValueError("status must be one of: red, yellow, green")
        message = arguments.get("message")
        language = read_status().get("language")
        data = write_status(status, str(message) if message else status_label(status, language), heartbeat=True)
        return tool_result(f"\u63d0\u793a\u706f\u5df2\u8bbe\u7f6e\u4e3a {status}\u3002", data)

    if name == "get_codex_light_status":
        write_status(heartbeat=True)
        return tool_result("\u5f53\u524d\u63d0\u793a\u706f\u72b6\u6001\uff1a", read_status())

    if name == "ping_codex_traffic_light":
        data = write_status(heartbeat=True)
        return tool_result("Codex \u7ea2\u7eff\u706f\u63d0\u793a\u706f\u8fde\u63a5\u5fc3\u8df3\u5df2\u5237\u65b0\u3002", data)

    raise ValueError(f"Unknown tool: {name}")


def handle(request: dict[str, Any]) -> None:
    message_id = request.get("id")
    method = request.get("method")

    if message_id is None:
        if method == "notifications/initialized":
            write_status(heartbeat=True)
        return

    try:
        if method == "initialize":
            write_status(heartbeat=True)
            respond(
                message_id,
                {
                    "protocolVersion": request.get("params", {}).get("protocolVersion", "2024-11-05"),
                    "capabilities": {"tools": {}},
                    "serverInfo": SERVER_INFO,
                },
            )
        elif method == "tools/list":
            write_status(heartbeat=True)
            respond(message_id, list_tools())
        elif method == "tools/call":
            params = request.get("params", {})
            result = call_tool(str(params.get("name", "")), params.get("arguments") or {})
            respond(message_id, result)
        else:
            respond(message_id, error={"code": -32601, "message": f"Method not found: {method}"})
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        respond(message_id, error={"code": -32000, "message": str(exc)})


def main() -> None:
    write_status(heartbeat=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            respond(None, error={"code": -32700, "message": str(exc)})
            continue
        handle(request)


if __name__ == "__main__":
    main()
