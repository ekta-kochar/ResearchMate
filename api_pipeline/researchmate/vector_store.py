"""Persistent ChromaDB storage for validated ResearchMate papers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from .deduplication import deduplicate_paper_records
from .normalization import standardize_paper_record
from .schema import validate_paper_record

DEFAULT_PERSIST_DIRECTORY = Path(__file__).resolve().parent.parent / "chroma_db"
DEFAULT_COLLECTION_NAME = "researchmate_papers"


def _paper_id(record: dict[str, Any]) -> str:
    canonical_id = record.get("canonical_id")
    if canonical_id:
        return str(canonical_id)
    identity = "|".join(
        str(record.get(field) or "") for field in ("source", "source_id", "title", "year")
    )
    return "researchmate:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _document_text(record: dict[str, Any]) -> str:
    sections = []
    if record.get("title"):
        sections.append(f"Title: {record['title']}")
    if record.get("authors"):
        sections.append("Authors: " + "; ".join(record["authors"]))
    if record.get("abstract"):
        sections.append(f"Abstract: {record['abstract']}")
    if record.get("keywords"):
        sections.append("Keywords: " + "; ".join(record["keywords"]))
    return "\n".join(sections) or f"Academic paper record: {_paper_id(record)}"


def _metadata(record: dict[str, Any]) -> dict[str, str | int | float | bool]:
    metadata: dict[str, str | int | float | bool] = {}
    for field in ("canonical_id", "source", "source_id", "title", "year", "doi", "url", "query"):
        value = record.get(field)
        if value is not None and value != "":
            metadata[field] = value
    # JSON strings preserve nested values while remaining valid Chroma metadata.
    metadata["record_json"] = json.dumps(record, ensure_ascii=False, sort_keys=True)
    return metadata


class ChromaPaperStore:
    """Validated paper storage backed by a persistent local Chroma collection.

    Chroma's default embedding function is used unless a compatible function is
    injected. It embeds each document on upsert and embeds query text on search.
    """

    def __init__(
        self,
        persist_directory: str | Path = DEFAULT_PERSIST_DIRECTORY,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        embedding_function: Callable[..., Any] | None = None,
    ) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise ImportError(
                "ChromaDB is required for persistent storage. Install it with "
                "'python -m pip install -r requirements.txt'."
            ) from exc

        self.persist_directory = Path(persist_directory).expanduser().resolve()
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.client = chromadb.PersistentClient(path=str(self.persist_directory))
        options: dict[str, Any] = {
            "name": collection_name,
            "metadata": {"hnsw:space": "cosine", "researchmate_schema": "1"},
        }
        if embedding_function is not None:
            options["embedding_function"] = embedding_function
        self.collection = self.client.get_or_create_collection(**options)

    def close(self) -> None:
        """Close the Chroma client and release its local database handles."""
        close_client = getattr(self.client, "close", None)
        if callable(close_client):
            close_client()

    def __enter__(self) -> "ChromaPaperStore":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def upsert_records(self, records: list[dict[str, Any]]) -> int:
        """Validate, deduplicate, embed, and persist paper records.

        Returns the number of unique records upserted. Repeating an upsert for
        the same canonical identifier updates that item instead of duplicating it.
        """
        normalized = [standardize_paper_record(record) for record in records]
        unique = deduplicate_paper_records(normalized)
        for record in unique:
            validate_paper_record(record)
        if not unique:
            return 0

        ids = [_paper_id(record) for record in unique]
        documents = [_document_text(record) for record in unique]
        metadatas = [_metadata(record) for record in unique]
        get_batch_size = getattr(self.client, "get_max_batch_size", None)
        batch_size = get_batch_size() if callable(get_batch_size) else len(unique)
        batch_size = max(1, int(batch_size))
        for start in range(0, len(unique), batch_size):
            stop = start + batch_size
            self.collection.upsert(
                ids=ids[start:stop],
                documents=documents[start:stop],
                metadatas=metadatas[start:stop],
            )
        return len(unique)

    def get_records(
        self, ids: list[str] | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Read stored validated paper records by ID or collection order."""
        options: dict[str, Any] = {"include": ["metadatas"]}
        if ids is not None:
            options["ids"] = ids
        if limit is not None:
            options["limit"] = limit
        result = self.collection.get(**options)
        records = []
        for metadata in result.get("metadatas") or []:
            if not metadata or not metadata.get("record_json"):
                continue
            record = json.loads(metadata["record_json"])
            validate_paper_record(record)
            records.append(record)
        return records

    def count(self) -> int:
        """Return the number of records in the persistent collection."""
        return int(self.collection.count())

    def query_papers(
        self,
        query: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Find papers by semantic similarity and return records with distances."""
        if not query.strip():
            raise ValueError("Search query must not be empty.")
        count = self.collection.count()
        if count == 0:
            return []
        options: dict[str, Any] = {
            "query_texts": [query],
            "n_results": min(max(1, n_results), count),
            "include": ["metadatas", "distances"],
        }
        if where is not None:
            options["where"] = where
        result = self.collection.query(**options)
        matches: list[dict[str, Any]] = []
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        for metadata, distance in zip(metadatas, distances):
            if not metadata or not metadata.get("record_json"):
                continue
            record = json.loads(metadata["record_json"])
            validate_paper_record(record)
            matches.append({"record": record, "distance": distance})
        return matches
