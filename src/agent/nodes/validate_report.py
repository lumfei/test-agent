"""
节点 5：Validate & Report — 验证测试结果并生成报告。
含 LLM 语义验证（LLM-as-Judge）和报告生成。
"""
from __future__ import annotations

import json
import time

from src.agent.state import AgentState
from src.llm import llm
from src.tools import report_gen
from src.prompts import prompt_registry
from src.observability import cost_tracker
from src.tools.report_gen import TestCaseResult

VALIDATE_SYSTEM_PROMPT = prompt_registry.get_system_prompt(
    "validate_report",
    """你是一个 API 测试结果分析专家。审查测试执行结果，识别：
1. **真实缺陷**：指 API 行为与预期不符的 bug
2. **测试用例问题**：测试本身设计有问题导致的失败
3. **环境问题**：网络/认证/配置问题导致的失败

对每个失败用例，给出你的判断和严重程度（critical/high/medium/low）。
输出严格的 JSON 格式。""",
)


async def validate_report_node(state: AgentState) -> AgentState:
    """
    验证结果并生成报告。

    输入: execution_results, api_name, base_url, spec_url
    产出: validation_results, report_path, report_summary
    """
    state["current_node"] = "validate"

    results = state.get("execution_results", [])
    api_name = state.get("api_name", "Unknown API")
    base_url = state.get("base_url", "")
    spec_url = state.get("spec_url", "")

    if not results:
        state["error"] = "无测试结果可验证"
        return state

    start = time.perf_counter()

    # 1. 收集所有失败用例，用 LLM 进行语义分析
    failures = [r for r in results if not r.get("passed", False)]
    if failures:
        validation = await _llm_validate_failures(failures, api_name)
        state["validation_results"] = validation
    else:
        state["validation_results"] = []

    # 2. 构建 TestCaseResult 列表
    tc_results: list[TestCaseResult] = []
    for r in results:
        tc_results.append(TestCaseResult(
            case_name=r.get("case_name", "Unknown"),
            passed=r.get("passed", False),
            method=r.get("method", ""),
            path=r.get("path", ""),
            status_code=r.get("status_code", 0),
            elapsed_ms=r.get("elapsed_ms", 0),
            expected_status=r.get("expected_status"),
            category=r.get("category", "unknown"),
            checks=r.get("checks", []),
            error=r.get("error"),
            response_preview=r.get("response_preview", ""),
        ))

    # 3. 生成报告
    duration = time.perf_counter() - start
    report = report_gen.generate(
        api_name=api_name,
        base_url=base_url,
        spec_url=spec_url,
        results=tc_results,
        duration_seconds=duration,
    )

    # 4. 保存报告（Markdown + HTML + JSON）
    from src.config import config
    paths = report_gen.save(report, config.REPORTS_DIR, formats=["md", "html", "json"])

    state["report_path"] = paths.get("md", "")
    state["report_summary"] = (
        f"测试完成！\n"
        f"- 总用例: {report.total_cases}\n"
        f"- 通过: {report.passed} | 失败: {report.failed} | 错误: {report.errors}\n"
        f"- 通过率: {report.pass_rate:.1%}\n"
        f"- 报告: {paths.get('md', 'N/A')}"
    )

    return state


async def _llm_validate_failures(
    failures: list[dict],
    api_name: str,
) -> list[dict]:
    """使用 LLM-as-Judge 分析失败用例"""
    # 精简失败信息
    compact = []
    for f in failures[:20]:  # 最多分析 20 个失败
        compact.append({
            "name": f.get("case_name", ""),
            "method": f.get("method", ""),
            "path": f.get("path", ""),
            "status": f.get("status_code"),
            "expected_status": f.get("expected_status"),
            "category": f.get("category", ""),
            "error": f.get("error", ""),
            "checks": [
                c for c in f.get("checks", []) if not c.get("passed")
            ],
            "response_preview": (f.get("response_preview", "") or "")[:300],
        })

    user_msg = f"""分析以下 {api_name} API 测试的失败用例：

{json.dumps(compact, ensure_ascii=False, indent=2)[:8000]}

对每个失败用例，输出：
{{
  "analysis": [
    {{
      "case_name": "原用例名",
      "verdict": "real_bug" | "test_issue" | "env_issue",
      "severity": "critical" | "high" | "medium" | "low",
      "explanation": "中文说明"
    }}
  ],
  "summary": "整体分析总结（中文，1-2句话）"
}}"""

    try:
        response = llm.chat_with_tools(
            system_prompt=VALIDATE_SYSTEM_PROMPT,
            user_message=user_msg,
            tools=[],  # 本节点不需要工具，仅需 LLM 文本分析
            temperature=0.2,
            max_tokens=2048,
        )
        usage = response.get('usage', {})
        cost_tracker.record(
            model=response.get('model', 'deepseek-chat'),
            tokens_in=usage.get('prompt_tokens', 0),
            tokens_out=usage.get('completion_tokens', 0),
        )
        content = llm.extract_content(response)

        # 提取 JSON
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        analysis = json.loads(content.strip())
        return analysis.get("analysis", [])

    except Exception:
        return [{
            "case_name": f.get("case_name", "Unknown"),
            "verdict": "unknown",
            "severity": "medium",
            "explanation": "LLM 分析失败，请人工审查",
        } for f in failures[:5]]
