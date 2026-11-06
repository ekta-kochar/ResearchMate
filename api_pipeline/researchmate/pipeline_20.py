"""Multi-source search orchestration for ResearchMate."""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Callable, Any

from .api_01_pubmed import search_pubmed
from .api_02_arxiv import search_arxiv
from .api_03_crossref import search_crossref
from .api_04_europepmc import search_europepmc
from .api_05_openalex import search_openalex
from .normalization import standardize_paper_records
from .enrichment import recover_missing_abstracts
from .deduplication import deduplicate_paper_records

SEARCHERS: dict[str, Callable[..., list[dict[str, Any]]]] = {
    "pubmed": search_pubmed,
    "arxiv": search_arxiv,
    "crossref": search_crossref,
    "europepmc": search_europepmc,
    "openalex": search_openalex,
}


def search_all_sources(
    query: str,
    max_results: int = 5,
    sources: Iterable[str] = ("pubmed", "arxiv", "crossref", "europepmc", "openalex"),
) -> list[dict[str, Any]]:
    """Run one query across selected APIs and combine normalized results."""
    all_results: list[dict[str, Any]] = []

    for source in sources:
        source_key = source.lower()
        if source_key not in SEARCHERS:
            raise ValueError(
                f"Unknown source '{source}'. Available: {', '.join(SEARCHERS)}"
            )

        try:
            results = SEARCHERS[source_key](query=query, max_results=max_results)
            results = standardize_paper_records(results)
            all_results.extend(results)
            print(f"{source_key}: {len(results)} results")
        except Exception as exc:
            print(f"{source_key} failed: {exc}")

    enriched_results = recover_missing_abstracts(all_results)
    return deduplicate_paper_records(enriched_results)


def run_query_batch(
    queries: Iterable[str],
    max_results: int = 5,
    sources: Iterable[str] = ("pubmed", "arxiv", "crossref", "europepmc", "openalex"),
    delay_between_queries: int = 5,
) -> list[dict[str, Any]]:
    """Run many queries across selected APIs.

    A pause is included between queries to reduce the chance of rate limiting.
    """
    query_list = list(queries)
    all_results: list[dict[str, Any]] = []

    for index, query in enumerate(query_list, start=1):
        print(f"\nQuery {index}/{len(query_list)}: {query}")
        results = search_all_sources(
            query=query,
            max_results=max_results,
            sources=sources,
        )
        all_results.extend(results)

        if index < len(query_list):
            time.sleep(delay_between_queries)

    return all_results
