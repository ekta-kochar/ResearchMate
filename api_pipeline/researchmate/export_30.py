"""DataFrame and CSV helpers for normalized ResearchMate results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[reportMissingModuleSource]

from .schema import PAPER_FIELDS, validate_paper_record

# Preserve the existing public constant while using the shared schema.
COLUMNS = list(PAPER_FIELDS)


def results_to_dataframe(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Validate records and convert them to a consistent DataFrame."""
    for index, record in enumerate(results):
        try:
            validate_paper_record(record)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid paper record at index {index}: {exc}"
            ) from exc

    return pd.DataFrame(results, columns=COLUMNS)


def save_results_csv(
    results: list[dict[str, Any]],
    output_path: str | Path = "researchmate_results.csv",
) -> Path:
    """Validate and save normalized results to CSV."""
    output_path = Path(output_path)
    df = results_to_dataframe(results)
    df.to_csv(output_path, index=False)
    return output_path


def source_counts(df: pd.DataFrame) -> pd.Series:
    """Count records returned by each source."""
    return df["source"].value_counts()


def query_source_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """Create a query-by-source result-count comparison table."""
    return df.groupby(["query", "source"]).size().unstack(fill_value=0)
