"""
LangGraph 状态图 — Agent 的完整执行流程。

节点: Parse → Analyze → Generate → Execute → Validate → Reflect ↻ Execute
                                                              ↘ END

内建 ReAct 循环：失败用例经 LLM 反思后自动修正并重试（最多 2 轮）。
每个节点间有 checkpoint，支持断点续跑和时间旅行调试。
"""
from __future__ import annotations

import json
from typing import Any, Literal

from langgraph.graph import StateGraph, END
from loguru import logger

from src.agent.state import AgentState, memory
from src.agent.progress_ctx import _progress_cb_ctx
from src.agent.nodes import (
    parse_spec_node,
    analyze_api_node,
    generate_tests_node,
    execute_tests_node,
    validate_report_node,
    reflect_node,
)


def should_continue_after_parse(state: AgentState) -> Literal["analyze", "error"]:
    """Parse 节点后的路由判断"""
    if state.get("error"):
        return "error"
    return "analyze"


def should_continue_after_analyze(state: AgentState) -> Literal["generate", "error"]:
    """Analyze 节点后的路由判断"""
    if state.get("error"):
        return "error"
    return "generate"


def should_continue_after_generate(state: AgentState) -> Literal["execute", "error"]:
    """Generate 节点后的路由判断"""
    if state.get("error"):
        return "error"
    if not state.get("test_cases"):
        return "error"
    return "execute"


def should_continue_after_execute(state: AgentState) -> Literal["validate", "error"]:
    """Execute 节点后的路由判断"""
    if state.get("error"):
        return "error"
    return "validate"


def should_continue_after_reflect(state: AgentState) -> Literal["execute", "end"]:
    """
    Reflect 节点后的路由判断 — ReAct 循环入口。

    如果 LLM 生成了修正后的测试用例且未达到最大迭代次数 → 回到 Execute 重试
    否则 → 结束

    双重保护（防无限循环）：
    1. reflect_node 内部在达到 MAX 时清空 regenerated_cases
    2. 本函数额外检查迭代次数作为纵深防御
    """
    from src.agent.nodes.reflect import MAX_REFLECT_ITERATIONS
    regenerated = state.get("regenerated_cases", [])
    iteration = state.get("reflect_iteration", 0)
    if regenerated and iteration < MAX_REFLECT_ITERATIONS:
        return "execute"
    return "end"


def build_graph() -> StateGraph:
    """构建 Agent 状态图（含 ReAct 反思循环）"""
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("parse", parse_spec_node)
    workflow.add_node("analyze", analyze_api_node)
    workflow.add_node("generate", generate_tests_node)
    workflow.add_node("execute", execute_tests_node)
    workflow.add_node("validate", validate_report_node)
    workflow.add_node("reflect", reflect_node)
    workflow.add_node("error", error_node)

    # 设置入口
    workflow.set_entry_point("parse")

    # 添加边
    workflow.add_conditional_edges("parse", should_continue_after_parse, {
        "analyze": "analyze",
        "error": "error",
    })
    workflow.add_conditional_edges("analyze", should_continue_after_analyze, {
        "generate": "generate",
        "error": "error",
    })
    workflow.add_conditional_edges("generate", should_continue_after_generate, {
        "execute": "execute",
        "error": "error",
    })
    workflow.add_conditional_edges("execute", should_continue_after_execute, {
        "validate": "validate",
        "error": "error",
    })

    # Validate → Reflect（ReAct 反思，可能回到 Execute）
    workflow.add_edge("validate", "reflect")

    # Reflect → Execute（修正后重试）或 → END
    workflow.add_conditional_edges("reflect", should_continue_after_reflect, {
        "execute": "execute",
        "end": END,
    })

    workflow.add_edge("error", END)

    # 编译（带 checkpoint，支持断点续跑）
    graph = workflow.compile(checkpointer=memory)
    return graph


async def error_node(state: AgentState) -> AgentState:
    """错误节点：记录错误信息后终止"""
    state["current_node"] = "error"
    if not state.get("error"):
        state["error"] = "未知错误"
    return state


# 全局图实例
agent_graph = build_graph()


