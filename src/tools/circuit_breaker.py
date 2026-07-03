"""
Circuit Breaker（熔断器）— 连续失败 N 次自动切断，防止雪崩。

三态模型：CLOSED → OPEN → HALF_OPEN → CLOSED

使用场景：
- 被测 API 连续返回 5xx → 熔断，不再浪费请求
- 冷却期后发送探测请求 → 成功则恢复，失败则继续熔断
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CircuitState(Enum):
    CLOSED = "closed"          # 正常通行
    OPEN = "open"              # 熔断——直接拒绝
    HALF_OPEN = "half_open"    # 半开——允许一个探测请求


@dataclass
class BreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5      # 连续失败 N 次后熔断
    timeout_seconds: float = 30.0   # 熔断后冷却时间（秒）
    half_open_probe_limit: int = 1  # 半开状态下最多允许几个探测请求
    enabled: bool = True


@dataclass
class BreakerStats:
    """熔断器统计"""
    state: str = "closed"
    total_failures: int = 0
    total_successes: int = 0
    times_opened: int = 0
    last_failure_time: float = 0.0
    last_failure_reason: str = ""


class CircuitBreaker:
    """
    熔断器——三态自动切换，带 HALF_OPEN 探测限制。

    工作原理：
    1. CLOSED（正常）: 所有请求通过。连续失败达到 threshold → OPEN
    2. OPEN（熔断）: 所有请求直接拒绝。冷却 timeout_seconds → HALF_OPEN
    3. HALF_OPEN（半开）: 最多允许 probe_limit 个探测请求。
       探测成功 → CLOSED；失败 → OPEN
    """

    def __init__(self, host: str = "default", config: BreakerConfig | None = None):
        self.host = host
        self.config = config or BreakerConfig()
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._consecutive_successes = 0  # 连续成功计数
        self._opened_at: float = 0.0
        self._last_failure_reason: str = ""
        self._times_opened: int = 0
        self._total_failures: int = 0
        self._total_successes: int = 0
        self._half_open_probes: int = 0  # HALF_OPEN 状态下的探测计数
        self._lock = None  # lazy init asyncio.Lock

    def _get_lock(self):
        """延迟创建 asyncio.Lock（避免在非 async 上下文创建）"""
        import asyncio
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _try_enter_half_open(self) -> bool:
        """
        尝试从 OPEN 进入 HALF_OPEN。

        返回 True 如果冷却完成且成功过渡到 HALF_OPEN。
        此方法不持锁——can_pass 在 _check_state 中调用。
        """
        if self.state != CircuitState.OPEN:
            return False
        if time.monotonic() - self._opened_at >= self.config.timeout_seconds:
            self.state = CircuitState.HALF_OPEN
            self._half_open_probes = 0
            return True
        return False

    @property
    def can_pass(self) -> bool:
        """
        检查请求是否可以通过。

        HALF_OPEN 状态下限制探测数量：最多 probe_limit 个。
        """
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            # 检查冷却时间是否已过
            self._try_enter_half_open()
        if self.state == CircuitState.OPEN:
            return False
        # HALF_OPEN: 限制探测数量
        if self._half_open_probes >= self.config.half_open_probe_limit:
            return False
        self._half_open_probes += 1
        return True

    def record_success(self):
        """记录一次成功的请求"""
        self._total_successes += 1

        if self.state == CircuitState.HALF_OPEN:
            self._consecutive_successes += 1
            # 探测成功 → 恢复正常
            if self._consecutive_successes >= 1:
                self.state = CircuitState.CLOSED
                self._failure_count = 0
                self._consecutive_successes = 0
        elif self.state == CircuitState.CLOSED:
            self._failure_count = 0  # 重置连续失败计数
            self._consecutive_successes += 1

    def record_failure(self, reason: str = ""):
        """记录一次失败的请求"""
        self._total_failures += 1
        self._last_failure_reason = reason
        self._consecutive_successes = 0

        if self.state == CircuitState.HALF_OPEN:
            # 半开状态下探测失败 → 重新熔断
            self.state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            self._times_opened += 1
        elif self.state == CircuitState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                self._times_opened += 1

    def reset(self):
        """手动重置熔断器"""
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._consecutive_successes = 0
        self._half_open_probes = 0
        self._opened_at = 0.0

    @property
    def stats(self) -> BreakerStats:
        """获取统计信息"""
        return BreakerStats(
            state=self.state.value,
            total_failures=self._total_failures,
            total_successes=self._total_successes,
            times_opened=self._times_opened,
            last_failure_time=self._opened_at,
            last_failure_reason=self._last_failure_reason,
        )


class CircuitBreakerRegistry:
    """
    熔断器注册表 — 按 host 管理多个断路器实例。

    相同 host 的请求共享同一个熔断器。
    """

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._config = BreakerConfig()

    def get(self, host: str) -> CircuitBreaker:
        """获取或创建指定 host 的熔断器"""
        if host not in self._breakers:
            self._breakers[host] = CircuitBreaker(host=host, config=self._config)
        return self._breakers[host]

    def reset_all(self):
        """重置所有熔断器"""
        for breaker in self._breakers.values():
            breaker.reset()

    @property
    def all_stats(self) -> dict[str, BreakerStats]:
        """获取所有熔断器统计"""
        return {host: b.stats for host, b in self._breakers.items()}


# 全局注册表（配置来自 config.py）
from src.config import config as _cfg
breaker_registry = CircuitBreakerRegistry()
breaker_registry._config = BreakerConfig(
    failure_threshold=_cfg.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    timeout_seconds=_cfg.CIRCUIT_BREAKER_TIMEOUT,
)
