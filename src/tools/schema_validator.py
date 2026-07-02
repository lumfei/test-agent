"""
JSON Schema 验证器 — 验证 API 响应是否符合预期 Schema。
支持结构验证（字段存在性、类型、必填）和语义验证（LLM-as-Judge）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import jsonschema


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    check_type: str            # "schema" | "status_code" | "header" | "semantic"
    detail: str                # 人类可读的验证结果描述
    expected: Any = None       # 期望值
    actual: Any = None         # 实际值


@dataclass
class BatchValidationResult:
    """批量验证结果"""
    all_passed: bool
    results: list[ValidationResult] = field(default_factory=list)
    summary: str = ""

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 1.0
        passed = sum(1 for r in self.results if r.passed)
        return passed / len(self.results)


class SchemaValidator:
    """
    JSON Schema 验证工具。

    职责：验证 API 响应的结构正确性。
    边界：只验证结构，不判断业务逻辑正确性——业务逻辑由 LLM 评估。
    """

    def validate_status_code(
        self, actual_status: int, expected_status: int | list[int]
    ) -> ValidationResult:
        """验证 HTTP 状态码是否符合预期"""
        expected_list = expected_status if isinstance(expected_status, list) else [expected_status]
        passed = actual_status in expected_list

        return ValidationResult(
            passed=passed,
            check_type="status_code",
            detail=f"期望状态码 {expected_list}，实际 {actual_status}" + (" ✓" if passed else " ✗"),
            expected=expected_list,
            actual=actual_status,
        )

    def validate_json_schema(
        self, response_body: Any, expected_schema: dict[str, Any]
    ) -> ValidationResult:
        """
        使用 JSON Schema 验证响应体结构。

        Args:
            response_body: API 响应体（dict/list/str）
            expected_schema: JSON Schema 定义

        Returns:
            ValidationResult
        """
        if not isinstance(response_body, (dict, list)):
            return ValidationResult(
                passed=False,
                check_type="schema",
                detail=f"响应体不是 JSON 对象/数组，无法进行 Schema 验证。类型: {type(response_body).__name__}",
                expected=expected_schema,
                actual=str(response_body)[:200],
            )

        try:
            validator = jsonschema.Draft202012Validator(expected_schema)
            errors = list(validator.iter_errors(response_body))

            if not errors:
                return ValidationResult(
                    passed=True,
                    check_type="schema",
                    detail="JSON Schema 验证通过 ✓",
                    expected=expected_schema,
                    actual="(验证通过)",
                )
            else:
                error_msgs = []
                for err in errors[:10]:  # 最多展示 10 条错误
                    path = " → ".join(str(p) for p in err.absolute_path) if err.absolute_path else "(root)"
                    error_msgs.append(f"{path}: {err.message}")

                return ValidationResult(
                    passed=False,
                    check_type="schema",
                    detail=f"Schema 验证失败 ({len(errors)} 个错误):\n" + "\n".join(error_msgs),
                    expected=expected_schema,
                    actual=response_body if isinstance(response_body, str) else json.dumps(response_body, ensure_ascii=False)[:500],
                )

        except jsonschema.SchemaError as e:
            return ValidationResult(
                passed=False,
                check_type="schema",
                detail=f"期望的 JSON Schema 自身无效: {e.message}",
                expected=expected_schema,
                actual=None,
            )

    def validate_headers(
        self, headers: dict[str, str], expected_headers: dict[str, str]
    ) -> ValidationResult:
        """验证响应 Headers 是否包含期望的字段"""
        missing = []
        mismatch = []

        for key, expected_value in expected_headers.items():
            actual_value = headers.get(key)
            if actual_value is None:
                missing.append(key)
            elif expected_value.lower() != actual_value.lower():
                mismatch.append(f"{key}: 期望={expected_value}, 实际={actual_value}")

        issues = []
        if missing:
            issues.append(f"缺少 Headers: {missing}")
        if mismatch:
            issues.append(f"值不匹配: {mismatch}")

        passed = not missing and not mismatch
        return ValidationResult(
            passed=passed,
            check_type="header",
            detail="Headers 验证通过 ✓" if passed else "; ".join(issues),
            expected=expected_headers,
            actual={k: headers.get(k) for k in expected_headers},
        )

    def validate_response_time(
        self, elapsed_ms: float, max_ms: float = 3000
    ) -> ValidationResult:
        """验证响应时间是否在阈值内"""
        passed = elapsed_ms <= max_ms
        return ValidationResult(
            passed=passed,
            check_type="response_time",
            detail=f"响应时间 {elapsed_ms:.0f}ms（阈值 {max_ms:.0f}ms）{'✓' if passed else '✗ 超时'}",
            expected=f"≤{max_ms}ms",
            actual=f"{elapsed_ms:.0f}ms",
        )


# 工具定义
SCHEMA_VALIDATOR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "validate_response",
        "description": "验证 API 响应的正确性：状态码、JSON Schema 结构、Headers、响应时间。",
        "parameters": {
            "type": "object",
            "properties": {
                "response_body": {
                    "description": "API 返回的响应体（JSON 对象或文本）",
                },
                "expected_status": {
                    "description": "期望的 HTTP 状态码，如 200、201 或 [200, 201]",
                },
                "expected_schema": {
                    "type": "object",
                    "description": "期望的 JSON Schema 定义（JSON Schema Draft 2020-12 格式）",
                },
                "expected_headers": {
                    "type": "object",
                    "description": "期望的响应 Headers 键值对",
                },
                "actual_status": {
                    "type": "integer",
                    "description": "实际收到的 HTTP 状态码",
                },
                "actual_headers": {
                    "type": "object",
                    "description": "实际收到的响应 Headers",
                },
                "elapsed_ms": {
                    "type": "number",
                    "description": "请求实际耗时（毫秒）",
                },
            },
            "required": [],
        },
    },
}
