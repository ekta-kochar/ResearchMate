"""Hybrid ranking for paper records retrieved from ChromaDB."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

SEMANTIC_WEIGHT = 0.70
KEYWORD_WEIGHT = 0.20
RECENCY_WEIGHT = 0.10
RECENCY_WINDOW_YEARS = 10

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "based", "by", "for", "from",
    "how", "in", "is", "of", "on", "or", "paper", "papers", "research",
    "study", "the", "this", "to", "using", "what", "which", "with",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.casefold())
        if len(token) > 1 and token not in _STOPWORDS
    }


def _keyword_score(query: str, record: dict[str, Any]) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    paper_text = " ".join(
        [
            str(record.get("title") or ""),
            str(record.get("abstract") or ""),
            " ".join(record.get("keywords") or []),
        ]
    )
    return len(query_tokens & _tokens(paper_text)) / len(query_tokens)


def _recency_score(record: dict[str, Any], current_year: int) -> float:
    try:
        year = int(str(record.get("year") or "").strip()[:4])
    except (TypeError, ValueError):
        return 0.0
    if year < 1 or year > current_year:
        return 0.0
    return max(0.0, min(1.0, 1 - (current_year - year) / RECENCY_WINDOW_YEARS))


def rank_search_results(
    matches: list[dict[str, Any]],
    query: str,
    top_n: int | None = None,
    current_year: int | None = None,
) -> list[dict[str, Any]]:
    """Add 70/20/10 semantic, keyword, and recency scores to Chroma matches.

    Chroma's cosine distance is converted to a 0–1 similarity with
    ``1 - distance``. Scores are returned with the original match and record.
    """
    year_now = current_year or datetime.now().year
    ranked: list[dict[str, Any]] = []
    for match in matches:
        record = match["record"]
        distance = float(match.get("distance", 1.0))
        semantic = max(0.0, min(1.0, 1.0 - distance))
        keyword = _keyword_score(query, record)
        recency = _recency_score(record, year_now)
        score = (
            SEMANTIC_WEIGHT * semantic
            + KEYWORD_WEIGHT * keyword
            + RECENCY_WEIGHT * recency
        )
        ranked.append(
            {
                **match,
                "semantic_score": semantic,
                "keyword_score": keyword,
                "recency_score": recency,
                "final_score": score,
            }
        )
    ranked.sort(
        key=lambda item: (
            item["final_score"],
            item["semantic_score"],
            str(item["record"].get("title") or "").casefold(),
        ),
        reverse=True,
    )
    for rank, match in enumerate(ranked, start=1):
        match["rank"] = rank
    return ranked[:top_n] if top_n is not None else ranked
