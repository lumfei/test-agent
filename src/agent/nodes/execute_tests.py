"""
节点 4：Execute Tests — 并发执行所有测试用例。
"""
from __future__ import annotations

import asyncio
import json
import time

from src.agent.state import AgentState
from src.agent.progress_ctx import _progress_cb_ctx
from src.tools import http_client, schema_validator
from src.tools.http_client import HTTPResponse


async def execute_tests_node(state: AgentState) -> AgentState:
    """执行所有测试用例。若存在 regenerated_cases（ReAct 回环），仅执行修正后的用例。"""
    state["current_node"] = "execute"

    # ReAct 回环：仅执行 LLM 修正后的用例
    regenerated = state.get("regenerated_cases", [])
    is_retry = bool(regenerated)

    if is_retry:
        test_cases = regenerated
        state["regenerated_cases"] = []  # 清除，避免无限循环
    else:
        test_cases = state.get("test_cases", [])

    auth_config = state.get("auth_config", {})
    # 从 contextvars 读取（不可序列化的函数，不能放 state 里）
    progress_callback = _progress_cb_ctx.get(None)

    if not test_cases:
        if not is_retry:
            state["error"] = "无测试用例可执行"
        return state

    # 按优先级排序
    priority_order = {"high": 0, "medium": 1, "low": 2}
    sorted_cases = sorted(
        test_cases,
        key=lambda c: priority_order.get(c.get("priority", "medium"), 1)
    )

    from src.config import config
    sorted_cases = sorted_cases[:config.MAX_TEST_ITERATIONS]

    # 分离危险操作（PUT/DELETE/PATCH需要HITL确认）
    safe = []
    dangerous = []
    for tc in sorted_cases:
        if http_client.is_dangerous(tc.get("method", "GET")):
            dangerous.append(tc)
        else:
            safe.append(tc)

    all_results: list[dict] = []
    all_errors: list[dict] = []
    completed = 0
    total = len(safe) + len(dangerous)

    # 先执行安全用例（最多5并发）
    if safe:
        safe_out = await _execute_batch(
            safe, auth_config, max_concurrency=5,
            progress_callback=progress_callback,
            completed_offset=0, total=total,
        )
        all_results.extend(safe_out["results"])
        all_errors.extend(safe_out["errors"])
        completed += len(safe)

    # 危险操作用户确认后串行执行
    if dangerous:
        # 在API模式下默认跳过危险操作，通过参数可启用
        skipped = [
            {
                "case_name": c.get("name", ""),
                "passed": False,
                "method": c.get("method", ""),
                "path": c.get("path", ""),
                "status_code": 0,
                "elapsed_ms": 0,
                "category": c.get("category", "unknown"),
                "expected_status": c.get("expected_status"),
                "expected_schema": c.get("expected_schema"),
                "checks": [{"passed": False, "check_type": "hitl", "detail": "危险操作需人工确认，已跳过"}],
                "error": "HITL_SKIPPED: 危险操作（PUT/DELETE/PATCH）需人工确认",
                "response_preview": "",
            }
            for c in dangerous
        ]
        all_results.extend(skipped)
        completed += len(dangerous)

    # 最终执行进度
    if progress_callback is not None and total > 0:
        import asyncio as _asyncio
        try:
            await progress_callback("execute", 0.90, f"所有 {total} 个用例执行完毕")
        except Exception:
            pass

    # ReAct 回环：将修正后的结果追加到已有结果（不去重）
    # 注意：不能用 (method, path) 做去重 key — 一个端点会有多个用例，
    # 去重 key 太粗会误删所有同端点用例，导致报告只剩 retry 条目。
    if is_retry:
        existing = state.get("execution_results", [])
        existing.extend(all_results)
        state["execution_results"] = existing
        # 同样追加错误
        existing_errs = state.get("execution_errors", [])
        existing_errs.extend(all_errors)
        state["execution_errors"] = existing_errs
    else:
        state["execution_results"] = all_results
        state["execution_errors"] = all_errors

    return state


