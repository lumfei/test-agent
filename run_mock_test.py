"""Test the mock buggy API to demonstrate bug detection."""
import asyncio, sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.agent.graph import run_agent

async def main():
    spec_url = "http://localhost:8003/openapi.json"
    print(f"Testing Mock Buggy API: {spec_url}")
    print("-" * 60)

    state = await run_agent(spec_url=spec_url, auth_config=None, thread_id=None)

    if state.get("error"):
        print(f"\nERROR: {state['error']}")
        return

    print(f"\nAPI: {state.get('api_name')}")
    print(f"Base URL: {state.get('base_url')}")
    print(f"Endpoints: {len(state.get('endpoints', []))}")
    print(f"Generated test cases: {len(state.get('test_cases', []))}")

    results = state.get("execution_results", [])
    passed = sum(1 for r in results if r.get("passed"))
    failed = sum(1 for r in results if not r.get("passed") and not r.get("error"))
    errors = sum(1 for r in results if r.get("error"))
    total = len(results)
    print(f"Executed: {total} | Passed: {passed} | Failed: {failed} | Errors: {errors}")
    print(f"Pass rate: {passed/max(total,1)*100:.1f}%")

    # Show failures in detail
    bugs_found = []
    for r in results:
        if not r.get("passed"):
            name = r.get("case_name", "")
            status = r.get("status_code", "?")
            expected = r.get("expected_status", "?")
            cat = r.get("category", "?")

            # Classify the failure
            is_bug = False
            bug_type = ""
            if status == 500:
                is_bug = True
                bug_type = "Server 500 error (real bug!)"
            elif status == 200 and isinstance(expected, list) and all(e >= 400 for e in expected):
                is_bug = True
                bug_type = "Expected error but got 200 (validation bypass!)"
            elif cat == "normal" and status not in (200, 201):
                if status == 500:
                    is_bug = True
                    bug_type = "Normal case got 500 (real bug!)"

            bugs_found.append({
                "name": name, "method": r.get("method"), "path": r.get("path"),
                "status": status, "expected": expected, "category": cat,
                "is_bug": is_bug, "bug_type": bug_type,
                "checks": [c for c in r.get("checks", []) if not c.get("passed")],
            })

    if bugs_found:
        print(f"\n{'='*60}")
        print(f"BUGS & FAILURES FOUND: {len(bugs_found)}")
        print(f"{'='*60}")
        for i, b in enumerate(bugs_found, 1):
            marker = "[REAL BUG]" if b["is_bug"] else "[expected/edge case]"
            print(f"\n{i}. {marker} [{b['category']}] {b['method']} {b['path']}")
            print(f"   Status: {b['status']} | Expected: {b['expected']}")
            if b["is_bug"]:
                print(f"   >>> {b['bug_type']}")
            for c in b["checks"]:
                print(f"   Check [{c.get('check_type')}]: {c.get('detail')}")

    # Print real bugs summary
    real_bugs = [b for b in bugs_found if b["is_bug"]]
    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(real_bugs)} real bugs detected out of {len(bugs_found)} failures")
    print(f"Pass rate: {passed}/{total} ({passed/max(total,1)*100:.1f}%)")
    if real_bugs:
        print(f"REAL BUGS:")
        for b in real_bugs:
            print(f"  - {b['name']}: {b['bug_type']}")

    report_path = state.get("report_path", "")
    if report_path:
        print(f"\nReport: {report_path}")

if __name__ == "__main__":
    asyncio.run(main())
