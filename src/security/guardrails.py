"""
安全护栏系统 — OWASP ASI Top 10 对齐。

六层纵深防御：
1. 输入过滤      — Prompt Injection / SQL / XSS 模式检测
2. 指令隔离      — 用户输入与系统指令边界分离
3. 工具校验      — 工具调用前参数安全检查
4. 运行时隔离    — 沙箱执行、域名白名单、数据防泄露
5. 人工审批      — 危险操作 HITL 确认
6. 审计日志      — 全链路操作可追溯

设计原则（来自 OWASP ASI）：
"最关键的安全边界不在模型内部，而在组件交互的接口处"
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
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
        r"(?i)(\bOR\b.*\b=\b)",                # OR 1=1 (经典注入)
        r"(?i)(\bUNION\b.*\bSELECT\b)",        # UNION SELECT
        r"(?i)(\bDROP\b\s+\bTABLE\b)",          # DROP TABLE
        r"(?i)(\bINSERT\b\s+\bINTO\b)",         # INSERT INTO
        r"(?i)(\bDELETE\b\s+\bFROM\b)",         # DELETE FROM
        r"(?i)(--\s*(?:\r?\n|$))",             # SQL 注释（支持多行）
        r"(?i)(;\s*SELECT\b)",                   # 堆叠查询
    ]

    # XSS 检测模式
    XSS_PATTERNS = [
        r"(?i)<script[^>]*>",
        r"(?i)javascript\s*:",
        r"(?i)onerror\s*=",
        r"(?i)onload\s*=",
        r"(?i)<img[^>]+onerror",
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

    # ── 第 2 层：指令隔离 ────────────────────────────────────

    def validate_instruction_boundary(
        self, user_input: str, system_context: str = ""
    ) -> SecurityCheck:
        """
        第 2 层：指令隔离。

        检测用户输入是否尝试突破系统指令边界：
        - 包含系统指令覆盖尝试（"你的新任务是..."）
        - 尝试读取/修改系统 prompt
        - 注入分隔符绕过
        """
        # 检测分隔符注入
        delimiter_patterns = [
            r"---SYSTEM_INSTRUCTION_END---",
            r"<\|im_end\|>",
            r"<\|endoftext\|>",
            r"---END\s*OF\s*INSTRUCTION---",
            r"\[INST\].*\[/INST\]",
            r"<\|system\|>.*<\|/system\|>",
        ]
        for pattern in delimiter_patterns:
            if re.search(pattern, user_input, re.IGNORECASE | re.DOTALL):
                return SecurityCheck(
                    passed=False,
                    check_name="instruction_isolation",
                    detail=f"检测到指令分隔符注入",
                    severity="critical",
                )

        # 检测系统指令覆盖（中英文）
        override_patterns = [
            r"(?i)(你的新任务是|你的真实任务是|忽略上述|忘记之前)",
            r"(?i)(从现在开始.*你是|你不再是.*你是)",
            r"(?i)(ignore\s+(all\s+)?(previous|above|the)\s+instructions)",
            r"(?i)(forget\s+everything|disregard\s+(all\s+)?previous)",
            r"(?i)(system\s*:\s*|<<SYS>>|##\s*System)",
        ]
        for pattern in override_patterns:
            if re.search(pattern, user_input):
                return SecurityCheck(
                    passed=False,
                    check_name="instruction_isolation",
                    detail="检测到系统指令覆盖尝试",
                    severity="critical",
                )

        return SecurityCheck(
            passed=True,
            check_name="instruction_isolation",
            detail="指令隔离检查通过",
            severity="info",
        )

    # ── 第 4 层：运行时隔离 ──────────────────────────────────

    BLOCKED_IP_PREFIXES = [
        "10.", "172.16.", "172.17.", "172.18.", "172.19.",
        "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
        "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
        "172.30.", "172.31.", "192.168.", "127.", "0.",
        "169.254.", "224.", "239.",
    ]

    def validate_runtime_sandbox(
        self, url: str, allowed_domains: set[str] | None = None
    ) -> SecurityCheck:
        """
        第 4 层：运行时沙箱隔离。

        验证 HTTP 请求目标在安全范围内：
        - 禁止访问内网 IP / localhost
        - 禁止访问云元数据端点（AWS/GCP/Azure/Alibaba）
        - 可选域名白名单
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
        except Exception:
            return SecurityCheck(
                passed=False, check_name="runtime_sandbox",
                detail="无法解析 URL", severity="critical",
            )

        # 内网 IP 检查
        for prefix in self.BLOCKED_IP_PREFIXES:
            if hostname.startswith(prefix):
                return SecurityCheck(
                    passed=False, check_name="runtime_sandbox",
                    detail=f"禁止访问内网地址: {hostname}", severity="critical",
                )

        # localhost
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return SecurityCheck(
                passed=False, check_name="runtime_sandbox",
                detail=f"禁止访问 localhost: {hostname}", severity="critical",
            )

        # 云元数据端点
        cloud_metadata = {
            "169.254.169.254", "metadata.google.internal", "100.100.100.200",
        }
        if hostname in cloud_metadata:
            return SecurityCheck(
                passed=False, check_name="runtime_sandbox",
                detail=f"禁止访问云元数据: {hostname}", severity="critical",
            )

        # 域名白名单
        if allowed_domains is not None and hostname not in allowed_domains:
            return SecurityCheck(
                passed=False, check_name="runtime_sandbox",
                detail=f"域名不在白名单: {hostname}", severity="warning",
            )

        return SecurityCheck(
            passed=True, check_name="runtime_sandbox",
            detail=f"沙箱检查通过: {hostname}", severity="info",
        )


