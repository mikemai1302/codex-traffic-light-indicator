# Codex 红绿灯提示灯

一个 Windows 桌面悬浮提示灯，用红、黄、绿三种状态显示 Codex 当前是否在工作、等待授权或空闲。它同时包含一个本地 Codex 插件和一个透明无边框悬浮窗。

## 效果

- 红灯：Codex 正在处理你的任务，包含思考、执行命令、读取文件、测试等。
- 黄灯：Codex 正在等待你同意授权或权限请求。
- 绿灯：没有正在进行的 Codex 任务，处于空闲状态。
- 连接文字：检测本机 Codex 进程，显示 `Codex：已成功连接` 或 `Codex：等待连接`。

悬浮窗没有系统窗口边框，背景透明，只保留红绿灯图案和文字。窗口置顶、可拖动，右键可退出或打开状态文件夹。

## 目录结构

```text
.codex-plugin/           Codex 插件 manifest
skills/                  Codex 技能说明，让 Codex 知道何时更新提示灯
scripts/
  traffic_light_window.py 透明悬浮窗
  mcp_server.py           本地 MCP server
  traffic_light_common.py 状态文件读写
  start_codex_traffic_light.bat
  test_set_red.bat
  test_set_yellow.bat
  test_set_green.bat
.mcp.json                Codex MCP 配置
```

## 安装和运行

当前配置默认使用这个 Windows 路径：

```text
D:\codex红绿灯提示灯
```

把项目放到该目录后，双击启动：

```bat
D:\codex红绿灯提示灯\scripts\start_codex_traffic_light.bat
```

也可以在桌面放一个启动脚本，内容如下：

```bat
@echo off
set "PYTHONUTF8=1"
cd /d "D:\codex红绿灯提示灯\scripts"
start "" pythonw "D:\codex红绿灯提示灯\scripts\traffic_light_window.py"
```

## 接入 Codex

插件名：

```text
codex-traffic-light
```

`.mcp.json` 会让 Codex 通过本地 MCP server 写入状态文件：

```text
D:\codex红绿灯提示灯\state\status.json
```

如果你把项目放在其他目录，需要同步修改 `.mcp.json` 里的脚本路径，以及 `CODEX_TRAFFIC_LIGHT_STATUS` 状态文件路径。

## 测试

启动悬浮窗后，可以运行：

```bat
scripts\test_set_red.bat
scripts\test_set_yellow.bat
scripts\test_set_green.bat
```

这些脚本用于测试灯色显示。真实 Codex 工作状态由悬浮窗扫描本机 Codex 会话事件和授权请求来判断。

## 说明

这个项目是为 Codex Desktop 本地使用制作的个人插件。它依赖 Windows、Python、Tkinter，以及 Codex 在本机写入的会话状态文件。
