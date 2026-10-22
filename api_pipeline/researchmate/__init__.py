"""ResearchMate academic search utilities."""

from .api_01_pubmed import search_pubmed
from .api_02_arxiv import search_arxiv
from .api_03_crossref import search_crossref
from .queries_10 import DEFAULT_QUERIES
from .pipeline_20 import search_all_sources, run_query_batch
from .export_30 import (
    results_to_dataframe,
    save_results_csv,
    source_counts,
    query_source_comparison,
)

__all__ = [
    "search_pubmed",
    "search_arxiv",
    "search_crossref",
    "DEFAULT_QUERIES",
    "search_all_sources",
    "run_query_batch",
    "results_to_dataframe",
    "save_results_csv",
    "source_counts",
    "query_source_comparison",
]
