"""
全局配置管理，从 .env 文件和环境变量加载。
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(Path(__file__).parent.parent / ".env")


class Config:
    """应用配置"""

    # === DeepSeek LLM ===
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # === Qdrant ===
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "16333"))
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "api_test_specs")

    # === SQLite ===
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "./data/api_test.db")

    # === LangFuse ===
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")

    # === 服务 ===
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # === Agent 配置 ===
    MAX_TEST_ITERATIONS: int = 80       # 单次最多执行 50 个测试用例
    MAX_RETRIES_PER_CASE: int = 3       # 每个用例最多重试 3 次
    REQUEST_TIMEOUT: int = 30           # HTTP 请求超时（秒）
    MAX_RESPONSE_SIZE: int = 1024 * 1024  # 响应体最大 1MB

    # === 日志 ===
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "./data/api_test.log")

    # === 速率限制（令牌桶） ===
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_RPS: float = float(os.getenv("RATE_LIMIT_RPS", "10"))    # 每秒请求数
    RATE_LIMIT_BURST: int = int(os.getenv("RATE_LIMIT_BURST", "20"))    # 最大突发

    # === 熔断器 ===
    CIRCUIT_BREAKER_ENABLED: bool = True
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = int(os.getenv("CIRCUIT_BREAKER_FAILURES", "5"))
    CIRCUIT_BREAKER_TIMEOUT: float = float(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "30"))

    # === 安全 ===
    SANDBOX_ENABLED: bool = True
    ALLOWED_HOSTS: list[str] = None     # None = 允许所有（可配置白名单）

    # === 项目路径 ===
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    REPORTS_DIR: Path = PROJECT_ROOT / "reports"

    def __post_init__(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.REPORTS_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
config.__post_init__()
