"""
SQLite 持久化存储 — 测试用例、执行记录、报告的 CRUD。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

from src.config import config


class SQLiteStore:
    """SQLite 数据持久化"""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or config.SQLITE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def init(self):
        """初始化数据库表"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS test_runs (
                    id TEXT PRIMARY KEY,
                    api_name TEXT NOT NULL,
                    spec_url TEXT,
                    base_url TEXT,
                    status TEXT DEFAULT 'running',
                    total_cases INTEGER DEFAULT 0,
                    passed INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    pass_rate REAL DEFAULT 0.0,
                    report_path TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    config_json TEXT
                );

                CREATE TABLE IF NOT EXISTS test_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    params_json TEXT,
                    body_json TEXT,
                    expected_status TEXT,
                    expected_schema_json TEXT,
                    priority TEXT DEFAULT 'medium',
                    category TEXT DEFAULT 'normal',
                    tags_json TEXT DEFAULT '[]',
                    FOREIGN KEY (run_id) REFERENCES test_runs(id)
                );

                CREATE TABLE IF NOT EXISTS test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    case_name TEXT NOT NULL,
                    passed INTEGER DEFAULT 0,
                    method TEXT,
                    path TEXT,
                    status_code INTEGER,
                    elapsed_ms REAL,
                    category TEXT,
                    expected_status TEXT,
                    checks_json TEXT DEFAULT '[]',
                    error TEXT,
                    response_preview TEXT,
                    FOREIGN KEY (run_id) REFERENCES test_runs(id)
                );

                CREATE INDEX IF NOT EXISTS idx_test_runs_api ON test_runs(api_name);
                CREATE INDEX IF NOT EXISTS idx_test_runs_time ON test_runs(started_at);
                CREATE INDEX IF NOT EXISTS idx_results_run ON test_results(run_id);
                CREATE INDEX IF NOT EXISTS idx_results_passed ON test_results(run_id, passed);
            """)
            # 数据库迁移：为已有表添加 expected_status 列（v0.2.0+）
            try:
                await db.execute("ALTER TABLE test_results ADD COLUMN expected_status TEXT")
            except Exception:
                pass  # 列已存在
            await db.commit()

    # === Test Runs ===

    async def create_run(
        self,
        run_id: str,
        api_name: str,
        spec_url: str | None,
        base_url: str,
        started_at: str,
        config_json: dict | None = None,
    ):
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO test_runs
                   (id, api_name, spec_url, base_url, status, started_at, config_json)
                   VALUES (?, ?, ?, ?, 'running', ?, ?)""",
                (run_id, api_name, spec_url, base_url, started_at,
                 json.dumps(config_json) if config_json else None)
            )
            await db.commit()

    async def update_run_status(self, run_id: str, status: str, finished_at: str | None = None):
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            if finished_at:
                await db.execute(
                    "UPDATE test_runs SET status = ?, finished_at = ? WHERE id = ?",
                    (status, finished_at, run_id)
                )
            else:
                await db.execute(
                    "UPDATE test_runs SET status = ? WHERE id = ?",
                    (status, run_id)
                )
            await db.commit()

    async def update_run_stats(
        self, run_id: str, total: int, passed: int, failed: int,
        errors: int, pass_rate: float, report_path: str | None = None,
        api_name: str | None = None, base_url: str | None = None,
    ):
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE test_runs
                   SET total_cases = ?, passed = ?, failed = ?, errors = ?,
                       pass_rate = ?, report_path = ?,
                       api_name = COALESCE(?, api_name),
                       base_url = COALESCE(?, base_url),
                       status = 'completed',
                       finished_at = datetime('now')
                   WHERE id = ?""",
                (total, passed, failed, errors, pass_rate, report_path,
                 api_name, base_url, run_id)
            )
            await db.commit()

    async def get_run(self, run_id: str) -> dict | None:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM test_runs WHERE id = ?", (run_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_runs(self, limit: int = 20) -> list[dict]:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM test_runs ORDER BY started_at DESC LIMIT ?", (limit,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    # === Test Cases ===

    async def save_test_cases(self, run_id: str, cases: list[dict]):
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                """INSERT INTO test_cases
                   (run_id, name, description, method, path, params_json,
                    body_json, expected_status, expected_schema_json, priority, category, tags_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        run_id,
                        c.get("name", ""),
                        c.get("description", ""),
                        c.get("method", ""),
                        c.get("path", ""),
                        json.dumps(c.get("params")),
                        json.dumps(c.get("body")),
                        json.dumps(c.get("expected_status")),
                        json.dumps(c.get("expected_schema")),
                        c.get("priority", "medium"),
                        c.get("category", "normal"),
                        json.dumps(c.get("tags", [])),
                    )
                    for c in cases
                ]
            )
            await db.commit()

    # === Test Results ===

    async def save_test_results(self, run_id: str, results: list[dict]):
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                """INSERT INTO test_results
                   (run_id, case_name, passed, method, path, status_code,
                    elapsed_ms, category, expected_status, checks_json, error, response_preview)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        run_id,
                        r.get("case_name", ""),
                        1 if r.get("passed") else 0,
                        r.get("method", ""),
                        r.get("path", ""),
                        r.get("status_code", 0),
                        r.get("elapsed_ms", 0),
                        r.get("category", ""),
                        json.dumps(r.get("expected_status")),
                        json.dumps(r.get("checks", [])),
                        r.get("error"),
                        (r.get("response_preview", "") or "")[:500],
                    )
                    for r in results
                ]
            )
            await db.commit()

    async def get_run_results(self, run_id: str) -> list[dict]:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM test_results WHERE run_id = ? ORDER BY id", (run_id,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_category_stats(self, run_id: str) -> list[dict]:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT category, COUNT(*) as total,
                          SUM(passed) as passed,
                          COUNT(*) - SUM(passed) as failed
                   FROM test_results WHERE run_id = ?
                   GROUP BY category""",
                (run_id,)
            )
            return [
                {"category": row[0], "total": row[1], "passed": row[2], "failed": row[3]}
                async for row in cursor
            ]

    async def _ensure_init(self):
        """确保已初始化"""
        if not hasattr(self, "_initialized"):
            await self.init()
            self._initialized = True


# 全局单例
db = SQLiteStore()
