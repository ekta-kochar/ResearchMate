"""Persistent exact-query cache for online literature searches."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

CACHE_COLLECTION_NAME = "researchmate_online_query_cache"


def _normalized_query(query: str) -> str:
    return " ".join(query.casefold().split())


def _query_id(query: str) -> str:
    normalized = _normalized_query(query)
    return "online-query:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_cached_online_search(client: Any, query: str) -> dict[str, Any] | None:
    """Return cached metadata for a successful exact query, if present."""
    collection = client.get_or_create_collection(
        name=CACHE_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "researchmate_cache": "online-query-v1"},
    )
    result = collection.get(ids=[_query_id(query)], include=["metadatas"])
    metadatas = result.get("metadatas") or []
    return metadatas[0] if metadatas else None


def cache_online_search(
    client: Any, query: str, record_count: int
) -> None:
    """Mark an exact query successful after its records were stored."""
    collection = client.get_or_create_collection(
        name=CACHE_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "researchmate_cache": "online-query-v1"},
    )
    normalized = _normalized_query(query)
    collection.upsert(
        ids=[_query_id(query)],
        documents=[normalized],
        metadatas=[
            {
                "query": normalized,
                "record_count": int(record_count),
                "searched_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )
