#!/usr/bin/env python3
"""
API Test Agent — 一键环境初始化 & 验证脚本

用法:
    python setup_and_test.py              # 完整检查 + 安装 + 测试
    python setup_and_test.py --check-only # 仅检查环境
    python setup_and_test.py --skip-docker # 跳过 Docker 服务启动
    python setup_and_test.py --test-url https://petstore3.swagger.io/api/v3/openapi.json

检查项:
    1.  Python 版本 >= 3.10
    2.  .env 配置文件存在且 API Key 已配置
    3.  pip 依赖完整性
    4.  Docker 运行状态（可选）
    5.  单元测试（32 项）
    6.  综合测试（146 项）
    7.  Mock API E2E 测试
"""

import os
import sys
import subprocess
import shutil
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
#  ANSI Colors
# ============================================================
class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def header(text: str) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 60}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}  {text}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 60}{Color.RESET}\n")


def ok(text: str) -> None:
    print(f"  {Color.GREEN}[OK]{Color.RESET}    {text}")


def warn(text: str) -> None:
    print(f"  {Color.YELLOW}[WARN]{Color.RESET}  {text}")


def fail(text: str) -> None:
    print(f"  {Color.RED}[FAIL]{Color.RESET}  {text}")


def info(text: str) -> None:
    print(f"  {Color.BLUE}[INFO]{Color.RESET}  {text}")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


# ============================================================
#  1. Python 版本检查
# ============================================================
def check_python() -> bool:
    header("1. Python 版本检查")
    major, minor = sys.version_info[:2]
    version_str = f"{major}.{minor}.{sys.version_info.micro}"

    if (major, minor) >= (3, 10):
        ok(f"Python {version_str} (>= 3.10 required)")
        return True
    else:
        fail(f"Python {version_str} — 需要 Python 3.10+")
        return False


# ============================================================
#  2. .env 配置检查
# ============================================================
def check_env() -> bool:
    header("2. 环境变量配置检查")

    env_path = PROJECT_ROOT / ".env"
    env_example_path = PROJECT_ROOT / ".env.example"

    if not env_path.exists():
        if env_example_path.exists():
            warn(".env 文件不存在，正在从 .env.example 复制...")
            shutil.copy(env_example_path, env_path)
            info("已创建 .env 文件，请编辑填入 DeepSeek API Key:")
            info(f"  文件位置: {env_path}")
            return False
        else:
            fail(".env 和 .env.example 均不存在")
            return False

    ok(".env 文件存在")

    # 检查关键配置
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)

        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key or api_key == "sk-your-api-key-here":
            warn("DEEPSEEK_API_KEY 未配置或仍为默认值")
            info("请编辑 .env 文件，填入 DeepSeek API Key")
            return False
        ok(f"DEEPSEEK_API_KEY 已配置 ({api_key[:12]}...)")

        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        ok(f"DEEPSEEK_MODEL = {model}")

        return True

    except Exception as e:
        fail(f"读取 .env 失败: {e}")
        return False


# ============================================================
#  3. pip 依赖检查
# ============================================================
def check_dependencies() -> bool:
    header("3. Python 依赖检查")

    req_path = PROJECT_ROOT / "requirements.txt"
    if not req_path.exists():
        fail("requirements.txt 不存在")
        return False

    ok("requirements.txt 存在")

    # Check key dependencies
    required = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "langgraph": "langgraph",
        "openai": "openai",
        "httpx": "httpx",
        "pydantic": "pydantic",
        "jsonschema": "jsonschema",
        "qdrant_client": "qdrant-client",
        "streamlit": "streamlit",
        "python_dotenv": "python-dotenv",
        "loguru": "loguru",
    }

    missing = []
    for import_name, pkg_name in required.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg_name)

    if missing:
        warn(f"缺少 {len(missing)} 个依赖: {', '.join(missing)}")
        info("正在安装依赖...")
        result = run([sys.executable, "-m", "pip", "install", "-r", str(req_path)])
        if result.returncode == 0:
            ok("依赖安装完成")
            return True
        else:
            fail(f"依赖安装失败:\n{result.stderr[-500:]}")
            return False
    else:
        ok(f"所有 {len(required)} 个关键依赖已安装")
        return True


