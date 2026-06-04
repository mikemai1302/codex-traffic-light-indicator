---
name: codex-traffic-light
description: Update the local Codex traffic light floating window. Use when a user wants the Codex status light changed, checked, or connected.
---

# Codex Traffic Light

Use the `codex-traffic-light` MCP tools to keep the floating indicator in sync with the Codex thread lifecycle:

- Green means there is no active Codex conversation task, or the previous task has finished.
- Red means the user has submitted a message and Codex is processing, thinking, editing, testing, browsing, or otherwise doing work.
- Yellow means Codex is waiting for the user to approve an authorization or permission prompt.

Preferred flow:

1. At the start of every user-submitted task, call `set_codex_light` with `status: "red"` and message `Codex 正在干活`.
2. Before any request for authorization, permission, or approval, call `set_codex_light` with `status: "yellow"` and message `Codex 等待授权`.
3. Before the final response, call `set_codex_light` with `status: "green"` and message `Codex 空闲中`.
4. Call `get_codex_light_status` when the user asks whether the floating window is connected or what it currently shows.

The floating window reads `D:\codex红绿灯提示灯\state\status.json`. Yellow is only kept while an authorization request is pending; otherwise it automatically returns to green.
