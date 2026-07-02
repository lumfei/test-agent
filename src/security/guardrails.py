"""
安全护栏系统 — OWASP ASI Top 10 对齐。

六层纵深防御：
1. 输入过滤
2. 指令隔离
3. 工具校验
4. 运行时隔离
5. 人工审批
6. 审计日志
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SecurityCheck:
    """安全检查结果"""
    passed: bool
    check_name: str
    detail: str
    severity: str = "info"  # info / warning / critical


class Guardrails:
    """
    Agent 安全护栏。

    核心思想（来自 OWASP ASI）：
    "最关键的的安全边界不在模型内部，而在组件交互的接口处"
    """

    # SQL 注入检测模式
    SQL_INJECTION_PATTERNS = [
        r"(?i)(\bOR\b.*\b=\b.*\b=\b)",       # OR 1=1
        r"(?i)(\bUNION\b.*\bSELECT\b)",        # UNION SELECT
        r"(?i)(\bDROP\b\s+\bTABLE\b)",          # DROP TABLE
        r"(?i)(\bINSERT\b\s+\bINTO\b)",         # INSERT INTO
        r"(?i)(\bDELETE\b\s+\bFROM\b)",         # DELETE FROM
        r"(?i)(--\s*$)",                        # SQL 注释
        r"(?i)(;\s*SELECT\b)",                   # 堆叠查询
    ]

    # XSS 检测模式
    XSS_PATTERNS = [
        r"<script[^>]*>",
        r"javascript\s*:",
        r"onerror\s*=",
        r"onload\s*=",
        r"<img[^>]+onerror",
    ]

    # Prompt Injection 检测模式
    PROMPT_INJECTION_PATTERNS = [
        r"(?i)(ignore\s+(all\s+)?(previous|above|the)\s+instructions)",
        r"(?i)(system\s*prompt\s*(:|=|is))",
        r"(?i)(you\s+are\s+now\s+(a|an|the))",
        r"(?i)(pretend\s+you\s+are)",
        r"(?i)(forget\s+everything)",
    ]

    def validate_input(self, text: str) -> list[SecurityCheck]:
        """
        第 1 层：输入过滤。

        检测用户输入中的 Prompt Injection、SQL 注入、XSS 模式。
        """
        checks: list[SecurityCheck] = []

        # Prompt Injection
        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text):
                checks.append(SecurityCheck(
                    passed=False,
                    check_name="prompt_injection",
                    detail=f"检测到可能的 Prompt Injection 模式: {pattern}",
                    severity="critical",
                ))
                break

        # SQL 注入
        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, text):
                checks.append(SecurityCheck(
                    passed=False,
                    check_name="sql_injection",
                    detail=f"检测到 SQL 注入模式",
                    severity="warning",
                ))
                break

        # XSS
        for pattern in self.XSS_PATTERNS:
            if re.search(pattern, text):
                checks.append(SecurityCheck(
                    passed=False,
                    check_name="xss",
                    detail=f"检测到 XSS 模式",
                    severity="warning",
                ))
                break

        if not checks:
            checks.append(SecurityCheck(
                passed=True,
                check_name="input_validation",
                detail="输入验证通过",
                severity="info",
            ))

        return checks

    def validate_tool_call(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> SecurityCheck:
        """
        第 3 层：工具调用校验。

        在所有工具执行前验证参数合法性。
        """
        # HTTP 请求工具检查
        if tool_name == "http_request":
            url = arguments.get("url", "")
            method = arguments.get("method", "GET")

            # 检查内部 IP 访问
            internal_ips = ["127.0.0.1", "0.0.0.0", "::1", "localhost"]
            for ip in internal_ips:
                if ip in url:
                    return SecurityCheck(
                        passed=False,
                        check_name="internal_ip_block",
                        detail=f"禁止访问内部地址: {ip}",
                        severity="critical",
                    )

            # 检查危险方法
            if method.upper() in ("DELETE",):
                return SecurityCheck(
                    passed=False,
                    check_name="dangerous_method",
                    detail=f"HTTP {method} 操作需要人工确认",
                    severity="critical",
                )

        return SecurityCheck(
            passed=True,
            check_name="tool_validation",
            detail=f"工具 {tool_name} 验证通过",
            severity="info",
        )

    def validate_response(self, response_body: str) -> SecurityCheck:
        """验证工具响应，防止数据泄露"""
        # 检测敏感信息模式（API Key、Token、密码等）
        sensitive_patterns = [
            r'sk-[a-zA-Z0-9]{32,}',        # OpenAI/DeepSeek API Key
            r'Bearer\s+[a-zA-Z0-9\-_\.]{20,}',  # Bearer Token
            r'(?i)(password["\']?\s*[:=]\s*["\'])',  # 密码
            r'(?i)(secret["\']?\s*[:=]\s*["\'])',    # Secret
        ]

        for pattern in sensitive_patterns:
            if re.search(pattern, response_body):
                return SecurityCheck(
                    passed=False,
                    check_name="sensitive_data",
                    detail="响应中包含可能的敏感信息",
                    severity="warning",
                )

        return SecurityCheck(
            passed=True,
            check_name="response_validation",
            detail="响应验证通过",
            severity="info",
        )

    def check_auth_bypass(self, url: str, auth_configured: bool) -> SecurityCheck:
        """检查是否尝试绕过认证"""
        if not auth_configured:
            return SecurityCheck(
                passed=True,
                check_name="auth_check",
                detail="无需认证检查",
                severity="info",
            )

        # 检查 URL 是否尝试访问认证端点
        auth_bypass_paths = ["/admin", "/internal", "/debug", "/.env"]
        for path in auth_bypass_paths:
            if path in url.lower():
                return SecurityCheck(
                    passed=False,
                    check_name="auth_bypass",
                    detail=f"检测到尝试访问受限路径: {path}",
                    severity="critical",
                )

        return SecurityCheck(
            passed=True,
            check_name="auth_check",
            detail="认证检查通过",
            severity="info",
        )


# 全局实例
guardrails = Guardrails()


def check_dangerous_operation(method: str, path: str) -> bool:
    """检查是否为需要 HITL 审批的危险操作"""
    dangerous_methods = {"DELETE", "PUT", "PATCH"}
    return method.upper() in dangerous_methods
