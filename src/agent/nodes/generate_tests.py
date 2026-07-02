"""
节点 3：Generate Tests — 基于 API 规范生成完整测试用例套件。
"""
from __future__ import annotations

import json

from src.agent.state import AgentState
from src.llm import llm
from src.tools import test_data_gen
from src.tools.test_data_gen import TestSuite
from src.prompts import prompt_registry
from src.observability import cost_tracker

GENERATE_SYSTEM_PROMPT = prompt_registry.get_system_prompt(
    "generate_tests",
    """你是一个 API 测试用例设计专家。根据 API 端点定义生成全面的测试用例。

## 测试用例类别
1. **normal** — 正常场景（合法参数、期望成功）
2. **boundary** — 边界场景（空值、极限值、特殊字符、Unicode）
3. **error** — 异常场景（错误方法、错误 Content-Type、缺少必填参数、畸形 JSON）
4. **security** — 安全场景（SQL 注入、XSS、无认证访问、无效 Token）

## 规则
- 每个端点至少生成 4 个用例（每类至少 1 个）
- 核心业务端点（标记为 high priority）加倍
- 输出严格 JSON 数组""",
)


async def generate_tests_node(state: AgentState) -> AgentState:
    """
    生成测试用例。

    输入: endpoints (原始含完整 schema), endpoints_prioritized (LLM 优先级), base_url, api_name
    产出: test_cases

    重要：用原始 endpoints 生成测试（含完整 schema），只用 LLM 的 prioritized_endpoints
    来确定优先级顺序。LLM 返回的端点列表可能丢失 request_body_schema/parameters 等字段。
    """
    state["current_node"] = "generate"

    raw_endpoints = state.get("endpoints", [])
    prioritized = state.get("endpoints_prioritized", [])
    base_url = state.get("base_url", "")
    api_name = state.get("api_name", "Unknown API")
    auth_required = state.get("auth_required", False)
    auth_config = state.get("auth_config", {})

    if not raw_endpoints:
        state["error"] = "无 API 端点可生成测试用例"
        return state

    # 构建原始端点 lookup: (method, path) → endpoint dict
    endpoint_map: dict[str, dict] = {}
    for ep in raw_endpoints:
        key = f"{ep.get('method', '')}:{ep.get('path', '')}"
        endpoint_map[key] = ep

    # 给原始端点加上 LLM 的优先级
    priority_map: dict[str, str] = {}
    for ep in prioritized:
        key = f"{ep.get('method', '')}:{ep.get('path', '')}"
        priority_map[key] = ep.get("priority", "medium")

    # 合并：原始端点 + LLM 优先级
    endpoints: list[dict] = []
    for ep in raw_endpoints:
        key = f"{ep.get('method', '')}:{ep.get('path', '')}"
        ep_with_priority = dict(ep)
        ep_with_priority["priority"] = priority_map.get(key, ep.get("priority", "medium"))
        endpoints.append(ep_with_priority)

    # 按优先级排序
    prio_order = {"high": 0, "medium": 1, "low": 2}
    endpoints.sort(key=lambda e: prio_order.get(e.get("priority", "medium"), 1))

    all_cases: list[dict] = []

    for ep in endpoints[:20]:  # 最多处理 20 个端点
        method = ep.get("method", "GET")
        path = ep.get("path", "/")
        parameters = ep.get("parameters", [])
        request_body_schema = ep.get("request_body_schema")
        success_status = ep.get("success_status", 200)
        priority = ep.get("priority", "medium")

        # 使用 TestDataGenerator 自动生成测试数据
        suite: TestSuite = test_data_gen.generate_full_suite(
            api_name=f"{api_name} - {method} {path}",
            base_url=base_url,
            method=method,
            path=path,
            parameters=parameters,
            request_body_schema=request_body_schema,
            success_status=success_status,
            auth_required=auth_required,
        )

        # 根据优先级调整用例数量
        cases_to_add = suite.cases
        if priority == "high":
            # 核心端点：额外用 LLM 生成更多针对性的用例
            extra_cases = await _llm_generate_extra_cases(
                api_name, base_url, method, path, parameters, request_body_schema
            )
            cases_to_add.extend(extra_cases)

        # 序列化
        for tc in cases_to_add:
            all_cases.append({
                "name": tc.name,
                "description": tc.description,
                "method": tc.method,
                "path": tc.path,
                "params": tc.params,
                "body": tc.body,
                "headers": tc.headers,
                "expected_status": tc.expected_status,
                "expected_schema": tc.expected_schema,
                "priority": priority,
                "category": tc.category,
                "tags": tc.tags,
            })

    state["test_cases"] = all_cases
    return state


async def _llm_generate_extra_cases(
    api_name: str,
    base_url: str,
    method: str,
    path: str,
    parameters: list[dict],
    request_body_schema: dict | None,
) -> list:
    """使用 LLM 为核心端点生成额外的针对性测试用例"""
    user_msg = f"""为以下 API 端点额外生成 2-3 个高价值的测试用例（侧重业务逻辑边界）：

- API: {api_name}
- Base URL: {base_url}
- 端点: {method} {path}
- 参数: {json.dumps(parameters, ensure_ascii=False)[:2000]}
- 请求体 Schema: {json.dumps(request_body_schema, ensure_ascii=False)[:2000] if request_body_schema else "无"}

输出格式（严格 JSON 数组）：
[
  {{
    "name": "用例名称",
    "description": "描述",
    "method": "{method}",
    "path": "{path}",
    "params": {{}},
    "body": {{}},
    "expected_status": 200,
    "category": "normal",
    "tags": ["llm-generated"]
  }}
]"""

    try:
        response = llm.chat_with_tools(
            system_prompt=GENERATE_SYSTEM_PROMPT,
            user_message=user_msg,
            temperature=0.4,
            max_tokens=2048,
        )
        usage = response.get('usage', {})
        cost_tracker.record(
            model=response.get('model', 'deepseek-chat'),
            tokens_in=usage.get('prompt_tokens', 0),
            tokens_out=usage.get('completion_tokens', 0),
        )
        content = llm.extract_content(response)
        # 移除 markdown 代码块
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())
    except Exception:
        return []
