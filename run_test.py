"""
Quick test script — 直接调用 Agent 测试目标 API。
用法: python run_test.py
"""
import asyncio
import sys
import os

# Fix Windows GBK encoding for emoji
sys.stdout.reconfigure(encoding='utf-8')

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agent.graph import run_agent


async def main():
    spec_url = "http://localhost:8000/openapi.json"
    print(f"🚀 开始测试: {spec_url}")
    print("-" * 60)

    state = await run_agent(
        spec_url=spec_url,
        auth_config=None,
        thread_id=None,
    )

    # Print summary
    if state.get("error"):
        print(f"\n❌ 错误: {state['error']}")
    else:
        print(f"\n✅ Agent 执行完成!")
        print(f"   API: {state.get('api_name', 'N/A')}")
        print(f"   Base URL: {state.get('base_url', 'N/A')}")
        print(f"   端点数量: {len(state.get('endpoints', []))}")
        print(f"   生成测试用例: {len(state.get('test_cases', []))}")
        print(f"   执行结果: {len(state.get('execution_results', []))}")

        results = state.get("execution_results", [])
        passed = sum(1 for r in results if r.get("passed"))
        failed = sum(1 for r in results if not r.get("passed") and not r.get("error"))
        errors = sum(1 for r in results if r.get("error"))
        print(f"   通过: {passed} / 失败: {failed} / 错误: {errors}")

        # Print report summary
        report = state.get("report_summary", "")
        if report:
            print(f"\n📊 报告概要:\n{report[:2000]}")

        report_path = state.get("report_path", "")
        if report_path:
            print(f"\n📁 报告路径: {report_path}")

        # Print failed cases
        if failed > 0 or errors > 0:
            print(f"\n🔍 失败/错误详情:")
            for r in results:
                if not r.get("passed"):
                    status = r.get("status_code", "?")
                    expected = r.get("expected_status", "?")
                    print(f"  [{r.get('category', '?')}] {r.get('method', '?')} {r.get('path', '?')}")
                    print(f"      状态码: {status} (期望: {expected})")
                    err = r.get("error", "")
                    if err:
                        print(f"      错误: {err}")
                    for c in r.get("checks", []):
                        if not c.get("passed"):
                            print(f"      检查失败 [{c.get('check_type')}]: {c.get('detail')}")


if __name__ == "__main__":
    asyncio.run(main())
