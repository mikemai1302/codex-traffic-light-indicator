from __future__ import annotations

import json
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import Menu

from traffic_light_common import normalize_language, read_status, status_label, status_path, write_status


WINDOW_SIZE = "188x236"
TRANSPARENT_COLOR = "#010203"
POLL_MS = 500
CONNECTED_WINDOW_SECONDS = 45
MIN_RED_SECONDS = 3
YELLOW_IDLE_SECONDS = 3
AUTH_PENDING_MAX_AGE_SECONDS = 600
TASK_ACTIVE_MAX_AGE_SECONDS = 7200
MAX_SESSION_SCAN_BYTES = 2_000_000
CODEX_STATE_PATH = Path.home() / ".codex" / ".codex-global-state.json"
CODEX_SESSIONS_ROOT = Path.home() / ".codex" / "sessions"
UI_TEXT = {
    "zh": {
        "connected": "Codex\uff1a\u5df2\u6210\u529f\u8fde\u63a5",
        "waiting": "Codex\uff1a\u7b49\u5f85\u8fde\u63a5",
        "set_red": "\u8bbe\u4e3a\u7ea2\u706f\uff1a\u6b63\u5728\u5e72\u6d3b",
        "set_yellow": "\u8bbe\u4e3a\u9ec4\u706f\uff1a\u7b49\u5f85\u6388\u6743",
        "set_green": "\u8bbe\u4e3a\u7eff\u706f\uff1a\u7a7a\u95f2\u4e2d",
        "language": "\u8bed\u8a00 / Language",
        "chinese": "\u4e2d\u6587",
        "english": "English",
        "open_state": "\u6253\u5f00\u72b6\u6001\u6587\u4ef6\u5939",
        "exit": "\u9000\u51fa",
    },
    "en": {
        "connected": "Codex connected",
        "waiting": "Codex waiting",
        "set_red": "Set red: working",
        "set_yellow": "Set yellow: approval",
        "set_green": "Set green: idle",
        "language": "Language / \u8bed\u8a00",
        "chinese": "\u4e2d\u6587",
        "english": "English",
        "open_state": "Open state folder",
        "exit": "Exit",
    },
}


class TrafficLightWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Codex \u7ea2\u7eff\u706f\u63d0\u793a\u706f")
        self.root.geometry(WINDOW_SIZE)
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.drag_origin: tuple[int, int] | None = None
        self.language = normalize_language(read_status().get("language"))
        self.prompt_history_count = self.read_prompt_history_count()
        self.last_session_mtime = self.latest_session_mtime()
        self.session_quiet_since = time.time()

        self.canvas = tk.Canvas(self.root, width=128, height=172, bg=TRANSPARENT_COLOR, highlightthickness=0)
        self.canvas.pack(pady=(12, 0))

        self.canvas.create_round_rectangle = self._round_rectangle  # type: ignore[attr-defined]
        self.canvas.create_round_rectangle(24, 4, 104, 168, radius=18, fill="#262a31", outline="#3a404a", width=2)
        self.lights = {
            "red": self.canvas.create_oval(42, 20, 86, 64, fill="#5b1d20", outline="#1f1113", width=3),
            "yellow": self.canvas.create_oval(42, 68, 86, 112, fill="#5c4b1d", outline="#211c10", width=3),
            "green": self.canvas.create_oval(42, 116, 86, 160, fill="#1d4f34", outline="#101f16", width=3),
        }
        self.canvas.create_rectangle(57, 168, 71, 184, fill="#30343b", outline="")
        self.canvas.create_rectangle(38, 184, 90, 192, fill="#30343b", outline="")

        self.text_canvas = tk.Canvas(self.root, width=188, height=48, bg=TRANSPARENT_COLOR, highlightthickness=0)
        self.text_canvas.pack(pady=(6, 0))
        self.status_text_items = self.create_outlined_text(
            self.text_canvas,
            94,
            12,
            status_label("green", self.language),
            fill="#ffffff",
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        self.connection_text_items = self.create_outlined_text(
            self.text_canvas,
            94,
            34,
            UI_TEXT[self.language]["waiting"],
            fill="#f3c969",
            font=("Microsoft YaHei UI", 10, "bold"),
        )

        self.menu = Menu(self.root, tearoff=False)
        self.rebuild_menu()

        for widget in (self.root, self.canvas, self.text_canvas):
            widget.bind("<ButtonPress-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)
            widget.bind("<Button-3>", self.show_menu)

        self.poll()

    def _round_rectangle(self, x1: int, y1: int, x2: int, y2: int, radius: int = 16, **kwargs: object) -> int:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def create_outlined_text(
        self,
        canvas: tk.Canvas,
        x: int,
        y: int,
        text: str,
        *,
        fill: str,
        font: tuple[str, int, str],
    ) -> list[int]:
        items: list[int] = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)]:
            items.append(canvas.create_text(x + dx, y + dy, text=text, fill="#050607", font=font, anchor="center"))
        items.append(canvas.create_text(x, y, text=text, fill=fill, font=font, anchor="center"))
        return items

    def update_outlined_text(self, canvas: tk.Canvas, items: list[int], text: str, fill: str) -> None:
        for item in items[:-1]:
            canvas.itemconfig(item, text=text, fill="#050607")
        canvas.itemconfig(items[-1], text=text, fill=fill)

    def start_drag(self, event: tk.Event) -> None:
        self.drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def drag(self, event: tk.Event) -> None:
        if self.drag_origin is None:
            return
        x_offset, y_offset = self.drag_origin
        self.root.geometry(f"+{event.x_root - x_offset}+{event.y_root - y_offset}")

    def show_menu(self, event: tk.Event) -> None:
        self.rebuild_menu()
        self.menu.tk_popup(event.x_root, event.y_root)

    def rebuild_menu(self) -> None:
        text = UI_TEXT[self.language]
        self.menu.delete(0, "end")
        self.menu.add_command(label=text["set_red"], command=lambda: self.manual_set("red"))
        self.menu.add_command(label=text["set_yellow"], command=lambda: self.manual_set("yellow"))
        self.menu.add_command(label=text["set_green"], command=lambda: self.manual_set("green"))
        self.menu.add_separator()
        self.language_menu = Menu(self.menu, tearoff=False)
        self.language_menu.add_command(label=text["chinese"], command=lambda: self.set_language("zh"))
        self.language_menu.add_command(label=text["english"], command=lambda: self.set_language("en"))
        self.menu.add_cascade(label=text["language"], menu=self.language_menu)
        self.menu.add_separator()
        self.menu.add_command(label=text["open_state"], command=self.open_state_folder)
        self.menu.add_command(label=text["exit"], command=self.root.destroy)

    def set_language(self, language: str) -> None:
        self.language = normalize_language(language)
        write_status(language=self.language)
        self.rebuild_menu()
        self.apply_status()

    def manual_set(self, status: str) -> None:
        write_status(status, status_label(status, self.language), language=self.language)
        self.apply_status()

    def open_state_folder(self) -> None:
        folder = status_path().parent
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(folder)])

    def poll(self) -> None:
        self.detect_new_codex_prompt()
        self.track_session_activity()
        self.sync_codex_lifecycle_status()
        self.apply_status()
        self.root.after(POLL_MS, self.poll)

    def read_prompt_history_count(self) -> int:
        if not CODEX_STATE_PATH.exists():
            return 0
        try:
            data = json.loads(CODEX_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return self.prompt_history_count if hasattr(self, "prompt_history_count") else 0
        history = data.get("electron-persisted-atom-state", {}).get("prompt-history", {})
        if not isinstance(history, dict):
            return 0
        return sum(len(items) for items in history.values() if isinstance(items, list))

    def detect_new_codex_prompt(self) -> None:
        current_count = self.read_prompt_history_count()
        if current_count > self.prompt_history_count:
            write_status("red", status_label("red", self.language), language=self.language)
            self.last_session_mtime = self.latest_session_mtime()
            self.session_quiet_since = time.time()
        self.prompt_history_count = max(self.prompt_history_count, current_count)

    def latest_session_mtime(self) -> float:
        if not CODEX_SESSIONS_ROOT.exists():
            return 0
        latest = 0.0
        try:
            for path in CODEX_SESSIONS_ROOT.rglob("*.jsonl"):
                latest = max(latest, path.stat().st_mtime)
        except OSError:
            return latest
        return latest

    def track_session_activity(self) -> None:
        latest = self.latest_session_mtime()
        if latest > self.last_session_mtime:
            self.last_session_mtime = latest
            self.session_quiet_since = time.time()

    def codex_available(self) -> bool:
        return self.codex_process_running()

    def codex_process_running(self) -> bool:
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                errors="ignore",
                creationflags=creationflags,
                timeout=2,
            )
        except Exception:
            return False
        if result.returncode != 0:
            return False

        for line in result.stdout.splitlines():
            image_name = line.split(",", 1)[0].strip().strip('"').lower()
            if image_name in {"codex.exe", "codex"}:
                return True
        return False

    def recent_session_files(self) -> list[Path]:
        if not CODEX_SESSIONS_ROOT.exists():
            return []
        try:
            files = list(CODEX_SESSIONS_ROOT.rglob("*.jsonl"))
        except OSError:
            return []
        files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return files[:3]

    def parse_timestamp(self, value: object) -> float:
        if not isinstance(value, str):
            return 0.0
        try:
            parsed = value.replace("Z", "+00:00")
            return __import__("datetime").datetime.fromisoformat(parsed).timestamp()
        except Exception:
            return 0.0

    def recent_session_lines(self, path: Path) -> list[str]:
        try:
            with path.open("rb") as handle:
                handle.seek(0, 2)
                size = handle.tell()
                handle.seek(max(0, size - MAX_SESSION_SCAN_BYTES))
                data = handle.read()
        except OSError:
            return []
        return data.decode("utf-8", errors="ignore").splitlines()

    def authorization_pending(self) -> bool:
        pending: dict[str, float] = {}
        for path in reversed(self.recent_session_files()):
            for line in self.recent_session_lines(path):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = event.get("payload", {})
                if not isinstance(payload, dict):
                    continue
                event_type = payload.get("type")
                call_id = payload.get("call_id")
                if event_type == "function_call" and isinstance(call_id, str):
                    arguments = str(payload.get("arguments") or "")
                    if '"sandbox_permissions":"require_escalated"' in arguments or "require_escalated" in arguments:
                        pending[call_id] = self.parse_timestamp(event.get("timestamp")) or path.stat().st_mtime
                elif event_type == "function_call_output" and isinstance(call_id, str):
                    pending.pop(call_id, None)

        now = time.time()
        return any(now - created_at < AUTH_PENDING_MAX_AGE_SECONDS for created_at in pending.values())

    def codex_task_active(self) -> bool:
        latest_started = 0.0
        latest_completed = 0.0
        for path in reversed(self.recent_session_files()):
            fallback_mtime = path.stat().st_mtime
            for line in self.recent_session_lines(path):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = event.get("payload", {})
                if not isinstance(payload, dict):
                    continue
                payload_type = payload.get("type")
                timestamp = self.parse_timestamp(event.get("timestamp")) or fallback_mtime
                if payload_type == "task_started":
                    latest_started = max(latest_started, timestamp)
                elif payload_type == "task_complete":
                    completed_at = payload.get("completed_at")
                    if isinstance(completed_at, (int, float)):
                        timestamp = max(timestamp, float(completed_at))
                    latest_completed = max(latest_completed, timestamp)

        if latest_started <= latest_completed:
            return False
        return time.time() - latest_started < TASK_ACTIVE_MAX_AGE_SECONDS

    def sync_codex_lifecycle_status(self) -> None:
        data = read_status()
        self.language = normalize_language(data.get("language"))
        if self.authorization_pending():
            if data.get("status") != "yellow":
                write_status("yellow", status_label("yellow", self.language), language=self.language)
            return

        if self.codex_task_active():
            if data.get("status") != "red":
                write_status("red", status_label("red", self.language), language=self.language)
            return

        updated_at = float(data.get("updated_at") or 0)
        if data.get("status") in {"red", "yellow"} and time.time() - updated_at > YELLOW_IDLE_SECONDS:
            write_status("green", status_label("green", self.language), language=self.language)

    def apply_status(self) -> None:
        data = read_status()
        self.language = normalize_language(data.get("language"))
        active = data.get("status", "green")
        updated_at = float(data.get("updated_at") or 0)
        if active == "yellow" and not self.authorization_pending() and time.time() - updated_at > YELLOW_IDLE_SECONDS:
            active = "green"
            data["message"] = status_label("green", self.language)
            write_status("green", status_label("green", self.language), language=self.language)
        if active == "red" and not self.codex_task_active() and time.time() - updated_at > MIN_RED_SECONDS:
            active = "green"
            data["message"] = status_label("green", self.language)
            write_status("green", status_label("green", self.language), language=self.language)
        colors = {
            "red": ("#ef4444", "#5b1d20"),
            "yellow": ("#facc15", "#5c4b1d"),
            "green": ("#22c55e", "#1d4f34"),
        }
        for name, item in self.lights.items():
            self.canvas.itemconfig(item, fill=colors[name][0 if name == active else 1])

        status_text = status_label(str(active), self.language)
        self.update_outlined_text(self.text_canvas, self.status_text_items, status_text, "#ffffff")
        connected = self.codex_available()
        if connected != bool(data.get("codex_connected")):
            write_status(codex_connected=connected)
        if connected:
            self.update_outlined_text(
                self.text_canvas,
                self.connection_text_items,
                UI_TEXT[self.language]["connected"],
                "#71f2a1",
            )
        else:
            self.update_outlined_text(
                self.text_canvas,
                self.connection_text_items,
                UI_TEXT[self.language]["waiting"],
                "#ffd166",
            )

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    status_path().parent.mkdir(parents=True, exist_ok=True)
    app = TrafficLightWindow()
    app.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
