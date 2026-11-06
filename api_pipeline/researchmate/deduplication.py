"""Conservative duplicate detection and metadata-preserving merges."""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any

from .normalization import standardize_paper_record
from .schema import validate_paper_record


def _key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()


def _same_paper(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_doi, right_doi = left.get("doi"), right.get("doi")
    if left_doi and right_doi:
        return left_doi.casefold() == right_doi.casefold()

    left_ids = left.get("identifiers") or {}
    right_ids = right.get("identifiers") or {}
    shared_keys = set(left_ids) & set(right_ids)
    if any(left_ids[key] and left_ids[key] == right_ids[key] for key in shared_keys):
        return True
    if any(left_ids[key] and right_ids[key] and left_ids[key] != right_ids[key] for key in shared_keys):
        return False

    if not left.get("year") or not right.get("year") or left["year"] != right["year"]:
        return False
    if _key(left.get("title")) != _key(right.get("title")):
        return False
    left_authors = left.get("authors") or []
    right_authors = right.get("authors") or []
    if not left_authors or not right_authors:
        return False
    return _key(left_authors[0]) == _key(right_authors[0])


def _merge_unique_strings(first: list[str], second: list[str]) -> list[str]:
    result = list(first)
    seen = {_key(value) for value in first}
    for value in second:
        normalized = _key(value)
        if normalized and normalized not in seen:
            result.append(value)
            seen.add(normalized)
    return result


def _merge_records(primary: dict[str, Any], secondary: dict[str, Any]) -> None:
    """Merge secondary into primary in place, retaining conflicting values."""
    primary.setdefault("metadata_conflicts", [])
    primary["metadata_conflicts"].extend(secondary.get("metadata_conflicts", []))

    for field in ("authors", "keywords"):
        primary[field] = _merge_unique_strings(primary.get(field, []), secondary.get(field, []))

    primary.setdefault("identifiers", {}).update(secondary.get("identifiers") or {})
    primary.setdefault("provenance", {})
    for field, entries in (secondary.get("provenance") or {}).items():
        current = primary["provenance"].setdefault(field, [])
        for entry in entries:
            if entry not in current:
                current.append(dict(entry))

    for field in ("title", "abstract", "year", "doi", "url"):
        current, incoming = primary.get(field), secondary.get(field)
        if not current and incoming:
            primary[field] = incoming
        elif current and incoming and _key(str(current)) != _key(str(incoming)):
            primary["metadata_conflicts"].append(
                {
                    "field": field,
                    "value": incoming,
                    "source": secondary["source"],
                    "source_id": secondary.get("source_id"),
                }
            )

    if primary.get("doi"):
        primary["canonical_id"] = f"doi:{primary['doi']}"
    elif not primary.get("canonical_id"):
        primary["canonical_id"] = secondary.get("canonical_id")


def deduplicate_paper_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return unique records, merging only high-confidence duplicates.

    DOI or a matching provider identifier establishes identity. Without those,
    title, year, and first author must all agree exactly after normalization.
    """
    unique: list[dict[str, Any]] = []
    for raw_record in records:
        record = standardize_paper_record(raw_record)
        duplicate = next((existing for existing in unique if _same_paper(existing, record)), None)
        if duplicate is None:
            unique.append(record)
        else:
            _merge_records(duplicate, record)
            validate_paper_record(duplicate)
    return unique
