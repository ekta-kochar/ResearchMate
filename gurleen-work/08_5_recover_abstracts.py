import csv
import json
import re
import importlib
from pathlib import Path
from difflib import SequenceMatcher

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "papers_normalized.json"
OUTPUT_JSON = BASE_DIR / "papers_recovered.json"
OUTPUT_CSV = BASE_DIR / "papers_recovered.csv"

# Use the API functions already present in your project.
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
    ("OpenAlex", openalex.search_openalex)
]


def clean_title(title):
    title = str(title or "").lower()
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def clean_doi(doi):
    doi = str(doi or "").strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi.strip()


def find_matching_paper(original, results):
    original_doi = clean_doi(original.get("doi"))
    original_title = clean_title(original.get("title"))

    # First preference: exact DOI match.
    if original_doi:
        for result in results:
            result_doi = clean_doi(result.get("doi"))

            if result_doi and result_doi == original_doi:
                return result

    # If DOI is unavailable or did not match, compare titles.
    for result in results:
        result_title = clean_title(result.get("title"))

        if not original_title or not result_title:
            continue

        if original_title == result_title:
            return result

        # Allow only very similar titles.
        score = SequenceMatcher(
            None, original_title, result_title
        ).ratio()

        if score >= 0.96:
            result_doi = clean_doi(result.get("doi"))

            # Do not match two different known DOIs.
            if original_doi and result_doi and original_doi != result_doi:
                continue

            return result

    return None


def main():
    if not INPUT_FILE.exists():
        print("papers_normalized.json was not found.")
        print("Run 08_normalize_papers.py first.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        papers = json.load(file)

    recovered_count = 0
    still_missing_count = 0

    for paper in papers:
        # Preserve any recovery information if the script is run again.
        if paper.get("abstract"):
            paper["abstract_status"] = "Already available"
            paper["abstract_source"] = paper.get("source", "")
            continue

        paper["abstract_status"] = "Not found yet"
        paper["abstract_source"] = ""

        original_source = str(paper.get("source") or "").strip().lower()
        title = paper.get("title", "")
        doi = paper.get("doi", "")

        # Without a title or DOI, recovery cannot be attempted reliably.
        if not title and not doi:
            still_missing_count += 1
            continue

        # Try other APIs, stopping when a matching abstract is found.
        for api_name, search_function in APIS:
            if api_name.lower() == original_source:
                continue

            # Prefer DOI as the search query when it is available.
            search_query = doi or title

            try:
                results = search_function(search_query, limit=5)
                match = find_matching_paper(paper, results)

                if match and str(match.get("abstract") or "").strip():
                    paper["abstract"] = str(
                        match["abstract"]
                    ).strip()

                    paper["abstract_status"] = "Recovered"
                    paper["abstract_source"] = api_name

                    recovered_count += 1

                    print("Abstract recovered:", title)
                    print("Found through:", api_name)
                    break

            except Exception as error:
                print("Search failed through", api_name, ":", error)

        if not paper.get("abstract"):
            paper["abstract_status"] = "Still missing"
            still_missing_count += 1

    # Save the complete dataset in JSON format.
    with open(OUTPUT_JSON, "w", encoding="utf-8") as file:
        json.dump(papers, file, indent=4, ensure_ascii=False)

    # Save the same dataset in CSV format.
    fields = list(papers[0].keys()) if papers else [
        "paper_id", "title", "authors", "abstract", "year",
        "doi", "url", "source", "abstract_status", "abstract_source"
    ]

    with open(
        OUTPUT_CSV, "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for paper in papers:
            row = paper.copy()

            if isinstance(row.get("authors"), list):
                row["authors"] = "; ".join(row["authors"])

            if isinstance(row.get("keywords"), list):
                row["keywords"] = "; ".join(row["keywords"])

            writer.writerow(row)

    print("\nABSTRACT RECOVERY COMPLETED")
    print("Total records:", len(papers))
    print("Abstracts recovered:", recovered_count)
    print("Still missing:", still_missing_count)
    print("Created:", OUTPUT_JSON.name)
    print("Created:", OUTPUT_CSV.name)


if __name__ == "__main__":
    main()