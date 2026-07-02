"""
Qdrant 向量存储 — 存储 API Spec Embedding，用于相似端点检索和历史用例召回。
"""
from __future__ import annotations

import hashlib
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from src.config import config


class QdrantStore:
    """Qdrant 向量数据库"""

    VECTOR_SIZE = 1536  # DeepSeek embedding 维度（兼容 OpenAI text-embedding-3-small）

    def __init__(self):
        self.client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
        self.collection = config.QDRANT_COLLECTION

    def ensure_collection(self):
        """确保 collection 存在"""
        try:
            self.client.get_collection(self.collection)
        except (UnexpectedResponse, Exception):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(
                    size=self.VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                ),
            )

    def store_endpoint(
        self,
        endpoint_id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ):
        """
        存储一个 API 端点的 Embedding。

        Args:
            endpoint_id: 端点的唯一标识（如 method+path 的 hash）
            content: 端点的文本描述
            embedding: 向量
            metadata: 附加元数据
        """
        self.ensure_collection()

        point_id = int(hashlib.md5(endpoint_id.encode()).hexdigest()[:16], 16) % (2**63)

        self.client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "endpoint_id": endpoint_id,
                        "content": content[:2000],
                        "metadata": metadata or {},
                    },
                )
            ],
        )

    def search_similar(
        self,
        query_embedding: list[float],
        limit: int = 5,
        score_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """
        搜索与查询相似的端点。

        Returns:
            [{"endpoint_id": ..., "content": ..., "score": ...}, ...]
        """
        self.ensure_collection()

        try:
            results = self.client.search(
                collection_name=self.collection,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
            )

            return [
                {
                    "endpoint_id": r.payload.get("endpoint_id", ""),
                    "content": r.payload.get("content", ""),
                    "metadata": r.payload.get("metadata", {}),
                    "score": r.score,
                }
                for r in results
            ]
        except Exception:
            return []

    def delete_endpoint(self, endpoint_id: str):
        """删除端点"""
        point_id = int(hashlib.md5(endpoint_id.encode()).hexdigest()[:16], 16) % (2**63)
        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=models.PointIdsList(points=[point_id]),
            )
        except Exception:
            pass


# 全局单例
qdrant = QdrantStore()
