"""
Web 文档抓取器 — 从网页读取 API 文档。
支持直接获取 OpenAPI Spec、抓取 Swagger/Redoc 页面、提取 HTML 文档文本。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx
import yaml
from bs4 import BeautifulSoup


@dataclass
class FetchedDoc:
    """抓取的文档内容"""
    source_url: str
    source_type: str  # openapi_json | openapi_yaml | swagger_page | html_doc | unknown
    raw_content: str | None = None
    openapi_spec: dict[str, Any] | None = None
    text_content: str | None = None
    error: str | None = None


class WebDocFetcher:
    """
    Web 文档抓取工具。

    职责：从网页获取 API 文档/OpenAPI Spec。
    边界：只获取和解析文档，不执行请求——执行交给 HTTPClient。
    """

    OPENAPI_JSON_EXTENSIONS = (".json",)
    OPENAPI_YAML_EXTENSIONS = (".yaml", ".yml")
    SWAGGER_PATHS = ("/docs", "/swagger", "/api-docs", "/swagger-ui.html", "/api/docs")
    OPENAPI_COMMON_PATHS = (
        "/openapi.json", "/api/openapi.json", "/v3/api-docs",
        "/swagger/v1/swagger.json", "/api/v1/openapi.json",
        "/openapi.yaml", "/swagger.yaml",
    )

    async def fetch(self, url: str, timeout: int = 30) -> FetchedDoc:
        """
        智能抓取 API 文档。

        Args:
            url: 文档 URL 或基础 URL
            timeout: 超时秒数

        Returns:
            FetchedDoc 结构化文档
        """
        url = url.strip()

        # 策略 1：URL 看起来像直接的 OpenAPI Spec
        if url.endswith(".json"):
            return await self._fetch_openapi_json(url, timeout)
        if url.endswith((".yaml", ".yml")):
            return await self._fetch_openapi_yaml(url, timeout)

        # 策略 2：先尝试常见 OpenAPI 路径
        if not url.endswith(".html") and "/" in url:
            for common_path in self.SWAGGER_PATHS:
                if common_path in url:
                    result = await self._fetch_page(url, timeout)
                    if result.openapi_spec:
                        return result
                    return await self._try_common_spec_paths(url, timeout)

        # 策略 3：尝试作为 Swagger UI 页面处理
        result = await self._fetch_page(url, timeout)
        if result.openapi_spec:
            return result

        # 策略 4：作为纯 HTML 文档处理，提取文本
        return await self._extract_html_text(url, timeout)

    async def fetch_openapi_spec(self, url: str, timeout: int = 30) -> FetchedDoc:
        """
        直接获取 OpenAPI Spec（已知 URL 是 spec 文件）。
        """
        if url.endswith((".yaml", ".yml")):
            return await self._fetch_openapi_yaml(url, timeout)
        return await self._fetch_openapi_json(url, timeout)

    async def _fetch_openapi_json(self, url: str, timeout: int) -> FetchedDoc:
        """获取 JSON 格式的 OpenAPI Spec"""
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                spec = resp.json()

                # 验证是 OpenAPI Spec
                if self._is_openapi_spec(spec):
                    return FetchedDoc(
                        source_url=url,
                        source_type="openapi_json",
                        openapi_spec=spec,
                        raw_content=json.dumps(spec, ensure_ascii=False),
                    )
                else:
                    return FetchedDoc(
                        source_url=url,
                        source_type="unknown",
                        error="文件是有效 JSON 但不符合 OpenAPI 规范",
                    )
        except Exception as e:
            return FetchedDoc(source_url=url, source_type="unknown", error=str(e))

    async def _fetch_openapi_yaml(self, url: str, timeout: int) -> FetchedDoc:
        """获取 YAML 格式的 OpenAPI Spec"""
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                spec = yaml.safe_load(resp.text)

                if self._is_openapi_spec(spec):
                    return FetchedDoc(
                        source_url=url,
                        source_type="openapi_yaml",
                        openapi_spec=spec,
                        raw_content=resp.text,
                    )
                else:
                    return FetchedDoc(
                        source_url=url,
                        source_type="unknown",
                        error="文件是有效 YAML 但不符合 OpenAPI 规范",
                    )
        except Exception as e:
            return FetchedDoc(source_url=url, source_type="unknown", error=str(e))

    async def _fetch_page(self, url: str, timeout: int) -> FetchedDoc:
        """抓取页面，自动检测并提取 OpenAPI Spec"""
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
                soup = BeautifulSoup(html, "lxml")

                # 方法 1：查找 Swagger UI 的 spec 链接
                # Swagger UI 通常通过 JS 加载 spec URL，检查常见模式
                spec_url = self._extract_spec_url_from_page(soup, resp.text, url)

                if spec_url:
                    # 构建完整 URL
                    if spec_url.startswith("/"):
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        spec_url = f"{parsed.scheme}://{parsed.netloc}{spec_url}"
                    elif not spec_url.startswith("http"):
                        spec_url = url.rstrip("/") + "/" + spec_url.lstrip("/")

                    if spec_url.endswith((".yaml", ".yml")):
                        return await self._fetch_openapi_yaml(spec_url, timeout)
                    else:
                        return await self._fetch_openapi_json(spec_url, timeout)

                # 方法 2：检查页面本身是否为 JSON OpenAPI Spec
                try:
                    spec = resp.json()
                    if self._is_openapi_spec(spec):
                        return FetchedDoc(
                            source_url=url,
                            source_type="openapi_json",
                            openapi_spec=spec,
                            raw_content=resp.text,
                        )
                except (json.JSONDecodeError, ValueError):
                    pass

                return FetchedDoc(
                    source_url=url,
                    source_type="html_doc",
                    text_content=soup.get_text(separator="\n", strip=True)[:50000],
                )

        except Exception as e:
            return FetchedDoc(source_url=url, source_type="unknown", error=str(e))

    async def _extract_html_text(self, url: str, timeout: int) -> FetchedDoc:
        """提取 HTML 页面文本内容"""
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")

                # 移除 script/style 标签
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()

                text = soup.get_text(separator="\n", strip=True)

                # 尝试在文本中找 API 端点描述模式
                return FetchedDoc(
                    source_url=url,
                    source_type="html_doc",
                    text_content=text[:50000],
                )

        except Exception as e:
            return FetchedDoc(source_url=url, source_type="unknown", error=str(e))

    async def _try_common_spec_paths(self, base_url: str, timeout: int) -> FetchedDoc:
        """尝试常见的 OpenAPI Spec 路径"""
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        for path in self.OPENAPI_COMMON_PATHS:
            url = base + path
            try:
                result = await self._fetch_openapi_json(url, timeout)
                if result.openapi_spec and not result.error:
                    return result
            except Exception:
                continue

        # 回退到页面抓取
        return await self._extract_html_text(base_url, timeout)

    def _extract_spec_url_from_page(
        self, soup: BeautifulSoup, html: str, page_url: str
    ) -> str | None:
        """从 Swagger/Redoc 页面提取 OpenAPI Spec URL"""
        # Swagger UI 常用模式
        import re

        patterns = [
            r'url:\s*["\']([^"\']+\.(?:json|yaml|yml))["\']',
            r'spec-url=["\']([^"\']+)["\']',
            r'api-docs["\']?\s*:\s*["\']([^"\']+)["\']',
            r'href=["\']([^"\']*openapi[^"\']*\.json)["\']',
            r'href=["\']([^"\']*swagger[^"\']*\.json)["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _is_openapi_spec(self, data: dict[str, Any]) -> bool:
        """验证是否为有效的 OpenAPI 规范文档"""
        if not isinstance(data, dict):
            return False
        # OpenAPI 3.x
        if data.get("openapi") and isinstance(data.get("openapi"), str):
            return True
        # Swagger 2.x
        if data.get("swagger") and isinstance(data.get("swagger"), str):
            return True

        return False


# 工具定义
WEB_FETCHER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_api_docs",
        "description": (
            "从网页获取 API 文档。支持：直接 OpenAPI JSON/YAML URL、"
            "Swagger UI / Redocly 文档页面、纯 HTML 文档。"
            "自动检测并解析文档格式。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "API 文档的 URL。可以是 OpenAPI Spec 文件的直接链接、Swagger UI 页面的 URL，或 API 基础 URL",
                },
            },
            "required": ["url"],
        },
    },
}
