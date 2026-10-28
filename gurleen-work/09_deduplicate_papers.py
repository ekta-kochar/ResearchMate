import json
import csv
import re
from difflib import SequenceMatcher
from pathlib import Path

INPUT_FILE = "papers_recovered.json"
JSON_OUTPUT = "papers_deduplicated.json"
CSV_OUTPUT = "papers_deduplicated.csv"
REPORT_JSON = "deduplication_report.json"
REPORT_CSV = "deduplication_report.csv"

FIELDS = [
    "paper_id", "title", "authors", "abstract", "keywords",
    "year", "doi", "url", "source", "journal",
    "publication_type", "query_id", "search_query",
    "sources_seen", "duplicate_count"
]


def normalize_title(title):
    title = str(title or "").lower()
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def similarity(title1, title2):
    return SequenceMatcher(
        None, normalize_title(title1), normalize_title(title2)
    ).ratio()


def merge_papers(old, new):
    for field, value in new.items():
        old_value = old.get(field)

        if old_value in (None, "", []):
            if value not in (None, "", []):
                old[field] = value

        elif field in ("authors", "keywords"):
            if isinstance(old_value, list) and isinstance(value, list):
                for item in value:
                    if item not in old_value:
                        old_value.append(item)

    sources = old.get("sources_seen", [])

    if not isinstance(sources, list):
        sources = [sources] if sources else []

    for source in [old.get("source", ""), new.get("source", "")]:
        if source and source not in sources:
            sources.append(source)

    old["sources_seen"] = sources
    old["duplicate_count"] = old.get("duplicate_count", 1) + 1

    return old


def main():
    if not Path(INPUT_FILE).exists():
        print("File not found:", INPUT_FILE)
        print("Run 08_normalize_papers.py first.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        papers = json.load(file)

    unique_papers = []
    report = []

    for paper in papers:
        doi = str(paper.get("doi") or "").strip().lower()
        title = normalize_title(paper.get("title", ""))

        match_index = None
        reason = ""
        score = ""

        # First, compare DOI values.
        if doi:
            for index, old in enumerate(unique_papers):
                old_doi = str(old.get("doi") or "").strip().lower()

                if old_doi and doi == old_doi:
                    match_index = index
                    reason = "Same DOI"
                    score = 1.0
                    break

        # If DOI did not find a match, compare titles.
        if match_index is None and title:
            for index, old in enumerate(unique_papers):
                old_title = normalize_title(old.get("title", ""))
                old_doi = str(old.get("doi") or "").strip().lower()

                # Do not merge different known DOIs just because titles match.
                if doi and old_doi and doi != old_doi:
                    continue

                if title == old_title:
                    match_index = index
                    reason = "Same normalized title"
                    score = 1.0
                    break

                # Fuzzy title matching only when a DOI is missing.
                if not doi or not old_doi:
                    current_score = similarity(title, old_title)

                    if current_score >= 0.96:
                        match_index = index
                        reason = "Similar title - manual review needed"
                        score = round(current_score, 3)
                        break

        if match_index is None:
            paper["sources_seen"] = (
                [paper["source"]] if paper.get("source") else []
            )
            paper["duplicate_count"] = 1
            unique_papers.append(paper)

        else:
            old = unique_papers[match_index]

            report.append({
                "duplicate_title": paper.get("title", ""),
                "kept_title": old.get("title", ""),
                "duplicate_doi": paper.get("doi", ""),
                "kept_doi": old.get("doi", ""),
                "reason": reason,
                "similarity": score
            })

            unique_papers[match_index] = merge_papers(old, paper)

    # Save the deduplicated JSON dataset.
    with open(JSON_OUTPUT, "w", encoding="utf-8") as file:
        json.dump(unique_papers, file, indent=4, ensure_ascii=False)

    # Save the deduplicated CSV dataset.
    with open(CSV_OUTPUT, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()

        for paper in unique_papers:
            row = paper.copy()
            row["authors"] = "; ".join(row.get("authors", []))
            row["keywords"] = "; ".join(row.get("keywords", []))
            row["sources_seen"] = "; ".join(row.get("sources_seen", []))
            writer.writerow(row)

    # Save duplicate report in both formats.
    with open(REPORT_JSON, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4, ensure_ascii=False)

    report_fields = [
        "duplicate_title", "kept_title", "duplicate_doi",
        "kept_doi", "reason", "similarity"
    ]

    with open(REPORT_CSV, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=report_fields)
        writer.writeheader()
        writer.writerows(report)

    print("\nTASK 5 COMPLETED")
    print("Records before:", len(papers))
    print("Records after:", len(unique_papers))
    print("Duplicates merged:", len(report))
    print("Created:", JSON_OUTPUT)
    print("Created:", CSV_OUTPUT)
    print("Created:", REPORT_JSON)
    print("Created:", REPORT_CSV)


if __name__ == "__main__":
    main()