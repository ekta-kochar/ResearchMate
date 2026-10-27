
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
        value = record[field]
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
