"""
LangGraph 状态定义 — Agent 在所有节点间传递的共享状态。
"""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver

from src.memory.sqlite_checkpoint import SQLiteSaver
from src.config import config


class AgentState(TypedDict, total=False):
    """
    LangGraph 共享状态。

    各节点读取需要的字段，写入产出的字段。
    使用 TypedDict + total=False 使所有字段可选的（每个节点只写自己产出的字段）。
    """

    # === 输入 ===
    spec_url: str                       # 用户输入的 API 文档 URL
    spec_content: str                   # 原始 Spec 内容（JSON/YAML/HTML）
    auth_config: dict[str, Any]         # 认证配置 {"type": "bearer", "token": "xxx"}

    # === Parse 阶段产出 ===
    parsed_spec_summary: str            # LLM 可读的 API 摘要
    endpoints: list[dict[str, Any]]     # 端点列表（可序列化的 dict）
    base_url: str                       # API 基础 URL
    api_name: str                       # API 名称
    auth_required: bool                 # 是否需要认证

    # === Analyze 阶段产出 ===
    analysis_report: str                # LLM 分析报告
    endpoints_prioritized: list[dict[str, Any]]  # 按优先级排序的端点

    # === Generate 阶段产出 ===
    test_cases: list[dict[str, Any]]    # 所有测试用例

    # === Execute 阶段产出 ===
    execution_results: list[dict[str, Any]]  # 执行结果
    execution_errors: list[dict[str, Any]]   # 执行错误

    # === Validate & Report 阶段产出 ===
    validation_results: list[dict[str, Any]]  # 验证结果
    report_path: str                    # 报告文件路径
    report_summary: str                 # 报告摘要

    # === Reflect (ReAct) 阶段产出 ===
    reflect_iteration: int              # 当前反思轮次
    regenerated_cases: list[dict[str, Any]]  # LLM 修正后需重新执行的用例

    # === 元信息 ===
    started_at: str                     # 开始时间
    error: str                          # 全局错误信息
    current_node: str                   # 当前节点名


def _create_checkpointer():
    """Create the appropriate checkpointer based on config.

    Tries SQLiteSaver first for persistence. Falls back to MemorySaver
    if SQLite is unavailable or throws errors during operation.
    """
    # Always use MemorySaver for now — SQLiteSaver needs aiosqlite thread safety work.
    # To enable persistence, fix the SQLiteSaver threading or use PostgresSaver.
    return MemorySaver()


# 全局 checkpointer 实例（SQLite 持久化，fallback 内存）
memory = _create_checkpointer()
