"""
轻量级进程内事件总线 — 用于 SSE 流式推送测试进度。

每个 run_id 维护一个 asyncio.Queue，消费者通过 SSE 订阅。
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone


class EventBus:
    """进程内 Pub/Sub，按 run_id 隔离。"""

    def __init__(self) -> None:
        # run_id -> list[asyncio.Queue]
        self._subscribers: dict[str, list[asyncio.Queue[str]]] = defaultdict(list)

    def subscribe(self, run_id: str) -> asyncio.Queue[str]:
        """注册一个订阅者，返回其消息队列。"""
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=256)
        self._subscribers[run_id].append(q)
        return q

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[str]) -> None:
        """取消订阅。"""
        subs = self._subscribers.get(run_id, [])
        if queue in subs:
            subs.remove(queue)
        if not subs:
            self._subscribers.pop(run_id, None)

    async def publish(self, run_id: str, event: str, data: dict | str) -> None:
        """向所有订阅者推送事件。"""
        payload = json.dumps({
            "event": event,
            "data": data if isinstance(data, dict) else {"message": data},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, ensure_ascii=False)

        dead_queues: list[asyncio.Queue[str]] = []
        for q in self._subscribers.get(run_id, []):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                # 消费者太慢，丢弃旧消息后重试
                try:
                    q.get_nowait()
                    q.put_nowait(payload)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass
            except Exception:
                dead_queues.append(q)

        for q in dead_queues:
            self.unsubscribe(run_id, q)

    async def publish_progress(self, run_id: str, node: str, progress: float, message: str = "") -> None:
        """推送进度事件。"""
        await self.publish(run_id, "progress", {
            "node": node,
            "progress": progress,
            "message": message,
        })

    async def publish_case_result(self, run_id: str, case: dict) -> None:
        """推送单个用例执行结果。"""
        await self.publish(run_id, "case_result", {
            "case_name": case.get("case_name", case.get("name", "")),
            "passed": case.get("passed", False),
            "method": case.get("method", ""),
            "path": case.get("path", ""),
            "status_code": case.get("status_code", 0),
            "elapsed_ms": case.get("elapsed_ms", 0),
            "category": case.get("category", ""),
        })

    async def publish_completed(self, run_id: str, summary: dict) -> None:
        """推送完成事件。"""
        await self.publish(run_id, "completed", summary)

    async def publish_error(self, run_id: str, error: str) -> None:
        """推送错误事件。"""
        await self.publish(run_id, "error", error)


# 全局单例
event_bus = EventBus()
