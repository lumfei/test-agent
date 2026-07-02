"""
节点 2：Analyze API — LLM 分析 API 结构并确定测试策略。
"""
from __future__ import annotations

import json

from src.agent.state import AgentState
from src.llm import llm
from src.prompts import prompt_registry
from src.observability import cost_tracker

ANALYZE_SYSTEM_PROMPT = prompt_registry.get_system_prompt(
    "analyze_api",
    """你是一个资深的 API 测试架构师。分析给定的 API 规范，输出测试策略。

## 任务
1. 识别所有 API 端点及其风险等级
2. 确定测试优先级（高风险端点优先）
3. 识别认证方式
4. 给出测试覆盖策略建议

## 输出格式（严格 JSON）
{
  "api_overview": "API 整体描述（一句话）",
  "auth_analysis": "认证分析",
  "total_endpoints": 0,
  "high_priority": ["端点1", "端点2"],
  "risk_areas": ["风险点1", "风险点2"],
  "test_strategy": "推荐的测试策略",
  "prioritized_endpoints": [
    {
      "path": "/api/xxx",
      "method": "GET",
      "priority": "high",
      "reason": "核心业务端点"
    }
  ]
}""",
)


async def analyze_api_node(state: AgentState) -> AgentState:
    """
    分析 API 结构。

    输入: parsed_spec_summary, endpoints
    产出: analysis_report, endpoints_prioritized
    """
    state["current_node"] = "analyze"

    spec_summary = state.get("parsed_spec_summary", "")
    endpoints = state.get("endpoints", [])

    if not spec_summary:
        state["error"] = "无 API 规范可分析"
        return state

    # LLM 分析 API 结构
    user_msg = f"""请分析以下 API 规范并给出测试策略：

## API 规范摘要
{spec_summary}

## 端点 JSON 列表
{json.dumps(endpoints, ensure_ascii=False, indent=2)[:6000]}
"""

    response = llm.chat_with_tools(
        system_prompt=ANALYZE_SYSTEM_PROMPT,
        user_message=user_msg,
        tools=[],  # 本节点不需要工具
        temperature=0.2,
        max_tokens=2048,
    )

    # Track LLM cost
    usage = response.get('usage', {})
    cost_tracker.record(
        model=response.get('model', 'deepseek-chat'),
        tokens_in=usage.get('prompt_tokens', 0),
        tokens_out=usage.get('completion_tokens', 0),
    )

    content = llm.extract_content(response)

    # 尝试提取 JSON 分析结果
    try:
        analysis = _extract_json(content)
        state["analysis_report"] = json.dumps(analysis, ensure_ascii=False, indent=2)
        state["endpoints_prioritized"] = analysis.get("prioritized_endpoints", endpoints)
    except (json.JSONDecodeError, ValueError):
        state["analysis_report"] = content
        state["endpoints_prioritized"] = endpoints  # fallback: 保持原顺序

    return state


def _extract_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON（处理 markdown 代码块包装）"""
    text = text.strip()

    # 移除 markdown 代码块
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    return json.loads(text.strip())