# ============================================================
#  4. Docker 状态检查
# ============================================================
def check_docker(skip_docker: bool = False) -> bool:
    header("4. Docker 环境检查")

    if skip_docker:
        warn("已跳过 Docker 检查 (--skip-docker)")
        return True

    # Check if docker is available
    docker_cmd = shutil.which("docker")
    if not docker_cmd:
        warn("Docker 未安装或不在 PATH 中，跳过容器检查")
        return True

    ok(f"Docker 已安装: {docker_cmd}")

    # Check if docker daemon is running
    result = run(["docker", "info"], timeout=10)
    if result.returncode != 0:
        warn("Docker daemon 未运行，跳过容器检查")
        return True

    ok("Docker daemon 运行中")

    # Check compose plugin
    compose_result = run(["docker", "compose", "version"], timeout=10)
    if compose_result.returncode == 0:
        ok("Docker Compose 可用")
    else:
        warn("Docker Compose 不可用，将使用 docker-compose（如已安装）")

    return True


# ============================================================
#  5. 单元测试
# ============================================================
def run_unit_tests() -> bool:
    header("5. 单元测试 (tests/)")

    result = run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        timeout=120,
        cwd=str(PROJECT_ROOT),
    )

    if result.returncode == 0:
        ok("所有单元测试通过")
        return True
    else:
        # Print last 40 lines for diagnosis
        lines = result.stdout.split("\n")
        for line in lines[-30:]:
            print(f"       {line}")
        fail("部分单元测试失败")
        return False


# ============================================================
#  6. 综合测试
# ============================================================
def run_comprehensive_tests() -> bool:
    header("6. 综合测试 (test_comprehensive.py)")

    if not (PROJECT_ROOT / "test_comprehensive.py").exists():
        warn("test_comprehensive.py 不存在，跳过")
        return True

    result = run(
        [sys.executable, "test_comprehensive.py"],
        timeout=300,
        cwd=str(PROJECT_ROOT),
    )

    if result.returncode == 0:
        ok("所有综合测试通过")
        return True
    else:
        lines = (result.stdout + result.stderr).split("\n")
        for line in lines[-20:]:
            print(f"       {line}")
        fail("部分综合测试失败")
        return False


