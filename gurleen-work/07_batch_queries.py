import csv
import json
import importlib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

QUERIES_FILE = BASE_DIR / "queries.csv"
OUTPUT_JSON = BASE_DIR / "papers_all_queries.json"
OUTPUT_CSV = BASE_DIR / "api_comparison.csv"

# Import the five academic API modules
crossref = importlib.import_module("02_crossref_api")
arxiv = importlib.import_module("03_arxiv_api")
pubmed = importlib.import_module("04_pubmed_api")
europepmc = importlib.import_module("05_europepmc_api")
openalex = importlib.import_module("06_openalex_api")

APIS = [
    ("Crossref", crossref.search_crossref),
    ("arXiv", arxiv.search_arxiv),
    ("PubMed", pubmed.search_pubmed),
    ("Europe PMC", europepmc.search_europepmc),
    ("OpenAlex", openalex.search_openalex),
]


def read_queries():
    with open(
        QUERIES_FILE, "r", encoding="utf-8-sig", newline=""
    ) as file:
        return list(csv.DictReader(file))


def main():
    queries = read_queries()

    all_papers = []
    comparison_results = []

    for query_item in queries:
        query_id = query_item["query_id"]
        query = query_item["query"]

        print("\nSearching for:", query)
        print("Query ID:", query_id)

        for api_name, search_function in APIS:
            try:
                papers = search_function(query, limit=5)

                for paper in papers:
                    paper["query_id"] = query_id
                    paper["search_query"] = query
                    paper["api_used"] = api_name

                all_papers.extend(papers)

                doi_count = sum(
                    1 for paper in papers if paper.get("doi")
                )
                abstract_count = sum(
                    1 for paper in papers if paper.get("abstract")
                )

                comparison_results.append({
                    "query_id": query_id,
                    "query": query,
                    "api": api_name,
                    "status": "Success",
                    "papers_found": len(papers),
                    "papers_with_doi": doi_count,
                    "papers_with_abstract": abstract_count,
                    "error": "",
                })

                print(
                    api_name,
                    "- Papers:", len(papers),
                    "| DOI:", doi_count,
                    "| Abstracts:", abstract_count,
                )

            except Exception as error:
                comparison_results.append({
                    "query_id": query_id,
                    "query": query,
                    "api": api_name,
                    "status": "Failed",
                    "papers_found": 0,
                    "papers_with_doi": 0,
                    "papers_with_abstract": 0,
                    "error": str(error),
                })

                print(api_name, "- Error:", error)

    # Save all retrieved paper records
    with open(OUTPUT_JSON, "w", encoding="utf-8") as file:
        json.dump(all_papers, file, indent=4, ensure_ascii=False)

    # Save API comparison results
    comparison_fields = [
        "query_id",
        "query",
        "api",
        "status",
        "papers_found",
        "papers_with_doi",
        "papers_with_abstract",
        "error",
    ]

    with open(
        OUTPUT_CSV, "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=comparison_fields
        )
        writer.writeheader()
        writer.writerows(comparison_results)

    print("\nBATCH SEARCH COMPLETED")
    print("Queries processed:", len(queries))
    print("API comparisons:", len(comparison_results))
    print("Paper records:", len(all_papers))
    print("Records with DOI:", sum(
        1 for paper in all_papers if paper.get("doi")
    ))
    print("Records with abstract:", sum(
        1 for paper in all_papers if paper.get("abstract")
    ))
    print("Created:", OUTPUT_JSON.name)
    print("Created:", OUTPUT_CSV.name)


if __name__ == "__main__":
    main()