"""
SQLite-based LangGraph checkpoint saver.
Replaces MemorySaver with persistent storage for session recovery.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, AsyncIterator

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    CheckpointTuple,
    Checkpoint,
    CheckpointMetadata,
    ChannelVersions,
)


class SQLiteSaver(BaseCheckpointSaver):
    """
    Persistent checkpoint saver backed by SQLite.
    Survives process restarts — enables session resume.
    """

    def __init__(self, db_path: str = "./data/api_test_checkpoint.db"):
        super().__init__()
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    parent_checkpoint_id TEXT,
                    checkpoint BLOB NOT NULL,
                    metadata BLOB,
                    created_at TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY (thread_id, checkpoint_id)
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoint_writes (
                    thread_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    idx INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    value BLOB,
                    PRIMARY KEY (thread_id, checkpoint_id, task_id, idx)
                )
            """)
            self._conn.commit()
        return self._conn

    def get_tuple(self, config: dict) -> CheckpointTuple | None:
        conn = self._ensure_conn()
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id")

        if checkpoint_id:
            row = conn.execute(
                "SELECT checkpoint, metadata, parent_checkpoint_id FROM checkpoints "
                "WHERE thread_id = ? AND checkpoint_id = ?",
                (thread_id, checkpoint_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT checkpoint, metadata, parent_checkpoint_id FROM checkpoints "
                "WHERE thread_id = ? ORDER BY created_at DESC LIMIT 1",
                (thread_id,),
            ).fetchone()

        if not row:
            return None

        checkpoint = json.loads(row[0])
        metadata = json.loads(row[1]) if row[1] else {}
        parent_id = row[2]

        # Load pending writes
        writes = []
        write_rows = conn.execute(
            "SELECT task_id, channel, value FROM checkpoint_writes "
            "WHERE thread_id = ? AND checkpoint_id = ? ORDER BY idx",
            (thread_id, checkpoint["id"]),
        ).fetchall()
        for wr in write_rows:
            writes.append((wr[0], wr[1], json.loads(wr[2]) if wr[2] else None))

        return CheckpointTuple(
            config=config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config={"configurable": {"thread_id": thread_id, "checkpoint_id": parent_id}} if parent_id else None,
            pending_writes=writes,
        )

    def list(
        self,
        config: dict | None,
        *,
        filter: dict | None = None,
        before: dict | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        # This is a simplified sync version; full async would need aiosqlite
        conn = self._ensure_conn()
        thread_id = config.get("configurable", {}).get("thread_id", "default") if config else "default"

        query = "SELECT checkpoint, metadata, parent_checkpoint_id, checkpoint_id FROM checkpoints WHERE thread_id = ? ORDER BY created_at DESC"
        params: list = [thread_id]
        if limit:
            query += " LIMIT ?"
            params.append(limit)

        rows = conn.execute(query, params).fetchall()
        for row in rows:
            checkpoint = json.loads(row[0])
            metadata = json.loads(row[1]) if row[1] else {}
            parent_id = row[2]
            cid = row[3]
            yield CheckpointTuple(
                config={"configurable": {"thread_id": thread_id, "checkpoint_id": cid}},
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config={"configurable": {"thread_id": thread_id, "checkpoint_id": parent_id}} if parent_id else None,
            )

    def put(
        self,
        config: dict,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> dict:
        conn = self._ensure_conn()
        thread_id = config.get("configurable", {}).get("thread_id", "default")

        conn.execute(
            "INSERT OR REPLACE INTO checkpoints (thread_id, checkpoint_id, parent_checkpoint_id, checkpoint, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                thread_id,
                checkpoint["id"],
                metadata.get("parent_checkpoint_id", ""),
                json.dumps(checkpoint, default=str),
                json.dumps(metadata, default=str),
            ),
        )
        conn.commit()
        return {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint["id"]}}

    def put_writes(
        self,
        config: dict,
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        conn = self._ensure_conn()
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id", "")

        for idx, (channel, value) in enumerate(writes):
            conn.execute(
                "INSERT OR REPLACE INTO checkpoint_writes (thread_id, checkpoint_id, task_id, idx, channel, value) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (thread_id, checkpoint_id, task_id, idx, channel, json.dumps(value, default=str)),
            )
        conn.commit()

    def delete_thread(self, thread_id: str) -> None:
        conn = self._ensure_conn()
        conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM checkpoint_writes WHERE thread_id = ?", (thread_id,))
        conn.commit()

    # === Async wrappers (required by LangGraph ainvoke) ===

    async def aget_tuple(self, config: dict) -> CheckpointTuple | None:
        import asyncio
        return await asyncio.to_thread(self.get_tuple, config)

    async def aput(
        self,
        config: dict,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> dict:
        import asyncio
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: dict,
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        import asyncio
        return await asyncio.to_thread(self.put_writes, config, writes, task_id)

    async def alist(
        self,
        config: dict | None,
        *,
        filter: dict | None = None,
        before: dict | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        import asyncio
        # Collect results from sync generator in thread
        results = await asyncio.to_thread(
            lambda: list(self.list(config, filter=filter, before=before, limit=limit))
        )
        for r in results:
            yield r

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
