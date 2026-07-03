"""
Token Bucket Rate Limiter — 防止打爆被测 API。

基于令牌桶算法：匀速填充令牌，突发流量靠桶容量缓冲。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass
class RateLimiterConfig:
    """速率限制配置"""
    requests_per_second: float = 10.0   # 每秒允许的请求数
    burst_size: int = 20                # 最大突发请求数（桶容量）
    enabled: bool = True


class TokenBucket:
    """
    令牌桶速率限制器。

    工作原理：
    - 令牌以固定速率（requests_per_second）生成
    - 每次请求消耗一个令牌
    - 桶满时令牌不再增加（容量=burst_size）
    - 令牌不足时请求等待（不拒绝）

    使用示例：
        limiter = TokenBucket(rate=10, burst=20)
        async with limiter:
            await make_request()
    """

    def __init__(self, rate: float = 10.0, burst: int = 20):
        if rate <= 0:
            raise ValueError(f"rate must be > 0, got {rate}")
        if burst < 1:
            raise ValueError(f"burst must be >= 1, got {burst}")
        self.rate = rate                  # 令牌填充速率（个/秒）
        self.burst = burst                # 桶容量（最大令牌数）
        self._tokens = float(burst)       # 当前令牌数
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        self._total_waited = 0.0          # 累计等待时间（秒，统计用）
        self._acquire_count = 0           # 获取次数

    async def acquire(self):
        """
        获取一个令牌。如果当前没有令牌，等待直到有可用令牌。
        不会拒绝请求——只延迟。

        使用重试循环避免竞态：sleep 后其他协程可能抢先消费令牌，
        需要重新检查。
        """
        while True:
            async with self._lock:
                self._refill()
                self._acquire_count += 1

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

                # 计算需要等待的时间
                wait_time = (1.0 - self._tokens) / self.rate
                self._total_waited += wait_time

            # 在锁外等待，让其他协程有机会获取令牌
            await asyncio.sleep(wait_time)
            # 重试循环：醒来后重新竞争令牌

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        pass

    def _refill(self):
        """根据流逝的时间补充令牌"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_refill = now

    @property
    def available_tokens(self) -> float:
        """当前可用令牌数（近似值，不持锁）"""
        elapsed = time.monotonic() - self._last_refill
        return min(self.burst, self._tokens + elapsed * self.rate)

    @property
    def stats(self) -> dict:
        """统计信息"""
        return {
            "rate": self.rate,
            "burst": self.burst,
            "available_tokens": round(self.available_tokens, 1),
            "acquire_count": self._acquire_count,
            "total_waited_ms": round(self._total_waited * 1000, 1),
        }


# 全局速率限制器实例（配置来自 config.py）
from src.config import config as _cfg
default_limiter = TokenBucket(
    rate=_cfg.RATE_LIMIT_RPS,
    burst=_cfg.RATE_LIMIT_BURST,
)