async def _execute_batch(
    cases: list[dict],
    auth_config: dict,
    max_concurrency: int = 5,
    progress_callback: Any = None,
    completed_offset: int = 0,
    total: int = 0,
) -> dict[str, list[dict]]:
    """并发执行一批测试用例，每完成一个推送进度。"""
    import asyncio as _asyncio
    semaphore = asyncio.Semaphore(max_concurrency)
    completed_count = [0]  # 用列表避免闭包赋值问题

    async def execute_one(case: dict) -> dict:
        async with semaphore:
            result = await _execute_single(case, auth_config)
            completed_count[0] += 1
            # 每完成一个用例推送子进度（execute 阶段 65%→90%）
            if progress_callback is not None and total > 0:
                done = completed_offset + completed_count[0]
                sub_pct = 0.65 + (done / total) * 0.25  # 65% → 90%
                try:
                    await progress_callback(
                        "execute", round(sub_pct, 3),
                        f"执行用例 {done}/{total}: {case.get('name', '?')[:50]}"
                    )
                except Exception:
                    pass
            return result

    tasks = [execute_one(c) for c in cases]
    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[dict] = []
    errors: list[dict] = []

    for i, outcome in enumerate(outcomes):
        case = cases[i]
        if isinstance(outcome, Exception):
            errors.append({
                "case_name": case.get("name", ""),
                "method": case.get("method", ""),
                "path": case.get("path", ""),
                "error": str(outcome),
            })
            results.append({
                "case_name": case.get("name", ""),
                "passed": False,
                "method": case.get("method", ""),
                "path": case.get("path", ""),
                "status_code": 0,
                "elapsed_ms": 0,
                "category": case.get("category", "unknown"),
                "expected_status": case.get("expected_status"),
                "expected_schema": case.get("expected_schema"),
                "checks": [],
                "error": str(outcome),
                "response_preview": "",
            })
        else:
            results.append(outcome)

    return {"results": results, "errors": errors}


async def _execute_single(case: dict, auth_config: dict) -> dict:
    """执行单个测试用例"""
    method = case.get("method", "GET")
    path = case.get("path", "")
    params = case.get("params")
    body = case.get("body")
    headers = case.get("headers") or {}
    expected_status = case.get("expected_status", 200)
    expected_schema = case.get("expected_schema")
    category = case.get("category", "unknown")
    url = path

    auth = None
    if auth_config and auth_config.get("type"):
        auth = auth_config

    try:
        response: HTTPResponse = await http_client.request(
            method=method, url=url, headers=headers,
            params=params, body=body, auth=auth,
        )
    except Exception as e:
        return {
            "case_name": case.get("name", ""),
            "passed": False,
            "method": method, "path": path,
            "status_code": 0, "elapsed_ms": 0,
            "category": category,
            "expected_status": expected_status,
            "expected_schema": expected_schema,
            "checks": [],
            "error": f"请求异常: {type(e).__name__}: {e}",
            "response_preview": "",
        }

    result = {
        "case_name": case.get("name", ""),
        "passed": False,
        "method": method, "path": path,
        "status_code": response.status_code,
        "elapsed_ms": response.elapsed_ms,
        "category": category,
        "expected_status": expected_status,
        "expected_schema": expected_schema,
        "checks": [],
        "error": response.error,
        "response_preview": "",
    }

    if response.error:
        return result

    checks: list[dict] = []
    passed = True

    # 状态码检查
    expected_list = expected_status if isinstance(expected_status, list) else [expected_status]
    status_ok = response.status_code in expected_list
    checks.append({
        "passed": status_ok, "check_type": "status_code",
        "detail": f"状态码: {response.status_code} (期望 {expected_list})",
        "expected": expected_list, "actual": response.status_code,
    })
    if not status_ok:
        passed = False

    # Schema 验证（仅正常用例的 2xx 响应）
    if expected_schema and 200 <= response.status_code < 300 and category == "normal":
        schema_result = schema_validator.validate_json_schema(response.body, expected_schema)
        checks.append({
            "passed": schema_result.passed, "check_type": "schema",
            "detail": schema_result.detail,
            "expected": str(expected_schema)[:200],
            "actual": "(验证通过)" if schema_result.passed else str(response.body)[:200],
        })
        if not schema_result.passed:
            passed = False

    # 响应时间检查（LLM API 响应可能较慢，阈值设为 25s）
    if response.elapsed_ms > 25000:
        checks.append({
            "passed": False, "check_type": "response_time",
            "detail": f"响应时间过长: {response.elapsed_ms:.0f}ms (阈值 25000ms)",
        })
        passed = False

    preview = (
        json.dumps(response.body, ensure_ascii=False)
        if isinstance(response.body, (dict, list))
        else str(response.body)
    )
    result["response_preview"] = preview[:500]
    result["passed"] = passed
    result["checks"] = checks

    return result
