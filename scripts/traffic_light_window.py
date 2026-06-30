from __future__ import annotations

import json
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import Menu

from traffic_light_common import normalize_language, normalize_ui_size, read_status, status_label, status_path, write_status


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
ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"

# 三种灯色分别对应三张 PNG；{size} 会被替换成 small/medium/large。
STATUS_IMAGE_FILES = {
    "red": "traffic-light-red-{size}.png",
    "yellow": "traffic-light-yellow-{size}.png",
    "green": "traffic-light-green-{size}.png",
}

# 三档窗口尺寸配置。每档都同时调整窗口、图片画布、文字画布和字体大小。
UI_SIZES = {
    "small": {
        "window": "168x222",
        "canvas_w": 112,
        "canvas_h": 150,
        "text_w": 168,
        "text_h": 48,
        "text_x": 84,
        "status_y": 12,
        "connection_y": 34,
        "status_font": ("Microsoft YaHei UI", 10, "bold"),
        "connection_font": ("Microsoft YaHei UI", 9, "bold"),
        "canvas_pady": (10, 0),
        "text_pady": (6, 0),
    },
    "medium": {
        "window": "188x236",
        "canvas_w": 128,
        "canvas_h": 172,
        "text_w": 188,
        "text_h": 48,
        "text_x": 94,
        "status_y": 12,
        "connection_y": 34,
        "status_font": ("Microsoft YaHei UI", 11, "bold"),
        "connection_font": ("Microsoft YaHei UI", 10, "bold"),
        "canvas_pady": (12, 0),
        "text_pady": (6, 0),
    },
    "large": {
        "window": "228x288",
        "canvas_w": 164,
        "canvas_h": 220,
        "text_w": 228,
        "text_h": 56,
        "text_x": 114,
        "status_y": 14,
        "connection_y": 40,
        "status_font": ("Microsoft YaHei UI", 12, "bold"),
        "connection_font": ("Microsoft YaHei UI", 11, "bold"),
        "canvas_pady": (12, 0),
        "text_pady": (7, 0),
    },
}

# 右键菜单和连接文字的中英文文案。
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
        "size": "\u5927\u5c0f / Size",
        "small": "\u5c0f",
        "medium": "\u4e2d",
        "large": "\u5927",
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
        "size": "Size / \u5927\u5c0f",
        "small": "Small",
        "medium": "Medium",
        "large": "Large",
        "open_state": "Open state folder",
        "exit": "Exit",
    },
}


