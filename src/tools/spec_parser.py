"""
OpenAPI Spec 解析器 — 解析 OpenAPI 3.x / Swagger 2.x 规范。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EndpointInfo:
    """单个 API 端点的完整信息"""
    path: str
    method: str
    summary: str = ""
    description: str = ""
    operation_id: str = ""
    tags: list[str] = field(default_factory=list)
    parameters: list[dict[str, Any]] = field(default_factory=list)
    request_body: dict[str, Any] | None = None
    request_body_schema: dict[str, Any] | None = None
    responses: dict[str, Any] = field(default_factory=dict)
    success_status: int = 200
    success_response_schema: dict[str, Any] | None = None
    security: list[dict[str, list[str]]] | None = None


@dataclass
class ParsedSpec:
    """解析后的 API 规范"""
    title: str
    version: str
    description: str = ""
    base_url: str = ""
    endpoints: list[EndpointInfo] = field(default_factory=list)
    servers: list[dict[str, str]] = field(default_factory=list)
    security_schemes: dict[str, Any] = field(default_factory=dict)
    raw_spec: dict[str, Any] | None = None

    @property
    def endpoint_count(self) -> int:
        return len(self.endpoints)

    @property
    def method_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for ep in self.endpoints:
            counts[ep.method] = counts.get(ep.method, 0) + 1
        return dict(sorted(counts.items()))

    @property
    def auth_required(self) -> bool:
        return any(ep.security for ep in self.endpoints)


class SpecParser:
    """
    OpenAPI Spec 解析工具。

    职责：解析 OpenAPI/Swagger 规范，提取结构化端点信息。
    边界：只解析，不生成测试用例——生成交给 TestDataGenerator。
    支持：OpenAPI 3.0 / 3.1 / Swagger 2.0
    """

    def parse(self, spec: dict[str, Any]) -> ParsedSpec:
        """解析 OpenAPI Spec 字典"""
        # 存为实例变量供 _resolve_ref 使用
        self._raw_spec = spec

        is_openapi_v3 = "openapi" in spec
        is_swagger_v2 = "swagger" in spec

        if not is_openapi_v3 and not is_swagger_v2:
            raise ValueError("不支持的规范格式：缺少 'openapi' 或 'swagger' 字段")

        info = spec.get("info", {})
        title = info.get("title", "Unknown API")
        version = info.get("version", "0.0.0")
        description = info.get("description", "")

        servers: list[dict[str, str]] = []
        base_url = ""
        if is_openapi_v3:
            servers = spec.get("servers", [])
            base_url = servers[0].get("url", "") if servers else ""
        elif is_swagger_v2:
            host = spec.get("host", "localhost")
            base_path = spec.get("basePath", "/")
            schemes = spec.get("schemes", ["https"])
            base_url = f"{schemes[0]}://{host}{base_path}".rstrip("/")

        security_schemes = {}
        if is_openapi_v3:
            security_schemes = spec.get("components", {}).get("securitySchemes", {})
        elif is_swagger_v2:
            security_schemes = spec.get("securityDefinitions", {})

        endpoints: list[EndpointInfo] = []
        paths = spec.get("paths", {})

        for path, path_item in paths.items():
            if not path_item:
                continue

            http_methods = ("get", "post", "put", "patch", "delete", "options", "head")
            for method in http_methods:
                operation = path_item.get(method)
                if not operation:
                    continue

                endpoint = self._parse_endpoint(path, method.upper(), operation, is_openapi_v3)
                endpoints.append(endpoint)

        return ParsedSpec(
            title=title,
            version=version,
            description=description,
            base_url=base_url,
            endpoints=endpoints,
            servers=servers,
            security_schemes=security_schemes,
            raw_spec=spec,
        )

    def _resolve_ref(self, ref_str: str) -> dict[str, Any]:
        """
        解析 $ref 引用（如 #/components/schemas/ChatRequest）。
        只支持同文档内引用，不支持外部文件。
        """
        if not ref_str.startswith("#/"):
            return {}

        # 按 JSON Pointer 路径逐级访问
        parts = ref_str[2:].split("/")
        current: Any = self._raw_spec
        for part in parts:
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return {}
            if current is None:
                return {}

        return current if isinstance(current, dict) else {}

    def _resolve_schema(self, schema_obj: Any) -> dict[str, Any]:
        """
        解析 schema：如果是 $ref 则解引用，否则直接返回。
        解引用后递归处理嵌套的 $ref 和 allOf。
        """
        if not isinstance(schema_obj, dict):
            return {}
        if "$ref" in schema_obj:
            resolved = self._resolve_ref(schema_obj["$ref"])
            return self._resolve_schema(resolved) if resolved else {}
        if "allOf" in schema_obj:
            merged: dict[str, Any] = {"type": "object", "properties": {}}
            for sub in schema_obj["allOf"]:
                sub_resolved = self._resolve_schema(sub)
                if sub_resolved.get("properties"):
                    merged.setdefault("properties", {}).update(sub_resolved["properties"])
                if sub_resolved.get("required"):
                    merged.setdefault("required", []).extend(sub_resolved["required"])
            if not merged["properties"]:
                del merged["properties"]
            if not merged.get("required"):
                merged.pop("required", None)
            return merged
        return schema_obj

    def parse_from_json(self, content: str) -> ParsedSpec:
        """从 JSON 字符串解析"""
        spec = json.loads(content)
        return self.parse(spec)

    def parse_from_yaml(self, content: str) -> ParsedSpec:
        """从 YAML 字符串解析"""
        import yaml as _yaml
        spec = _yaml.safe_load(content)
        return self.parse(spec)

    def _parse_endpoint(
        self, path: str, method: str, operation: dict[str, Any], is_v3: bool
    ) -> EndpointInfo:
        """解析单个端点"""
        parameters = operation.get("parameters", [])

        request_body = operation.get("requestBody")
        request_body_schema = None
        if request_body and is_v3:
            content = request_body.get("content", {})
            json_content = content.get("application/json", {})
            raw_schema = json_content.get("schema")
            request_body_schema = self._resolve_schema(raw_schema) if raw_schema else None
        elif request_body and not is_v3:
            for param in operation.get("parameters", []):
                if param.get("in") == "body":
                    raw_schema = param.get("schema")
                    request_body_schema = self._resolve_schema(raw_schema) if raw_schema else None
                    break

        responses = operation.get("responses", {})
        success_status = 200
        success_schema = None
        for status_code, resp in responses.items():
            try:
                code = int(status_code)
                if 200 <= code < 300:
                    success_status = code
                    if is_v3:
                        c = resp.get("content", {})
                        jc = c.get("application/json", {})
                        raw_schema = jc.get("schema")
                        success_schema = self._resolve_schema(raw_schema) if raw_schema else None
                    else:
                        raw_schema = resp.get("schema")
                        success_schema = self._resolve_schema(raw_schema) if raw_schema else None
                    break
            except ValueError:
                continue

        security = operation.get("security")

        return EndpointInfo(
            path=path,
            method=method,
            summary=operation.get("summary", ""),
            description=operation.get("description", ""),
            operation_id=operation.get("operationId", f"{method}_{path}"),
            tags=operation.get("tags", []),
            parameters=parameters,
            request_body=request_body,
            request_body_schema=request_body_schema,
            responses=responses,
            success_status=success_status,
            success_response_schema=success_schema,
            security=security,
        )

    def to_summary_text(self, parsed: ParsedSpec, base_url_override: str = "") -> str:
        """生成可读的 API 摘要（用于 LLM Context）"""
        base_url = base_url_override or parsed.base_url
        lines = [
            f"# API: {parsed.title} v{parsed.version}",
            f"Base URL: {base_url}",
            f"描述: {parsed.description}" if parsed.description else "",
            f"端点总数: {parsed.endpoint_count}",
            f"方法分布: {parsed.method_summary}",
            f"需要认证: {'是' if parsed.auth_required else '否'}",
            "",
            "## 端点列表:",
        ]

        for ep in parsed.endpoints:
            auth_mark = "[auth]" if ep.security else "[open]"
            params_str = ", ".join(
                f"{p.get('name')}:{p.get('schema', {}).get('type', 'any')}"
                for p in ep.parameters
            ) if ep.parameters else "无参数"
            body_mark = " [含请求体]" if ep.request_body_schema else ""
            lines.append(
                f"- {auth_mark} **{ep.method}** {ep.path} | "
                f"参数: {params_str}{body_mark} | "
                f"期望: {ep.success_status}"
            )
            if ep.summary:
                lines.append(f"  _{ep.summary}_")

        return "\n".join(lines)


# 工具定义
SPEC_PARSER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "parse_api_spec",
        "description": "解析 OpenAPI 3.x / Swagger 2.0 规范，提取所有 API 端点的结构化信息。",
        "parameters": {
            "type": "object",
            "properties": {
                "spec_json": {
                    "type": "string",
                    "description": "OpenAPI Spec 的 JSON 字符串",
                },
            },
            "required": ["spec_json"],
        },
    },
}
