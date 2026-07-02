"""
LLM-as-Judge for semantic validation of test results.
Evaluates agent output across 5 dimensions:
- accuracy: did it find real bugs?
- completeness: did it cover all endpoints?
- false_positive_rate: how many false alarms?
- report_quality: is the report clear and actionable?
- efficiency: was the test execution reasonable?
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.llm import llm

JUDGE_SYSTEM_PROMPT = """你是一个 API 测试质量评估专家。评估测试 Agent 的输出质量。

## 评分维度（每项 0.0 - 1.0）
1. **accuracy** (准确性): 是否发现了真正的 Bug？真实 Bug 发现率
2. **completeness** (完整性): 是否覆盖了所有端点？端点覆盖率
3. **false_positive_rate** (误报率): 假阳性占比（越低越好，1.0 = 无误报）
4. **report_quality** (报告质量): 报告是否清晰、结构化、可操作
5. **efficiency** (效率): 用例数量是否合理、执行时间是否可接受

## 输出格式（严格 JSON）
{
  "scores": {
    "accuracy": 0.0,
    "completeness": 0.0,
    "false_positive_rate": 0.0,
    "report_quality": 0.0,
    "efficiency": 0.0
  },
  "overall": 0.0,
  "strengths": ["优点1"],
  "weaknesses": ["缺点1"],
  "bugs_found_summary": "发现的 Bug 总结",
  "recommendations": ["改进建议"]
}"""


@dataclass
class EvalResult:
    """Result of a single evaluation run."""
    scores: dict[str, float]
    overall: float
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    bugs_found_summary: str = ""
    recommendations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.overall >= 0.6


async def evaluate_test_results(
    test_results: list[dict[str, Any]],
    total_endpoints: int,
    total_cases: int,
    pass_rate: float,
    execution_time_ms: float,
    bugs_detected: list[str] | None = None,
) -> EvalResult:
    """
    Use LLM-as-Judge to evaluate test agent output.

    Returns EvalResult with 5-dimension scores.
    """
    user_msg = f"""请评估以下 API 自动化测试结果：

## 测试执行摘要
- 总端点: {total_endpoints}
- 总用例: {total_cases}
- 通过率: {pass_rate:.1f}%
- 执行时间: {execution_time_ms:.0f}ms

## 检测到的 Bug
{chr(10).join(f"- {b}" for b in (bugs_detected or [])) if bugs_detected else "无"}

## 测试结果（前30条）
{json.dumps(test_results[:30], ensure_ascii=False, indent=2)[:4000]}
"""

    try:
        response = llm.chat_with_tools(
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_message=user_msg,
            temperature=0.2,
            max_tokens=2048,
        )
        content = llm.extract_content(response)
        data = _extract_json(content)

        return EvalResult(
            scores=data.get("scores", {}),
            overall=data.get("overall", 0.0),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            bugs_found_summary=data.get("bugs_found_summary", ""),
            recommendations=data.get("recommendations", []),
        )
    except Exception:
        return EvalResult(
            scores={},
            overall=0.0,
            weaknesses=["Evaluation failed — LLM returned invalid response"],
        )


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())
