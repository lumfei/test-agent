"""
节点 6：Reflect — ReAct 循环的反思节点。

实现 Reasoning → Acting → Observing 闭环：
  1. Reasoning: LLM 分析失败用例，判断真实 Bug / 测试设计问题 / 环境问题
  2. Acting: 对测试设计问题，LLM 自动修正期望值和参数
  3. Observing: 修正后的用例重新进入 Execute 节点执行

这是 Agent 区别于普通自动化脚本的核心——能自我纠错。
"""
from __future__ import annotations

import json

from src.agent.state import AgentState
from src.llm import llm
from src.observability import cost_tracker

REFLECT_SYSTEM_PROMPT = """你是一个 API 测试结果分析专家，负责审视测试失败的原因并修正测试用例。

## 你的任务
对每个失败用例，判断失败原因类型：
- **real_bug**: 测试设计合理，API 返回确实不符合预期 → 真正的缺陷
- **test_issue**: 测试用例本身有问题（期望状态码不合理、参数错误、Schema 不匹配）→ 你需要修正
- **env_issue**: 网络/认证/配置问题 → 无法通过修改用例解决

## 修正规则
对于 test_issue 类型的用例，输出修正后的版本：
- 调整 expected_status 为合理的值
- 修正 params/body 使其符合 API 实际要求
- 如果发现 response 提示缺少某个参数，补充它
- 如果 API 实际返回 200 但用例期望 400，改为接受 200（说明 API 较宽容）

## 重要
- 只修正 test_issue 类型的用例
- real_bug 和 env_issue 保持原样标记即可
- 一个用例最多修正一次（避免无限循环）
- 输出严格 JSON 格式"""

# 最大反思迭代次数
MAX_REFLECT_ITERATIONS = 2


