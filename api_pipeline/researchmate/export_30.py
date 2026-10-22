"""DataFrame and CSV helpers for normalized ResearchMate results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

COLUMNS = [
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
]


def results_to_dataframe(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert normalized result dictionaries to a consistent DataFrame."""
    return pd.DataFrame(results, columns=COLUMNS)


def save_results_csv(
    results: list[dict[str, Any]],
    output_path: str | Path = "researchmate_results.csv",
) -> Path:
    """Save normalized results to CSV and return the saved path."""
    output_path = Path(output_path)
    df = results_to_dataframe(results)
    df.to_csv(output_path, index=False)
    return output_path


def source_counts(df: pd.DataFrame) -> pd.Series:
    """Count records returned by each source."""
    return df["source"].value_counts()


def query_source_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """Create a query-by-source result-count comparison table."""
    return (
        df.groupby(["query", "source"])
        .size()
        .unstack(fill_value=0)
    )
