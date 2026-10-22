"""Crossref API client for ResearchMate."""

from __future__ import annotations

from typing import Any

import requests

CROSSREF_URL = "https://api.crossref.org/works"
USER_AGENT = "ResearchMate/1.0"


def search_crossref(query: str, max_results: int = 5, timeout: int = 30) -> list[dict[str, Any]]:
    """Search Crossref and return normalized paper dictionaries."""
    params = {
        "query": query,
        "rows": max_results,
    }
    headers = {"User-Agent": USER_AGENT}

    response = requests.get(
        CROSSREF_URL,
        params=params,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()

    items = response.json()["message"]["items"]
    results: list[dict[str, Any]] = []

    for item in items:
        titles = item.get("title", [])
        title = titles[0] if titles else None

        authors: list[str] = []
        for author in item.get("author", []):
            first = author.get("given")
            last = author.get("family")
            name = " ".join(part for part in (first, last) if part)
            if name:
                authors.append(name)

        abstract = item.get("abstract")
        doi = item.get("DOI")

        year = None
        date_parts = item.get("published-print", {}).get("date-parts", [])
        if not date_parts:
            date_parts = item.get("published-online", {}).get("date-parts", [])
        if date_parts and date_parts[0]:
            year = str(date_parts[0][0])

        results.append(
            {
                "query": query,
                "source": "Crossref",
                "source_id": doi,
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "keywords": item.get("subject", []),
                "year": year,
                "doi": doi,
                "url": item.get("URL"),
            }
        )

    return results
