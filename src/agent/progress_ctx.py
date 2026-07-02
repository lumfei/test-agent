"""
进度回调上下文 — 通过 contextvars 在 LangGraph 节点间传递 progress callback。

不能放入 AgentState：callback 是函数，无法被 checkpoint 序列化（msgpack）。
contextvars 天然避开序列化，且支持 asyncio 并发隔离。
"""
from __future__ import annotations

import contextvars

_progress_cb_ctx: contextvars.ContextVar = contextvars.ContextVar(
    "progress_callback", default=None
)
