"""
Token cost tracker — tracks LLM usage and cost across agent runs.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


# Model pricing per 1M tokens (input, output)
# Update these as pricing changes
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "deepseek-chat": (0.14, 0.28),       # DeepSeek V4 Flash
    "deepseek-reasoner": (0.55, 2.19),    # DeepSeek R1
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


@dataclass
class CostRecord:
    """Single LLM call cost record."""
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    timestamp: float = field(default_factory=time.time)


class CostTracker:
    """Tracks cumulative LLM costs across an agent run."""

    def __init__(self):
        self.records: list[CostRecord] = []
        self._session_start = time.time()

    def record(self, model: str, tokens_in: int = 0, tokens_out: int = 0):
        """Record a single LLM call's token usage."""
        prices = MODEL_PRICING.get(model, (0.0, 0.0))
        cost = (tokens_in / 1_000_000) * prices[0] + (tokens_out / 1_000_000) * prices[1]
        self.records.append(CostRecord(
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=round(cost, 6),
        ))

    @property
    def total_tokens(self) -> dict[str, int]:
        return {
            "input": sum(r.tokens_in for r in self.records),
            "output": sum(r.tokens_out for r in self.records),
            "total": sum(r.tokens_in + r.tokens_out for r in self.records),
        }

    @property
    def total_cost_usd(self) -> float:
        return round(sum(r.cost_usd for r in self.records), 4)

    @property
    def total_cost_cny(self) -> float:
        return round(self.total_cost_usd * 7.2, 2)

    @property
    def call_count(self) -> int:
        return len(self.records)

    def summary(self) -> dict[str, Any]:
        return {
            "calls": self.call_count,
            "tokens": self.total_tokens,
            "cost_usd": self.total_cost_usd,
            "cost_cny": self.total_cost_cny,
            "models_used": list(set(r.model for r in self.records)),
            "duration_s": round(time.time() - self._session_start, 1),
        }

    def reset(self):
        """Reset for a new session."""
        self.records.clear()
        self._session_start = time.time()