async def reflect_node(state: AgentState) -> AgentState:
    """
    ReAct 反思节点。

    分析失败用例 → 修正测试设计问题 → 生成再生用例列表。

    输入: execution_results, validation_results, reflect_iteration
    产出: regenerated_cases, reflect_iteration
    """
    state["current_node"] = "reflect"

    results = state.get("execution_results", [])
    validation = state.get("validation_results", [])
    iteration = state.get("reflect_iteration", 0)
    api_name = state.get("api_name", "Unknown API")

    # 检查迭代上限
    if iteration >= MAX_REFLECT_ITERATIONS:
        state["regenerated_cases"] = []
        return state

    # 收集失败用例
    failures = [r for r in results if not r.get("passed", False)]

    # 排除已知原因：
    # - HITL_SKIPPED: 危险操作跳过，无需修正
    # - 熔断器拒绝: 环境问题，无需修正
    # - 网络/超时错误: 环境问题
    actionable = []
    for f in failures:
        error = f.get("error", "") or ""
        if "HITL_SKIPPED" in error:
            continue
        if "熔断器" in error:
            continue
        if any(kw in error for kw in ("超时", "连接失败", "Timeout", "ConnectError")):
            continue
        actionable.append(f)

    if not actionable:
        state["regenerated_cases"] = []
        return state

    # 限制分析的失败用例数
    actionable = actionable[:15]

    # ── Reasoning: LLM 分析每个失败 ──────────────────────────
    compact = []
    for f in actionable:
        compact.append({
            "name": f.get("case_name", ""),
            "method": f.get("method", ""),
            "path": f.get("path", ""),
            "category": f.get("category", ""),
            "status": f.get("status_code"),
            "expected_status": f.get("expected_status"),
            "error": f.get("error", ""),
            "checks": [c for c in f.get("checks", []) if not c.get("passed")],
            # 带上原始参数，方便 LLM 修正
            "params": f.get("params"),
            "body": f.get("body"),
            "headers": f.get("headers"),
        })

    user_msg = f"""分析 {api_name} 的 {len(compact)} 个测试失败用例：

{json.dumps(compact, ensure_ascii=False, indent=2)[:12000]}

对每个失败用例，按以下格式输出（严格 JSON）：
{{
  "reflections": [
    {{
      "case_name": "原用例名",
      "failure_type": "real_bug | test_issue | env_issue",
      "reason": "中文说明为什么这样判断",
      "severity": "critical | high | medium | low",
      "corrected_case": null   // 仅 test_issue 时需要，见下方格式
    }}
  ],
  "summary": "整体反思总结（中文，1-2句）"
}}

对于 failure_type="test_issue" 的用例，corrected_case 格式：
{{
  "name": "修正后的用例名（加 [retry] 前缀）",
  "expected_status": 200,      // 修正后的期望状态码，可以是 [200, 201] 这样的列表
  "params": {{}},              // 修正后的参数（保持原值如果不需要改）
  "body": {{}},               // 修正后的请求体（保持原值如果不需要改）
  "headers": {{}},            // 修正后的 headers（保持原值如果不需要改）
  "reason": "修正说明"
}}"""

    try:
        response = llm.chat_with_tools(
            system_prompt=REFLECT_SYSTEM_PROMPT,
            user_message=user_msg,
            tools=[],  # 本节点不需要工具，仅需 LLM 文本分析
            temperature=0.3,
            max_tokens=4096,
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
        reflections = analysis.get("reflections", [])
    except Exception:
        # LLM 分析失败，放弃本次反思
        state["regenerated_cases"] = []
        state["reflect_iteration"] = iteration + 1
        return state

    # ── Acting: 为 test_issue 用例生成修正版本 ─────────────────
    regenerated = []
    bug_count = 0
    test_issue_count = 0
    env_issue_count = 0

    for ref in reflections:
        ft = ref.get("failure_type", "env_issue")
        if ft == "real_bug":
            bug_count += 1
        elif ft == "test_issue":
            test_issue_count += 1
            corrected = ref.get("corrected_case")
            if corrected and isinstance(corrected, dict):
                # 从原始用例中找到对应的原始数据来构建完整用例
                original = _find_original_case(actionable, ref.get("case_name", ""))
                new_case = _build_regenerated_case(original, corrected)
                if new_case is not None:
                    regenerated.append(new_case)
        elif ft == "env_issue":
            env_issue_count += 1

    state["regenerated_cases"] = regenerated
    state["reflect_iteration"] = iteration + 1

    # 将反思摘要写入 state 供报告使用
    summary = analysis.get("summary", f"反思完成: {bug_count} 真实Bug, {test_issue_count} 测试问题, {env_issue_count} 环境问题")
    existing = state.get("report_summary", "")
    state["report_summary"] = (
        f"{existing}\n\n## 🔄 ReAct 反思 (第 {iteration + 1} 轮)\n{summary}"
        if existing else f"## 🔄 ReAct 反思 (第 {iteration + 1} 轮)\n{summary}"
    )

    if regenerated:
        state["report_summary"] += f"\n- 已修正 {len(regenerated)} 个测试用例，将重新执行"

    return state


def _find_original_case(actionable: list[dict], case_name: str) -> dict:
    """在 actionable 列表中查找原始用例（精确匹配优先，模糊匹配兜底）"""
    # 精确匹配
    for c in actionable:
        if c.get("case_name") == case_name:
            return c
    # 模糊匹配：LLM 可能微调了 case_name（如去掉前缀、截断等）
    # 取 case_name 的核心部分（去掉方法前缀和路径，只留关键词）
    keywords = case_name.replace("[", "").replace("]", "").split()
    for c in actionable:
        name = c.get("case_name", "")
        # 如果 LLM 返回的 case_name 包含原始 name 的关键部分，认为匹配
        match_count = sum(1 for kw in keywords if kw in name)
        if match_count >= max(2, len(keywords) // 2):
            return c
    # 返回第一个作为 fallback（避免生成空 case）
    return actionable[0] if actionable else {}


def _build_regenerated_case(original: dict, corrected: dict) -> dict | None:
    """
    根据 LLM 修正结果构建完整的再生测试用例。

    保留原始用例的所有字段，只更新 LLM 明确修正的部分。
    如果原始用例数据不足以构建合法 case（如 method/path 缺失），返回 None。
    """
    method = original.get("method", "")
    path = original.get("path", "")
    if not method or not path:
        return None  # 无法构建合法的测试用例

    case = {
        "name": corrected.get("name", f"[retry] {original.get('case_name', 'unknown')}"),
        "description": f"ReAct 修正: {corrected.get('reason', 'LLM 自动修正')}",
        "method": method,
        "path": path,
        "params": corrected.get("params") if "params" in corrected else original.get("params"),
        "body": corrected.get("body") if "body" in corrected else original.get("body"),
        "headers": corrected.get("headers") if "headers" in corrected else original.get("headers"),
        "expected_status": corrected.get("expected_status", original.get("expected_status", 200)),
        "expected_schema": original.get("expected_schema"),
        "priority": "high",  # 修正后的用例优先执行
        "category": original.get("category", "normal"),
        "tags": (original.get("tags", []) or []) + ["react-retry"],
    }
    return case
