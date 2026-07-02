"""
HTTP 请求执行器 — Agent 的核心工具。
支持所有 REST 方法、多种认证方式、自动重试、超时控制。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import config


@dataclass
class HTTPResponse:
    """HTTP 请求响应"""
    status_code: int
    headers: dict[str, str]
    body: Any          # JSON 解析后的响应体，或原始文本
    elapsed_ms: float  # 请求耗时（毫秒）
    url: str
    method: str
    error: str | None = None


class HTTPClient:
    """
    HTTP 请求执行工具。

    职责：执行 HTTP 请求并返回结构化响应。
    边界：只负责执行，不负责验证响应是否正确——验证交给 SchemaValidator。
    """

    # 安全风险操作，需要 HITL 审批
    DANGEROUS_METHODS = {"DELETE", "PUT", "PATCH"}

    def __init__(self):
        self.timeout = config.REQUEST_TIMEOUT
        self.max_retries = config.MAX_RETRIES_PER_CASE

    async def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        body: Any = None,
        auth: dict[str, Any] | None = None,
    ) -> HTTPResponse:
        """
        执行单次 HTTP 请求。

        Args:
            method: HTTP 方法（GET/POST/PUT/PATCH/DELETE）
            url: 完整的请求 URL
            headers: 额外的 Headers（不含认证头）
            params: URL 查询参数
            body: 请求体（dict/str），dict 自动序列化为 JSON
            auth: 认证配置 {"type": "bearer"|"api_key"|"basic", ...}

        Returns:
            HTTPResponse 结构化响应
        """
        headers = headers or {}
        headers = self._apply_auth(headers, auth)

        # 序列化请求体
        content: str | None = None
        if body is not None:
            if isinstance(body, dict):
                content = json.dumps(body, ensure_ascii=False)
                headers.setdefault("Content-Type", "application/json")
            else:
                content = str(body)

        start = time.perf_counter()
        error: str | None = None

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    params=params,
                    content=content,
                    follow_redirects=True,
                )

                # 解析响应体
                try:
                    resp_body = response.json()
                except (json.JSONDecodeError, ValueError):
                    resp_body = response.text

                # 截断过大的响应
                if isinstance(resp_body, str) and len(resp_body) > config.MAX_RESPONSE_SIZE:
                    resp_body = resp_body[:config.MAX_RESPONSE_SIZE] + "...[truncated]"

                elapsed = (time.perf_counter() - start) * 1000

                return HTTPResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=resp_body,
                    elapsed_ms=elapsed,
                    url=str(response.url),
                    method=method.upper(),
                )

        except httpx.TimeoutException:
            elapsed = (time.perf_counter() - start) * 1000
            error = f"请求超时 ({self.timeout}s)"
        except httpx.ConnectError as e:
            elapsed = (time.perf_counter() - start) * 1000
            error = f"连接失败: {e}"
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            error = f"请求异常: {type(e).__name__}: {e}"

        return HTTPResponse(
            status_code=0,
            headers={},
            body=None,
            elapsed_ms=elapsed,
            url=url,
            method=method.upper(),
            error=error,
        )

    @retry(
        stop=stop_after_attempt(config.MAX_RETRIES_PER_CASE),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> HTTPResponse:
        """带指数退避重试的请求（5xx 错误或网络错误时重试）"""
        resp = await self.request(method, url, **kwargs)
        if resp.error or (500 <= resp.status_code < 600):
            raise Exception(f"Retryable error: status={resp.status_code}, error={resp.error}")
        return resp

    def is_dangerous(self, method: str) -> bool:
        """检查是否为需要 HITL 审批的危险操作"""
        return method.upper() in self.DANGEROUS_METHODS

    def _apply_auth(
        self, headers: dict[str, str], auth: dict[str, Any] | None
    ) -> dict[str, str]:
        """应用认证配置到 Headers"""
        if not auth:
            return headers

        auth_type = auth.get("type", "").lower()
        headers = dict(headers)

        if auth_type == "bearer":
            token = auth.get("token", "")
            headers["Authorization"] = f"Bearer {token}"

        elif auth_type == "api_key":
            # API Key 可通过 Header 或 Query Param
            key = auth.get("key", "")
            key_name = auth.get("header_name", "X-API-Key")
            if auth.get("in") == "query":
                # Query param 方式需要调用方自己加在 params 里
                pass
            else:
                headers[key_name] = key

        elif auth_type == "basic":
            import base64
            username = auth.get("username", "")
            password = auth.get("password", "")
            creds = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {creds}"

        elif auth_type == "oauth2":
            # OAuth2 Client Credentials — 简化实现，token 已预先获取
            token = auth.get("access_token", "")
            headers["Authorization"] = f"Bearer {token}"

        return headers


# 工具定义 (OpenAI Function Calling 格式)
HTTP_CLIENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "http_request",
        "description": "执行单个 HTTP 请求。用于测试 API 端点，获取响应状态码、响应体和耗时。",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
                    "description": "HTTP 请求方法",
                },
                "url": {
                    "type": "string",
                    "description": "完整的请求 URL（含协议和路径）",
                },
                "headers": {
                    "type": "object",
                    "description": "请求 Headers（不含认证头，认证头通过 auth 参数处理）",
                },
                "params": {
                    "type": "object",
                    "description": "URL 查询参数 (query string)",
                },
                "body": {
                    "description": "请求体。JSON 对象或字符串",
                },
                "auth": {
                    "type": "object",
                    "description": "认证配置",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["bearer", "api_key", "basic", "oauth2"],
                        },
                        "token": {"type": "string", "description": "Bearer token / OAuth2 access token"},
                        "key": {"type": "string", "description": "API Key 值"},
                        "header_name": {"type": "string", "description": "API Key 所在的 Header 名"},
                        "username": {"type": "string", "description": "Basic Auth 用户名"},
                        "password": {"type": "string", "description": "Basic Auth 密码"},
                    },
                },
            },
            "required": ["method", "url"],
        },
    },
}
