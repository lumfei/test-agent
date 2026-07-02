"""
节点 1：Parse Spec — 从 URL 获取并解析 API 规范。
"""
from __future__ import annotations

from src.agent.state import AgentState
from src.tools import spec_parser, web_fetcher


async def parse_spec_node(state: AgentState) -> AgentState:
    """
    解析 API 文档。

    输入: spec_url
    产出: spec_content, parsed_spec_summary, endpoints, base_url, api_name, auth_required
    """
    spec_url = state.get("spec_url", "")
    state["current_node"] = "parse"

    if not spec_url:
        state["error"] = "未提供 API 文档 URL"
        return state

    # 1. 使用 Web Fetcher 获取文档
    doc = await web_fetcher.fetch(spec_url)

    if doc.error and not doc.openapi_spec and not doc.text_content:
        state["error"] = f"无法获取 API 文档: {doc.error}"
        return state

    # 2. 如果直接获取到 OpenAPI Spec，解析它
    if doc.openapi_spec:
        try:
            parsed = spec_parser.parse(doc.openapi_spec)
            state["spec_content"] = doc.raw_content or ""

            # 如果 spec 没有声明 servers，从抓取 URL 推断 base_url
            base_url = parsed.base_url
            if not base_url:
                from urllib.parse import urlparse
                parsed_spec_url = urlparse(spec_url)
                base_url = f"{parsed_spec_url.scheme}://{parsed_spec_url.netloc}"

            state["parsed_spec_summary"] = spec_parser.to_summary_text(parsed, base_url)
            state["endpoints"] = [
                {
                    "path": ep.path,
                    "method": ep.method,
                    "summary": ep.summary,
                    "description": ep.description,
                    "operation_id": ep.operation_id,
                    "tags": ep.tags,
                    "parameters": ep.parameters,
                    "request_body_schema": ep.request_body_schema,
                    "success_status": ep.success_status,
                    "success_response_schema": ep.success_response_schema,
                    "security": ep.security,
                }
                for ep in parsed.endpoints
            ]
            state["base_url"] = base_url
            state["api_name"] = parsed.title
            state["auth_required"] = parsed.auth_required
            return state

        except Exception as e:
            state["error"] = f"解析 OpenAPI Spec 失败: {e}"
            return state

    # 3. 如果是 HTML 文档（纯文本），保留内容给后续 LLM 分析
    if doc.text_content:
        state["spec_content"] = doc.text_content
        state["base_url"] = spec_url
        state["api_name"] = spec_url
        state["auth_required"] = False
        state["parsed_spec_summary"] = (
            f"从 {doc.source_url} 提取的文档文本（{doc.source_type}）：\n\n"
            f"{doc.text_content[:8000]}"
        )
        state["endpoints"] = []
        return state

    state["error"] = "无法识别文档格式（非 OpenAPI Spec，非 HTML）"
    return state
