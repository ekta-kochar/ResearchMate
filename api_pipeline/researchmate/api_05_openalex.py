"""OpenAlex Works API client for ResearchMate."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

OPENALEX_URL = "https://api.openalex.org/works"
USER_AGENT = "ResearchMate/1.0"


def _abstract_from_index(inverted_index: dict[str, list[int]] | None) -> str | None:
    """Reconstruct OpenAlex's abstract inverted index in token order."""
    if not inverted_index:
        return None
    positions: dict[int, str] = {}
    for token, indexes in inverted_index.items():
        if isinstance(token, str) and isinstance(indexes, list):
            for index in indexes:
                if isinstance(index, int) and index >= 0:
                    positions[index] = token
    if not positions:
        return None
    return " ".join(positions[index] for index in sorted(positions))


def parse_openalex_work(item: dict[str, Any], query: str) -> dict[str, Any]:
    """Convert one OpenAlex work into a ResearchMate record."""
    openalex_id = item.get("id")
    source_id = openalex_id.rsplit("/", 1)[-1] if isinstance(openalex_id, str) else None
    doi = item.get("doi")
    if isinstance(doi, str) and doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    authors = [
        authorship.get("author", {}).get("display_name")
        for authorship in item.get("authorships", [])
        if isinstance(authorship, dict)
        and isinstance(authorship.get("author"), dict)
        and authorship["author"].get("display_name")
    ]
    keywords = [
        keyword.get("display_name")
        for keyword in item.get("keywords", [])
        if isinstance(keyword, dict) and keyword.get("display_name")
    ]
    year = item.get("publication_year")
    identifiers = {"openalex": source_id} if source_id else {}
    if doi:
        identifiers["doi"] = str(doi)
    abstract = _abstract_from_index(item.get("abstract_inverted_index"))
    url = (item.get("primary_location") or {}).get("landing_page_url") or openalex_id
    fields = tuple(
        field
        for field, value in (
            ("title", item.get("title")),
            ("authors", authors),
            ("abstract", abstract),
            ("keywords", keywords),
            ("year", year),
            ("doi", doi),
            ("url", url),
        )
        if value
    )
    retrieved_at = datetime.now(timezone.utc).isoformat()
    provenance_entry = {
        "source": "OpenAlex",
        "source_id": source_id,
        "method": "source_record",
        "retrieved_at": retrieved_at,
    }

    return {
        "query": query,
        "source": "OpenAlex",
        "source_id": source_id,
        "title": item.get("title"),
        "authors": authors,
        "abstract": abstract,
        "keywords": keywords,
        "year": str(year) if year is not None else None,
        "doi": doi,
        "url": url,
        "canonical_id": f"doi:{doi.lower()}" if doi else (
            f"openalex:{source_id}" if source_id else None
        ),
        "identifiers": identifiers,
        "provenance": {field: [provenance_entry.copy()] for field in fields},
    }


def search_openalex(
    query: str, max_results: int = 5, timeout: int = 30
) -> list[dict[str, Any]]:
    """Search OpenAlex Works and return normalized ResearchMate records."""
    response = requests.get(
        OPENALEX_URL,
        params={"search": query, "per-page": max_results},
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    return [parse_openalex_work(item, query) for item in results]