# ============================================================
#  7. Mock API E2E 测试
# ============================================================
def run_mock_e2e_test(test_url: str | None = None) -> bool:
    header("7. Mock API E2E 测试")

    if test_url:
        spec_url = test_url
        info(f"使用指定测试 URL: {spec_url}")
    else:
        spec_url = "http://localhost:8000/openapi.json"
        info(f"使用默认测试 URL: {spec_url}")

    info("启动测试（可能需要 30-60 秒，具体取决于 API 规模）...")

    try:
        from src.agent.graph import run_agent

        import asyncio
        async def _run():
            return await run_agent(spec_url=spec_url, auth_config=None, thread_id=None)

        state = asyncio.run(_run())

        if state.get("error"):
            fail(f"Agent 执行出错: {state['error']}")
            return False

        results = state.get("execution_results", [])
        total = len(results)
        passed = sum(1 for r in results if r.get("passed"))
        rate = passed / max(total, 1) * 100

        print()
        info(f"总用例: {total}  |  通过: {passed}  |  通过率: {rate:.1f}%")

        endpoints = len(state.get("endpoints", []))
        info(f"测试端点: {endpoints}  |  API: {state.get('api_name', 'N/A')}")

        report_path = state.get("report_path", "")
        if report_path:
            info(f"报告路径: {report_path}")

        if rate >= 80:
            ok(f"E2E 测试通过率 {rate:.1f}% >= 80%")
            return True
        elif rate >= 60:
            warn(f"E2E 测试通过率 {rate:.1f}% — 建议检查失败用例")
            return True
        else:
            fail(f"E2E 测试通过率仅 {rate:.1f}%")
            return False

    except Exception as e:
        fail(f"E2E 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
#  Main
# ============================================================
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="API Test Agent — 一键环境初始化 & 验证",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python setup_and_test.py                        # 完整初始化 + 测试
  python setup_and_test.py --check-only           # 仅检查环境
  python setup_and_test.py --skip-docker          # 跳过 Docker
  python setup_and_test.py --skip-e2e             # 跳过 E2E 测试
  python setup_and_test.py --test-url https://petstore3.swagger.io/api/v3/openapi.json
        """,
    )
    parser.add_argument("--check-only", action="store_true", help="仅检查环境，不安装/测试")
    parser.add_argument("--skip-docker", action="store_true", help="跳过 Docker 检查")
    parser.add_argument("--skip-unit", action="store_true", help="跳过单元测试")
    parser.add_argument("--skip-comprehensive", action="store_true", help="跳过综合测试")
    parser.add_argument("--skip-e2e", action="store_true", help="跳过 E2E 测试")
    parser.add_argument("--test-url", type=str, default=None, help="E2E 测试目标 URL")
    args = parser.parse_args()

    print(f"\n{Color.BOLD}{Color.CYAN}")
    print("   ╔══════════════════════════════════════════════╗")
    print("   ║       API Test Agent — 环境初始化 & 验证      ║")
    print("   ╚══════════════════════════════════════════════╝")
    print(f"{Color.RESET}")

    results: dict[str, bool] = {}

    # Environment checks
    results["Python"] = check_python()
    if not results["Python"]:
        print(f"\n{Color.RED}请先升级 Python 到 3.10+{Color.RESET}")
        sys.exit(1)

    results[".env"] = check_env()
    results["依赖"] = check_dependencies()
    results["Docker"] = check_docker(skip_docker=args.skip_docker)

    if args.check_only:
        print(f"\n{Color.BOLD}{'─' * 60}{Color.RESET}")
        print(f"{Color.BOLD}  环境检查总结{Color.RESET}")
        print(f"{Color.BOLD}{'─' * 60}{Color.RESET}")
        all_ok = True
        for name, passed in results.items():
            if passed:
                ok(name)
            else:
                fail(name)
                all_ok = False

        if not results[".env"]:
            print(f"\n{Color.YELLOW}  >>> 请先编辑 .env 文件，然后重新运行 setup_and_test.py{Color.RESET}")

        if all_ok:
            print(f"\n{Color.GREEN}  环境就绪，可以运行测试！{Color.RESET}")
        sys.exit(0 if all_ok else 1)

    # Tests
    if not args.skip_unit:
        results["单元测试"] = run_unit_tests()

    if not args.skip_comprehensive:
        results["综合测试"] = run_comprehensive_tests()

    if not args.skip_e2e:
        results["E2E 测试"] = run_mock_e2e_test(test_url=args.test_url)

    # Final summary
    print(f"\n{Color.BOLD}{'=' * 60}{Color.RESET}")
    print(f"{Color.BOLD}  验证总结{Color.RESET}")
    print(f"{Color.BOLD}{'=' * 60}{Color.RESET}\n")

    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    for name, passed in results.items():
        if passed:
            ok(name)
        else:
            fail(name)

    print(f"\n  {Color.BOLD}通过: {passed_count}/{total_count}{Color.RESET}")

    if passed_count == total_count:
        print(f"\n{Color.GREEN}{Color.BOLD}  全部通过！项目已就绪。{Color.RESET}\n")
        print(f"  启动命令:")
        print(f"    docker compose up -d                  # Docker 全栈部署")
        print(f"    uvicorn src.main:app --reload         # 本地开发")
        print(f"    streamlit run frontend/app.py         # 前端 Dashboard")
        sys.exit(0)
    else:
        failed_names = [n for n, v in results.items() if not v]
        print(f"\n{Color.YELLOW}  未通过项: {', '.join(failed_names)}{Color.RESET}")
        print(f"  请修复上述问题后重新运行。\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
