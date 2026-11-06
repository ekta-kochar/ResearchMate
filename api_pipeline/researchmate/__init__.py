"""ResearchMate academic search utilities."""

from .api_01_pubmed import search_pubmed
from .api_02_arxiv import search_arxiv
from .api_03_crossref import search_crossref
from .api_04_europepmc import search_europepmc
from .api_05_openalex import search_openalex
from .queries_10 import DEFAULT_QUERIES
from .pipeline_20 import search_all_sources, run_query_batch
from .export_30 import (
    results_to_dataframe,
    save_results_csv,
    source_counts,
    query_source_comparison,
)
from .normalization import standardize_paper_record, standardize_paper_records
from .enrichment import recover_missing_abstracts
from .deduplication import deduplicate_paper_records
from .vector_store import ChromaPaperStore

__all__ = [
    "search_pubmed",
    "search_arxiv",
    "search_crossref",
    "search_europepmc",
    "search_openalex",
    "DEFAULT_QUERIES",
    "search_all_sources",
    "run_query_batch",
    "results_to_dataframe",
    "save_results_csv",
    "source_counts",
    "query_source_comparison",
    "standardize_paper_record",
    "standardize_paper_records",
    "recover_missing_abstracts",
    "deduplicate_paper_records",
    "ChromaPaperStore",
]
