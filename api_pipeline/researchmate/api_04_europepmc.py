"""Europe PMC REST API client for ResearchMate."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
USER_AGENT = "ResearchMate/1.0"


def _provenance(source_id: str | None, fields: tuple[str, ...]) -> dict[str, list[dict[str, str | None]]]:
    retrieved_at = datetime.now(timezone.utc).isoformat()
    entry = {
        "source": "Europe PMC",
        "source_id": source_id,
        "method": "source_record",
        "retrieved_at": retrieved_at,
    }
    return {field: [entry.copy()] for field in fields}


def parse_europepmc_record(item: dict[str, Any], query: str) -> dict[str, Any]:
    """Convert one Europe PMC search result into a ResearchMate record."""
    pmid = item.get("pmid")
    pmcid = item.get("pmcid")
    doi = item.get("doi")
    source_id = str(pmid or pmcid or doi) if (pmid or pmcid or doi) else None
    authors_raw = item.get("authorString") or ""
    authors = [author.strip() for author in authors_raw.split(",") if author.strip()]
    year = item.get("firstPublicationDate", "")[:4] or item.get("pubYear")
    identifiers = {
        key: str(value)
        for key, value in (("doi", doi), ("pmid", pmid), ("pmcid", pmcid))
        if value
    }
    url = f"https://europepmc.org/article/MED/{pmid}" if pmid else (
        f"https://europepmc.org/articles/{pmcid}" if pmcid else None
    )
    fields = tuple(
        field
        for field, value in (
            ("title", item.get("title")),
            ("authors", authors),
            ("abstract", item.get("abstractText")),
            ("year", year),
            ("doi", doi),
            ("url", url),
        )
        if value
    )

    return {
        "query": query,
        "source": "Europe PMC",
        "source_id": source_id,
        "title": item.get("title"),
        "authors": authors,
        "abstract": item.get("abstractText") or None,
        "keywords": [],
        "year": str(year) if year else None,
        "doi": doi,
        "url": url,
        "canonical_id": f"doi:{doi.lower()}" if doi else (
            f"pmid:{pmid}" if pmid else (f"pmcid:{pmcid}" if pmcid else None)
        ),
        "identifiers": identifiers,
        "provenance": _provenance(source_id, fields),
    }


def search_europepmc(
    query: str, max_results: int = 5, timeout: int = 30
) -> list[dict[str, Any]]:
    """Search Europe PMC and return normalized ResearchMate records."""
    response = requests.get(
        EUROPE_PMC_URL,
        params={"query": query, "format": "json", "pageSize": max_results},
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    results = response.json().get("resultList", {}).get("result", [])
    return [parse_europepmc_record(item, query) for item in results]