# ── 第 6 层：审计日志 ──────────────────────────────────────

@dataclass
class AuditEntry:
    """单条审计日志"""
    timestamp: str
    event_type: str
    actor: str
    action: str
    target: str
    detail: dict[str, Any] = field(default_factory=dict)
    result: str = "success"
    severity: str = "info"


class AuditLogger:
    """
    第 6 层：审计日志。

    记录所有敏感操作的全链路轨迹，JSONL 格式写入 data/audit.jsonl。
    """

    def __init__(self, log_dir: str = "./data"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._entries: list[AuditEntry] = []
        self._log_file = self.log_dir / "audit.jsonl"

    def log(
        self, event_type: str, actor: str, action: str,
        target: str = "", detail: dict | None = None,
        result: str = "success", severity: str = "info",
    ):
        """记录审计日志"""
        entry = AuditEntry(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            event_type=event_type, actor=actor, action=action,
            target=target, detail=detail or {},
            result=result, severity=severity,
        )
        self._entries.append(entry)
        # 防止内存泄漏：保留最近 10000 条
        if len(self._entries) > 10000:
            self._entries = self._entries[-5000:]
        self._write_to_file(entry)

        if severity in ("critical", "high"):
            import sys
            print(
                f"[AUDIT] [{severity.upper()}] {event_type}: {action} → {target} ({result})",
                file=sys.stderr,
            )

    def log_tool_call(self, tool_name: str, arguments: dict, result: str = "success"):
        """记录工具调用"""
        self.log(
            event_type="tool_call", actor="agent", action=tool_name,
            target=arguments.get("url", arguments.get("path", "")),
            detail={k: str(v)[:200] for k, v in arguments.items()},
            result=result,
        )

    def log_security_alert(self, check_name: str, detail: str, severity: str = "warning"):
        """记录安全告警"""
        self.log(
            event_type="security_alert", actor="guardrails", action=check_name,
            detail={"message": detail}, result="blocked", severity=severity,
        )

    def log_auth_attempt(self, auth_type: str, success: bool, detail: str = ""):
        """记录认证尝试"""
        self.log(
            event_type="auth_attempt", actor="agent", action=f"auth_{auth_type}",
            detail={"message": detail},
            result="success" if success else "blocked",
            severity="info" if success else "warning",
        )

    def get_recent_entries(self, limit: int = 50) -> list[dict]:
        """获取最近的审计日志"""
        return [
            {
                "timestamp": e.timestamp, "event_type": e.event_type,
                "actor": e.actor, "action": e.action,
                "target": e.target, "result": e.result, "severity": e.severity,
            }
            for e in self._entries[-limit:]
        ]

    def _write_to_file(self, entry: AuditEntry):
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": entry.timestamp, "event_type": entry.event_type,
                    "actor": entry.actor, "action": entry.action,
                    "target": entry.target, "detail": entry.detail,
                    "result": entry.result, "severity": entry.severity,
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass


# 全局实例
guardrails = Guardrails()
audit_logger = AuditLogger()


def check_dangerous_operation(method: str, path: str) -> bool:
    """检查是否为需要 HITL 审批的危险操作"""
    dangerous_methods = {"DELETE", "PUT", "PATCH"}
    return method.upper() in dangerous_methods
