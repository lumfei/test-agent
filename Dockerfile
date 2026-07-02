# ============================================================
# API Test Agent — FastAPI 后端
# 多阶段构建: builder → runtime
# ============================================================

# ---- Stage 1: Builder ----
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖到隔离目录
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: Runtime ----
FROM python:3.12-slim AS runtime

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

# 安装运行时系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/data /app/reports \
    && chown -R appuser:appuser /app

# 从 builder 复制已安装的依赖
COPY --from=builder /install /usr/local

# 复制源码
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY .env.example ./

# 切换到非 root 用户
USER appuser

EXPOSE 8000

# HEALTHCHECK — 每 30 秒检查一次
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
