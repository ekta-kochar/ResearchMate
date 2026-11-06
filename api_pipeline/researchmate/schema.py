
"""Shared paper schema and validation for ResearchMate."""

from typing import Any

PAPER_FIELDS = (
    "query",
    "source",
    "source_id",
    "title",
    "authors",
    "abstract",
    "keywords",
    "year",
    "doi",
    "url",
)

# Optional extensions keep records produced by existing API adapters valid
# while allowing later pipeline stages to retain identity and provenance.
EXTENDED_PAPER_FIELDS = (
    "canonical_id",
    "identifiers",
    "provenance",
    "metadata_conflicts",
)

PROVENANCE_ENTRY_FIELDS = frozenset(
    {"source", "source_id", "method", "retrieved_at"}
)

# These fields must contain non-empty strings.
REQUIRED_TEXT_FIELDS = ("query", "source")

# These fields may be absent or None when a database lacks metadata.
OPTIONAL_TEXT_FIELDS = (
    "source_id",
    "title",
    "abstract",
    "year",
    "doi",
    "url",
    "canonical_id",
)


def validate_paper_record(record: dict[str, Any]) -> None:
    """Validate a paper record against the shared ResearchMate schema.

    Raises:
        TypeError: If a field has an invalid data type.
        ValueError: If required fields are missing or invalid.
    """
    if not isinstance(record, dict):
        raise TypeError("Paper record must be a dictionary.")

    missing = set(PAPER_FIELDS) - record.keys()
    if missing:
        raise ValueError(
            f"Missing paper fields: {', '.join(sorted(missing))}"
        )

    for field in REQUIRED_TEXT_FIELDS:
        value = record[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"'{field}' must be a non-empty string."
            )

    for field in OPTIONAL_TEXT_FIELDS:
        value = record.get(field)
        if value is not None and not isinstance(value, str):
            raise TypeError(
                f"'{field}' must be a string or None."
            )

    for field in ("authors", "keywords"):
        value = record[field]

        if not isinstance(value, list):
            raise TypeError(f"'{field}' must be a list.")

        if not all(isinstance(item, str) for item in value):
            raise TypeError(
                f"Every item in '{field}' must be a string."
            )

    identifiers = record.get("identifiers")
    if identifiers is not None:
        if not isinstance(identifiers, dict):
            raise TypeError("'identifiers' must be a dictionary or None.")
        for key, value in identifiers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise TypeError("Identifier names and values must be strings.")
            if not key.strip() or not value.strip():
                raise ValueError("Identifier names and values must be non-empty.")

    provenance = record.get("provenance")
    if provenance is not None:
        if not isinstance(provenance, dict):
            raise TypeError("'provenance' must be a dictionary or None.")
        for field, entries in provenance.items():
            if not isinstance(field, str) or not field.strip():
                raise ValueError("Provenance field names must be non-empty strings.")
            if not isinstance(entries, list):
                raise TypeError("Each provenance value must be a list of entries.")
            for entry in entries:
                if not isinstance(entry, dict):
                    raise TypeError("Each provenance entry must be a dictionary.")
                if set(entry) - PROVENANCE_ENTRY_FIELDS:
                    raise ValueError("Provenance entry contains unsupported fields.")
                for required in ("source", "method"):
                    value = entry.get(required)
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError(
                            f"Provenance entry '{required}' must be a non-empty string."
                        )
                for optional in ("source_id", "retrieved_at"):
                    value = entry.get(optional)
                    if value is not None and not isinstance(value, str):
                        raise TypeError(
                            f"Provenance entry '{optional}' must be a string or None."
                        )

    conflicts = record.get("metadata_conflicts")
    if conflicts is not None:
        if not isinstance(conflicts, list):
            raise TypeError("'metadata_conflicts' must be a list or None.")
        for conflict in conflicts:
            if not isinstance(conflict, dict):
                raise TypeError("Each metadata conflict must be a dictionary.")
            if set(conflict) - {"field", "value", "source", "source_id"}:
                raise ValueError("Metadata conflict contains unsupported fields.")
            for required in ("field", "source"):
                value = conflict.get(required)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"Metadata conflict '{required}' must be a non-empty string."
                    )
