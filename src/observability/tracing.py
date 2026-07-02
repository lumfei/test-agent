"""
LangFuse tracing integration for agent observability.
Traces every node execution, token usage, and test execution.
"""
from __future__ import annotations

import time
import functools
from contextlib import contextmanager
from typing import Any

from src.config import config

# LangFuse is optional — gracefully degrade if not configured
_langfuse = None
_langfuse_available = False

try:
    if config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY:
        from langfuse import Langfuse
        _langfuse = Langfuse(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            host=config.LANGFUSE_HOST,
        )
        _langfuse_available = True
except Exception:
    pass


class TraceManager:
    """Manages LangFuse tracing for agent nodes and tool calls."""

    def __init__(self):
        self._trace = None
        self._current_node: str | None = None
        self._node_spans: dict[str, Any] = {}
        self._start_time: float = 0.0

    @property
    def available(self) -> bool:
        return _langfuse_available and _langfuse is not None

    def start_trace(self, name: str, metadata: dict[str, Any] | None = None):
        """Start a new trace for an agent run."""
        if not self.available:
            return
        self._start_time = time.time()
        self._trace = _langfuse.trace(name=name, metadata=metadata or {})

    def end_trace(self, output: dict[str, Any] | None = None):
        """End the current trace."""
        if not self.available or not self._trace:
            return
        duration = time.time() - self._start_time
        self._trace.update(
            output=output or {},
            metadata={"duration_seconds": round(duration, 2)},
        )
        _langfuse.flush()
        self._trace = None

    def start_node(self, node_name: str, input_data: dict[str, Any] | None = None):
        """Start a span for a graph node."""
        if not self.available or not self._trace:
            return
        span = self._trace.span(name=node_name, input=input_data)
        self._node_spans[node_name] = span
        self._current_node = node_name

    def end_node(self, node_name: str, output_data: dict[str, Any] | None = None):
        """End a node span."""
        if not self.available:
            return
        span = self._node_spans.pop(node_name, None)
        if span:
            span.update(output=output_data or {})
            span.end()

    def log_tool_call(self, tool_name: str, input_data: Any, output_data: Any, duration_ms: float):
        """Log a tool call within the current node."""
        if not self.available or not self._trace:
            return
        self._trace.event(
            name=f"tool:{tool_name}",
            input={"args": str(input_data)[:500]},
            output={"result": str(output_data)[:500]},
            metadata={"duration_ms": duration_ms},
        )

    def log_llm_call(self, model: str, tokens_in: int, tokens_out: int, duration_ms: float):
        """Log LLM token usage."""
        if not self.available:
            return
        self._trace.generation(
            name=f"llm:{model}",
            model=model,
            usage={
                "input": tokens_in,
                "output": tokens_out,
                "total": tokens_in + tokens_out,
            },
            metadata={"duration_ms": duration_ms},
        )

    def log_error(self, error_msg: str):
        """Log an error event."""
        if not self.available or not self._trace:
            return
        self._trace.event(name="error", level="ERROR", metadata={"error": error_msg})


# Decorator for tracing async node functions
def trace_node(node_name: str):
    """Decorator that wraps an async node function with LangFuse tracing."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(state: dict, *args, **kwargs):
            from src.observability import trace_manager
            trace_manager.start_node(node_name, {
                "current_node": state.get("current_node", ""),
                "spec_url": state.get("spec_url", ""),
            })
            t0 = time.time()
            try:
                result = await func(state, *args, **kwargs)
                elapsed = (time.time() - t0) * 1000
                trace_manager.end_node(node_name, {
                    "success": not result.get("error"),
                    "error": result.get("error", ""),
                    "duration_ms": elapsed,
                })
                return result
            except Exception as e:
                elapsed = (time.time() - t0) * 1000
                trace_manager.log_error(f"{node_name}: {e}")
                trace_manager.end_node(node_name, {"error": str(e), "duration_ms": elapsed})
                raise
        return wrapper
    return decorator


# Convenience context manager
@contextmanager
def trace_span(name: str, **metadata):
    """Context manager for a named trace span."""
    from src.observability import trace_manager
    trace_manager.start_node(name, metadata)
    t0 = time.time()
    try:
        yield
    finally:
        elapsed = (time.time() - t0) * 1000
        trace_manager.end_node(name, {"duration_ms": elapsed})
