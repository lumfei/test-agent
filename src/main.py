"""
FastAPI 主入口 — API Test Agent REST 后端
"""
from __future__ import annotations

import uuid
import sys
from datetime import datetime, timezone
from typing import Any

import asyncio
import json

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

from src.agent.graph import run_agent
from src.memory import db
from src.config import config
from src.event_bus import event_bus

# ── loguru 配置 ──────────────────────────────────────────────
logger.remove()  # 移除默认 handler
logger.add(
    sys.stderr,
    level=config.LOG_LEVEL,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
)
logger.add(
    config.LOG_FILE,
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="10 MB",
    retention="7 days",
    encoding="utf-8",
)

app = FastAPI(
    title="API Test Agent",
    description="REST API 自动化测试 Agent（LangGraph + DeepSeek）",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Models =====

class TestRequest(BaseModel):
    spec_url: str = Field(..., description="OpenAPI Spec URL 或文档页面 URL")
    auth_type: str | None = Field(None, description="bearer/api_key/basic/oauth2")
    auth_token: str | None = Field(None)
    auth_username: str | None = Field(None)
    auth_password: str | None = Field(None)


# ===== Endpoints =====

@app.get("/api/health")
async def health():
    return {"status": "ok", "model": config.DEEPSEEK_MODEL}


@app.post("/api/test/run")
async def start_test(req: TestRequest, background_tasks: BackgroundTasks):
    """启动一次 API 测试，异步执行，立即返回 run_id"""
    run_id = uuid.uuid4().hex[:12]
    started_at = datetime.now(timezone.utc).isoformat()

    auth_config = {}
    if req.auth_type:
        auth_config["type"] = req.auth_type
        if req.auth_type in ("bearer", "api_key"):
            auth_config["token" if req.auth_type == "bearer" else "key"] = req.auth_token
        elif req.auth_type == "basic":
            auth_config["username"] = req.auth_username
            auth_config["password"] = req.auth_password

    await db.init()
    await db.create_run(run_id=run_id, api_name="Loading...", spec_url=req.spec_url,
                        base_url="", started_at=started_at, config_json=auth_config)

    background_tasks.add_task(_run_agent_background, run_id, req.spec_url, auth_config)

    return {"run_id": run_id, "status": "running", "started_at": started_at,
            "check_status_url": f"/api/test/status/{run_id}"}


@app.get("/api/test/status/{run_id}")
async def get_status(run_id: str):
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/api/test/results/{run_id}")
async def get_results(run_id: str):
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    results = await db.get_run_results(run_id)
    stats = await db.get_category_stats(run_id)
    return {"run": run, "results": results, "categories": stats}


@app.get("/api/test/report/{run_id}")
async def get_report(run_id: str, format: str = "md"):
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    stored_path = run.get("report_path", "")
    if not stored_path:
        raise HTTPException(status_code=404, detail="Report not yet generated")

    # Resolve filename against the runtime reports directory.
    # The stored path may be from a different OS (Windows host vs Linux container),
    # so we extract only the filename and resolve it against the configured dir.
    # Normalize backslashes (Windows) to forward slashes before extracting the name,
    # otherwise Linux Path() sees the entire string as one filename.
    from pathlib import Path

    normalized = stored_path.replace("\\", "/")
    filename = Path(normalized).name
    if format == "html":
        filename = filename.replace(".md", ".html")
    elif format == "json":
        filename = filename.replace(".md", ".json")

    report_path = config.REPORTS_DIR / filename
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")

    media = {"md": "text/markdown", "html": "text/html", "json": "application/json"}
    return FileResponse(str(report_path), media_type=media.get(format, "text/plain"),
                        filename=f"report_{run_id}.{format}")


@app.get("/api/test/history")
async def get_history(limit: int = 20):
    runs = await db.list_runs(limit=limit)
    return {"total": len(runs), "runs": runs}


@app.get("/api/test/stream/{run_id}")
async def stream_test_progress(run_id: str, request: Request):
    """
    SSE 实时流式推送测试执行进度。

    事件类型:
      - progress:  当前执行节点 + 进度百分比
      - case_result: 单个用例执行完成
      - completed: 测试全部完成（含统计摘要）
      - error:     执行出错

    前端消费示例:
      const es = new EventSource('/api/test/stream/{run_id}');
      es.addEventListener('progress', e => console.log(JSON.parse(e.data)));
      es.addEventListener('completed', e => { console.log('Done!'); es.close(); });
    """
    queue: asyncio.Queue[str] = event_bus.subscribe(run_id)

    async def event_generator():
        try:
            while True:
                # 检查客户端是否断开
                if await request.is_disconnected():
                    break

                payload = None
                try:
                    # 等待消息，每 15 秒超时发送心跳
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # 发送心跳保持连接
                    yield ": heartbeat\n\n"

                # 发送完 completed/error 后退出
                if payload and '"event":"completed"' in payload:
                    break
                if payload and '"event":"error"' in payload:
                    break

        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


# ===== Background =====

async def _run_agent_background(run_id: str, spec_url: str, auth_config: dict):
    logger.info(f"测试启动 | run_id={run_id} | spec_url={spec_url}")
    try:
        # 构建进度回调 — 桥接 agent graph 和 SSE 事件总线
        async def on_progress(node: str, pct: float, msg: str):
            await event_bus.publish_progress(run_id, node, pct, msg)

        state = await run_agent(
            spec_url=spec_url,
            auth_config=auth_config,
            thread_id=run_id,
            progress_callback=on_progress,
        )

        cases = state.get("test_cases", [])
        if cases:
            await db.save_test_cases(run_id, cases)

        results = state.get("execution_results", [])
        if results:
            await db.save_test_results(run_id, results)
            # 逐条推送用例结果（SSE）
            for r in results:
                await event_bus.publish_case_result(run_id, r)

        total = len(results)
        passed = sum(1 for r in results if r.get("passed"))
        failed = sum(1 for r in results if not r.get("passed") and not r.get("error"))
        errors = sum(1 for r in results if r.get("error"))
        rate = passed / max(total, 1)

        await db.update_run_stats(run_id, total, passed, failed, errors, rate,
                                  state.get("report_path", ""),
                                  api_name=state.get("api_name", ""),
                                  base_url=state.get("base_url", ""))

        logger.info(
            f"测试完成 | run_id={run_id} | total={total} | passed={passed} | "
            f"failed={failed} | errors={errors} | rate={rate:.1%}"
        )

        # 推送完成事件
        await event_bus.publish_completed(run_id, {
            "run_id": run_id,
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": round(rate * 100, 1),
            "api_name": state.get("api_name", ""),
            "report_path": state.get("report_path", ""),
        })

    except Exception:
        logger.opt(exception=True).error(f"测试执行异常 | run_id={run_id}")
        import traceback
        await event_bus.publish_error(run_id, f"测试执行异常: {traceback.format_exc()}")
        await db.update_run_status(run_id, "error")


@app.on_event("startup")
async def startup():
    await db.init()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=config.API_HOST, port=config.API_PORT, reload=True)
