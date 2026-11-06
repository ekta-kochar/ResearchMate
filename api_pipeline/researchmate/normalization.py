"""Cleanup and standardization helpers for ResearchMate paper records."""

from __future__ import annotations

import ast
import html
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote

from .schema import PAPER_FIELDS, validate_paper_record

_DOI_PREFIX = re.compile(r"^(?:doi\s*:\s*|https?://(?:dx\.)?doi\.org/)", re.IGNORECASE)
_YEAR = re.compile(r"\b(?:19|20|21)\d{2}\b")
_SPLIT_KEYWORDS = re.compile(r"\s*(?:;|\||\n)\s*")
_HTML_TAG = re.compile(r"<[^>]+>")


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = html.unescape(value)
    value = _HTML_TAG.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def _clean_doi(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    text = unquote(_DOI_PREFIX.sub("", text)).strip().rstrip(".,;)")
    return text.lower() if text else None


def _clean_year(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    match = _YEAR.search(text)
    return match.group(0) if match else None


def _keyword_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        # Some exports serialize a Python list into a CSV cell. Parse only
        # literal containers; never evaluate arbitrary input.
        if text.startswith(("[", "(")) and text.endswith(("]", ")")):
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, (list, tuple, set)):
                raw_values = list(parsed)
            else:
                raw_values = _SPLIT_KEYWORDS.split(text.strip("[]()"))
        else:
            raw_values = _SPLIT_KEYWORDS.split(text)
    else:
        raw_values = [value]

    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        text = _clean_text(raw)
        if text:
            text = text.strip(" \t\r\n\"'")
            key = text.casefold()
            if text and key not in seen:
                seen.add(key)
                cleaned.append(text)
    return cleaned


def standardize_paper_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return a cleaned, validated copy of a legacy or extended paper record."""
    if not isinstance(record, dict):
        raise TypeError("Paper record must be a dictionary.")
    missing = set(PAPER_FIELDS) - record.keys()
    if missing:
        raise ValueError(f"Missing paper fields: {', '.join(sorted(missing))}")
    paper = dict(record)
    paper["query"] = _clean_text(paper.get("query")) or ""
    paper["source"] = _clean_text(paper.get("source")) or ""

    for field in ("source_id", "title", "abstract", "url"):
        paper[field] = _clean_text(paper.get(field))
    author_values = paper.get("authors")
    if not isinstance(author_values, (list, tuple, set)):
        author_values = [author_values] if author_values is not None else []
    paper["authors"] = [
        text for author in author_values if (text := _clean_text(author))
    ]
    paper["keywords"] = _keyword_values(paper.get("keywords"))
    paper["doi"] = _clean_doi(paper.get("doi"))
    paper["year"] = _clean_year(paper.get("year"))

    raw_identifiers = paper.get("identifiers")
    identifiers = dict(raw_identifiers) if isinstance(raw_identifiers, dict) else {}
    identifiers = {
        str(key).strip().lower(): _clean_text(value)
        for key, value in identifiers.items()
        if _clean_text(value)
    }
    if paper["doi"]:
        identifiers["doi"] = paper["doi"]
    source = paper["source"].casefold().replace(" ", "")
    source_id = paper["source_id"]
    if source_id and source in {"pubmed", "europepmc"} and source_id.isdigit():
        identifiers.setdefault("pmid", source_id)
    elif source_id and source == "arxiv":
        identifiers.setdefault("arxiv", source_id.rsplit("/", 1)[-1])
    elif source_id and source == "openalex":
        identifiers.setdefault("openalex", source_id.rsplit("/", 1)[-1])
    paper["identifiers"] = identifiers

    canonical_id = _clean_text(paper.get("canonical_id"))
    if paper["doi"]:
        canonical_id = f"doi:{paper['doi']}"
    elif not canonical_id and source_id:
        canonical_id = f"{source}:{source_id.rsplit('/', 1)[-1]}"
    paper["canonical_id"] = canonical_id

    # Preserve supplied source evidence and append a traceable normalization
    # event for each field changed by this pass.
    provenance = {
        field: [dict(entry) for entry in entries]
        for field, entries in (paper.get("provenance") or {}).items()
    }
    for field, entries in provenance.items():
        cleaned_entries = []
        seen_standardization: set[tuple[str, str]] = set()
        for entry in entries:
            if entry.get("method") == "standardized":
                source_key = (entry.get("source", ""), entry.get("source_id") or "")
                if source_key in seen_standardization:
                    continue
                seen_standardization.add(source_key)
            cleaned_entries.append(entry)
        provenance[field] = cleaned_entries

    now = datetime.now(timezone.utc).isoformat()
    for field in ("query", "source_id", "title", "authors", "abstract", "keywords", "year", "doi", "url"):
        entries = provenance.setdefault(field, [])
        already_recorded = any(
            entry.get("method") == "standardized"
            and entry.get("source") == paper["source"]
            and entry.get("source_id") == paper["source_id"]
            for entry in entries
        )
        if not already_recorded:
            entries.append(
                {
                    "source": paper["source"],
                    "source_id": paper["source_id"],
                    "method": "standardized",
                    "retrieved_at": now,
                }
            )
    paper["provenance"] = provenance
    validate_paper_record(paper)
    return paper


def standardize_paper_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Standardize a collection of paper records without mutating inputs."""
    return [standardize_paper_record(record) for record in records]