class TrafficLightWindow:
    def __init__(self) -> None:
        # Tkinter 窗口使用透明色 + 无边框，做出“只有红绿灯和文字”的悬浮效果。
        self.root = tk.Tk()
        self.root.title("Codex \u7ea2\u7eff\u706f\u63d0\u793a\u706f")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.drag_origin: tuple[int, int] | None = None

        # 启动时从状态文件恢复语言和大小；没有状态文件时使用默认值。
        startup_status = read_status()
        self.language = normalize_language(startup_status.get("language"))
        self.ui_size = normalize_ui_size(startup_status.get("ui_size"))
        self.prompt_history_count = self.read_prompt_history_count()
        self.last_session_mtime = self.latest_session_mtime()
        self.session_quiet_since = time.time()

        # 上半部分画布只负责显示红绿灯图片。
        size_config = UI_SIZES[self.ui_size]
        self.canvas = tk.Canvas(
            self.root,
            width=int(size_config["canvas_w"]),
            height=int(size_config["canvas_h"]),
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
        )
        self.canvas.pack(pady=size_config["canvas_pady"])
        self.status_images = self.load_status_images()
        self.light_item: int | None = None
        self.lights: dict[str, int] = {}
        if self.status_images:
            self.light_item = self.canvas.create_image(
                int(size_config["canvas_w"]) // 2,
                int(size_config["canvas_h"]) // 2,
                image=self.status_images[self.ui_size]["green"],
                anchor="center",
            )
        else:
            # 如果图片资源丢失，自动退回到 Canvas 绘制版本，保证程序仍可运行。
            self.draw_fallback_light()

        # 下半部分画布显示状态文字和 Codex 连接状态。
        self.text_canvas = tk.Canvas(
            self.root,
            width=int(size_config["text_w"]),
            height=int(size_config["text_h"]),
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
        )
        self.text_canvas.pack(pady=size_config["text_pady"])
        self.status_text_items = self.create_outlined_text(
            self.text_canvas,
            int(size_config["text_x"]),
            int(size_config["status_y"]),
            status_label("green", self.language),
            fill="#ffffff",
            font=size_config["status_font"],
        )
        self.connection_text_items = self.create_outlined_text(
            self.text_canvas,
            int(size_config["text_x"]),
            int(size_config["connection_y"]),
            UI_TEXT[self.language]["waiting"],
            fill="#f3c969",
            font=size_config["connection_font"],
        )
        self.apply_window_size()

        self.menu = Menu(self.root, tearoff=False)
        self.rebuild_menu()

        # 鼠标左键拖动，右键打开设置菜单。
        for widget in (self.root, self.canvas, self.text_canvas):
            widget.bind("<ButtonPress-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)
            widget.bind("<Button-3>", self.show_menu)

        self.poll()

    def load_status_images(self) -> dict[str, dict[str, tk.PhotoImage]]:
        # Tkinter 的 PhotoImage 必须保存在实例变量里，否则会被垃圾回收导致图片消失。
        images: dict[str, dict[str, tk.PhotoImage]] = {}
        try:
            for size in UI_SIZES:
                images[size] = {}
                for status, filename in STATUS_IMAGE_FILES.items():
                    images[size][status] = tk.PhotoImage(file=str(ASSET_DIR / filename.format(size=size)))
        except tk.TclError:
            return {}
        return images

    def draw_fallback_light(self) -> None:
        # 备用绘制方案：不用图片，直接画一个简单交通灯。
        self.canvas.create_round_rectangle = self._round_rectangle  # type: ignore[attr-defined]
        self.canvas.create_round_rectangle(24, 4, 104, 168, radius=18, fill="#262a31", outline="#3a404a", width=2)
        self.lights = {
            "red": self.canvas.create_oval(42, 20, 86, 64, fill="#5b1d20", outline="#1f1113", width=3),
            "yellow": self.canvas.create_oval(42, 68, 86, 112, fill="#5c4b1d", outline="#211c10", width=3),
            "green": self.canvas.create_oval(42, 116, 86, 160, fill="#1d4f34", outline="#101f16", width=3),
        }
        self.canvas.create_rectangle(57, 168, 71, 184, fill="#30343b", outline="")
        self.canvas.create_rectangle(38, 184, 90, 192, fill="#30343b", outline="")

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
        # 用多层偏移文字模拟描边，让透明背景上的白字更清楚。
        items: list[int] = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)]:
            items.append(canvas.create_text(x + dx, y + dy, text=text, fill="#050607", font=font, anchor="center"))
        items.append(canvas.create_text(x, y, text=text, fill=fill, font=font, anchor="center"))
        return items

    def update_outlined_text(self, canvas: tk.Canvas, items: list[int], text: str, fill: str) -> None:
        for item in items[:-1]:
            canvas.itemconfig(item, text=text, fill="#050607")
        canvas.itemconfig(items[-1], text=text, fill=fill)

    def configure_outlined_text(
        self,
        canvas: tk.Canvas,
        items: list[int],
        *,
        x: int,
        y: int,
        font: tuple[str, int, str],
    ) -> None:
        # 切换小/中/大时，文字坐标和字体也要一起更新。
        offsets = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (0, 0)]
        for item, (dx, dy) in zip(items, offsets):
            canvas.coords(item, x + dx, y + dy)
            canvas.itemconfig(item, font=font)

    def apply_window_size(self) -> None:
        # 根据当前 ui_size 应用窗口尺寸、画布尺寸、图片位置和文字位置。
        size_config = UI_SIZES[self.ui_size]
        self.root.geometry(str(size_config["window"]))
        self.canvas.config(width=int(size_config["canvas_w"]), height=int(size_config["canvas_h"]))
        self.canvas.pack_configure(pady=size_config["canvas_pady"])
        self.text_canvas.config(width=int(size_config["text_w"]), height=int(size_config["text_h"]))
        self.text_canvas.pack_configure(pady=size_config["text_pady"])
        if self.light_item is not None and self.ui_size in self.status_images:
            self.canvas.coords(
                self.light_item,
                int(size_config["canvas_w"]) // 2,
                int(size_config["canvas_h"]) // 2,
            )
        self.configure_outlined_text(
            self.text_canvas,
            self.status_text_items,
            x=int(size_config["text_x"]),
            y=int(size_config["status_y"]),
            font=size_config["status_font"],
        )
        self.configure_outlined_text(
            self.text_canvas,
            self.connection_text_items,
            x=int(size_config["text_x"]),
            y=int(size_config["connection_y"]),
            font=size_config["connection_font"],
        )

    def start_drag(self, event: tk.Event) -> None:
        # 记录鼠标按下时相对于窗口左上角的偏移。
        self.drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def drag(self, event: tk.Event) -> None:
        # 根据鼠标移动位置更新窗口坐标。
        if self.drag_origin is None:
            return
        x_offset, y_offset = self.drag_origin
        self.root.geometry(f"+{event.x_root - x_offset}+{event.y_root - y_offset}")

    def show_menu(self, event: tk.Event) -> None:
        self.rebuild_menu()
        self.menu.tk_popup(event.x_root, event.y_root)

    def rebuild_menu(self) -> None:
        # 右键菜单每次打开前重建，确保语言切换后菜单文字立即更新。
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
        self.size_menu = Menu(self.menu, tearoff=False)
        self.size_menu.add_command(label=text["small"], command=lambda: self.set_size("small"))
        self.size_menu.add_command(label=text["medium"], command=lambda: self.set_size("medium"))
        self.size_menu.add_command(label=text["large"], command=lambda: self.set_size("large"))
        self.menu.add_cascade(label=text["size"], menu=self.size_menu)
        self.menu.add_separator()
        self.menu.add_command(label=text["open_state"], command=self.open_state_folder)
        self.menu.add_command(label=text["exit"], command=self.root.destroy)

    def set_language(self, language: str) -> None:
        # 切换语言后写入状态文件，重启后也会保留。
        self.language = normalize_language(language)
        write_status(language=self.language)
        self.rebuild_menu()
        self.apply_status()

    def set_size(self, ui_size: str) -> None:
        # 切换大小后立即重排窗口，并把大小写入状态文件。
        self.ui_size = normalize_ui_size(ui_size)
        write_status(ui_size=self.ui_size)
        self.apply_window_size()
        self.rebuild_menu()
        self.apply_status()

    def manual_set(self, status: str) -> None:
        # 菜单里的手动红/黄/绿测试入口。
        write_status(status, status_label(status, self.language), language=self.language)
        self.apply_status()

    def open_state_folder(self) -> None:
        folder = status_path().parent
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(folder)])

    def poll(self) -> None:
        # 主轮询：检测新对话、会话文件变化、授权等待，然后刷新 UI。
        self.detect_new_codex_prompt()
        self.track_session_activity()
        self.sync_codex_lifecycle_status()
        self.apply_status()
        self.root.after(POLL_MS, self.poll)

    def read_prompt_history_count(self) -> int:
        # Codex 桌面会把输入历史写入全局状态文件；数量增加说明用户刚提交了新消息。
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
        # 一旦发现用户提交了新 prompt，先切红灯，表示 Codex 正在处理。
        current_count = self.read_prompt_history_count()
        if current_count > self.prompt_history_count:
            write_status("red", status_label("red", self.language), language=self.language)
            self.last_session_mtime = self.latest_session_mtime()
            self.session_quiet_since = time.time()
        self.prompt_history_count = max(self.prompt_history_count, current_count)

    def latest_session_mtime(self) -> float:
        # 找到最近更新的 Codex session jsonl 文件时间，用于判断会话是否活跃。
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
        # 通过 Windows tasklist 检测 Codex 主进程是否存在，用于连接状态文字。
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
        # 只扫描最近几个 session 文件，降低轮询成本。
        if not CODEX_SESSIONS_ROOT.exists():
            return []
        try:
            files = list(CODEX_SESSIONS_ROOT.rglob("*.jsonl"))
        except OSError:
            return []
        files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return files[:3]

    def parse_timestamp(self, value: object) -> float:
        # Codex 事件时间通常是 ISO 字符串，这里转成秒级时间戳方便比较。
        if not isinstance(value, str):
            return 0.0
        try:
            parsed = value.replace("Z", "+00:00")
            return __import__("datetime").datetime.fromisoformat(parsed).timestamp()
        except Exception:
            return 0.0

    def recent_session_lines(self, path: Path) -> list[str]:
        # session 文件可能很大，只读末尾一段，足够判断最近的任务和授权状态。
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
        # 如果发现 require_escalated 的 function_call 还没有对应 output，就认为在等授权。
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
        # 通过 task_started/task_complete 配对判断 Codex 是否仍在处理任务。
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
        # 优先级：授权等待黄灯 > 任务进行红灯 > 空闲绿灯。
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
        # 把状态文件里的 status/language/ui_size 真正应用到窗口显示。
        data = read_status()
        self.language = normalize_language(data.get("language"))
        next_size = normalize_ui_size(data.get("ui_size"))
        if next_size != self.ui_size:
            self.ui_size = next_size
            self.apply_window_size()
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
        if self.light_item is not None and self.ui_size in self.status_images and active in self.status_images[self.ui_size]:
            self.canvas.itemconfig(self.light_item, image=self.status_images[self.ui_size][active])
        else:
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
