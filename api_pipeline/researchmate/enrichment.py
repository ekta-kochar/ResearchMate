"""Conservative metadata enrichment for ResearchMate paper records."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from difflib import SequenceMatcher
from datetime import datetime, timezone
import re
from typing import Any

from .normalization import standardize_paper_record
from .schema import validate_paper_record

RecordSearcher = Callable[..., list[dict[str, Any]]]

ABSTRACT_SEARCH_ORDER = ("europepmc", "crossref", "openalex", "pubmed")
TITLE_MATCH_THRESHOLD = 0.97


def _title_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()


def _has_exact_identifier(
    original: dict[str, Any], candidate: dict[str, Any]
) -> bool:
    original_ids = {str(k).casefold(): str(v).casefold() for k, v in (original.get("identifiers") or {}).items()}
    candidate_ids = {str(k).casefold(): str(v).casefold() for k, v in (candidate.get("identifiers") or {}).items()}
    for key in set(original_ids) & set(candidate_ids):
        if original_ids[key] and original_ids[key] == candidate_ids[key]:
            return True
    original_doi = original.get("doi")
    candidate_doi = candidate.get("doi")
    return bool(original_doi and candidate_doi and original_doi.casefold() == candidate_doi.casefold())


def _title_match(original: dict[str, Any], candidate: dict[str, Any]) -> bool:
    left = _title_key(original.get("title"))
    right = _title_key(candidate.get("title"))
    if not left or not right or SequenceMatcher(None, left, right).ratio() < TITLE_MATCH_THRESHOLD:
        return False
    left_year, right_year = original.get("year"), candidate.get("year")
    return not (left_year and right_year and left_year != right_year)


def _find_abstract_match(
    paper: dict[str, Any], searchers: dict[str, RecordSearcher]
) -> tuple[dict[str, Any], str] | None:
    for source in ABSTRACT_SEARCH_ORDER:
        searcher = searchers.get(source)
        if searcher is None or source == paper.get("source", "").casefold().replace(" ", ""):
            continue

        # Identifier queries are preferred and only accepted after exact
        # identifier equality is verified against the returned record.
        identifiers = paper.get("identifiers") or {}
        exact_queries: list[str] = []
        if paper.get("doi"):
            exact_queries.append(f'DOI:"{paper["doi"]}"')
        exact_queries.extend(str(value) for value in identifiers.values() if value)
        for query in dict.fromkeys(exact_queries):
            try:
                candidates = searcher(query=query, max_results=5)
            except Exception:
                continue
            for raw_candidate in candidates:
                try:
                    candidate = standardize_paper_record(raw_candidate)
                except (TypeError, ValueError):
                    continue
                if candidate.get("abstract") and _has_exact_identifier(paper, candidate):
                    return candidate, "exact_identifier"

        title = paper.get("title")
        if not title:
            continue
        try:
            candidates = searcher(query=f'"{title}"', max_results=5)
        except Exception:
            continue
        for raw_candidate in candidates:
            try:
                candidate = standardize_paper_record(raw_candidate)
            except (TypeError, ValueError):
                continue
            if candidate.get("abstract") and _title_match(paper, candidate):
                return candidate, "title_year_exact" if paper.get("year") else "title_exact"
    return None


def recover_missing_abstracts(
    records: Iterable[dict[str, Any]],
    searchers: dict[str, RecordSearcher] | None = None,
) -> list[dict[str, Any]]:
    """Fill missing abstracts only when identifier or strict title matching succeeds.

    ``searchers`` is injectable for offline use and tests. It maps source keys
    to functions accepting ``query`` and ``max_results`` keyword arguments.
    """
    if searchers is None:
        from .pipeline_20 import SEARCHERS

        searchers = SEARCHERS

    enriched: list[dict[str, Any]] = []
    for raw_paper in records:
        paper = standardize_paper_record(raw_paper)
        if paper.get("abstract"):
            enriched.append(paper)
            continue

        match = _find_abstract_match(paper, searchers)
        if match is None:
            enriched.append(paper)
            continue

        candidate, method = match
        paper["abstract"] = candidate["abstract"]
        paper.setdefault("provenance", {}).setdefault("abstract", []).append(
            {
                "source": candidate["source"],
                "source_id": candidate.get("source_id"),
                "method": method,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        validate_paper_record(paper)
        enriched.append(paper)
    return enriched