# 节点进度映射：(node_name, progress_pct, message)
_NODE_PROGRESS = [
    ("parse", 0.10, "正在解析 API 文档..."),
    ("analyze", 0.25, "LLM 正在分析端点风险等级..."),
    ("generate", 0.45, "LLM 正在生成测试用例..."),
    ("execute", 0.65, "正在发送 HTTP 请求..."),
    ("validate", 0.90, "正在验证结果 & 生成报告..."),
    ("reflect", 0.95, "ReAct 反思: LLM 分析失败用例..."),
]


async def run_agent(
    spec_url: str,
    auth_config: dict[str, Any] | None = None,
    thread_id: str | None = None,
    progress_callback: Any = None,
) -> dict[str, Any]:
    """
    运行完整 Agent Pipeline。

    Args:
        spec_url: API 文档 URL（OpenAPI JSON/YAML 或 Swagger 页面 URL）
        auth_config: 认证配置
        thread_id: LangGraph 线程 ID（用于断点续跑）
        progress_callback: async callable(node, pct, msg) — 进度回调

    Returns:
        最终状态字典（含报告路径和摘要）
    """
    import uuid
    import time
    from datetime import datetime, timezone
    from src.observability import trace_manager, cost_tracker

    run_id = thread_id or uuid.uuid4().hex[:8]
    logger.info(f"Agent pipeline 启动 | run_id={run_id} | spec_url={spec_url}")

    # Start LangFuse trace
    trace_manager.start_trace(
        name=f"api-test:{run_id}",
        metadata={"spec_url": spec_url, "thread_id": run_id},
    )
    cost_tracker.reset()
    t0 = time.time()

    initial_state: AgentState = {
        "spec_url": spec_url,
        "auth_config": auth_config or {},
        "started_at": datetime.now(timezone.utc).isoformat(),
        "current_node": "parse",
    }

    # 将 progress callback 注入 contextvars（供 execute 节点使用）
    # 不能放入 state — LangGraph checkpoint 会尝试 msgpack 序列化 function
    token = None
    if progress_callback is not None:
        token = _progress_cb_ctx.set(progress_callback)

    config = {"configurable": {"thread_id": run_id}}

    try:
        if progress_callback is not None:
            # 使用 astream 获取每个节点完成后的状态
            final_state = dict(initial_state)  # type: ignore[arg-type]
            node_idx = 0
            async for chunk in agent_graph.astream(initial_state, config, stream_mode="values"):
                final_state = chunk  # type: ignore[assignment]
                current = final_state.get("current_node", "")
                # 在节点完成时推送进度（execute 节点内部已自行推送子进度，跳过）
                if node_idx < len(_NODE_PROGRESS):
                    expected_node, pct, msg = _NODE_PROGRESS[node_idx]
                    if current == expected_node:
                        if expected_node != "execute":
                            await progress_callback(expected_node, pct, msg)
                        node_idx += 1
        else:
            final_state = await agent_graph.ainvoke(initial_state, config)
    except Exception as e:
        logger.exception(f"Agent pipeline 异常 | run_id={run_id}")
        trace_manager.log_error(str(e))
        trace_manager.end_trace({"error": str(e)})
        raise
    finally:
        if token is not None:
            _progress_cb_ctx.reset(token)

    # End trace with summary
    elapsed_s = time.time() - t0
    results = final_state.get("execution_results", [])
    passed = sum(1 for r in results if r.get("passed"))
    total = max(len(results), 1)

    trace_manager.end_trace({
        "api_name": final_state.get("api_name", ""),
        "endpoints": len(final_state.get("endpoints", [])),
        "test_cases": len(final_state.get("test_cases", [])),
        "executed": total,
        "passed": passed,
        "pass_rate": round(passed / total * 100, 1),
        "duration_s": round(elapsed_s, 1),
        "cost": cost_tracker.summary(),
    })

    logger.info(
        f"Agent pipeline 完成 | run_id={run_id} | api={final_state.get('api_name', 'N/A')} | "
        f"endpoints={len(final_state.get('endpoints', []))} | "
        f"cases={len(final_state.get('test_cases', []))} | "
        f"passed={passed}/{total} | duration={elapsed_s:.1f}s"
    )

    return final_state
