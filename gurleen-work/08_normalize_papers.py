import json
import csv
import re
from pathlib import Path

INPUT_FILE = "papers_all_queries.json"
JSON_OUTPUT = "papers_normalized.json"
CSV_OUTPUT = "papers_normalized.csv"

FIELDS = [
    "paper_id", "title", "authors", "abstract", "keywords",
    "year", "doi", "url", "source", "journal",
    "publication_type", "query_id", "search_query"
]


def get_value(record, names):
    for name in names:
        value = record.get(name)
        if value not in (None, "", [], {}):
            return value
    return ""


def clean_text(value):
    if value is None:
        return ""

    if isinstance(value, list):
        value = " ".join(str(item) for item in value)

    if isinstance(value, dict):
        return ""

    value = re.sub(r"<[^>]+>", " ", str(value))
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def clean_authors(value):
    if not value:
        return []

    if isinstance(value, str):
        return [name.strip() for name in value.split(";") if name.strip()]

    if not isinstance(value, list):
        value = [value]

    authors = []

    for author in value:
        if isinstance(author, str):
            name = author.strip()

        elif isinstance(author, dict):
            name = (
                author.get("name")
                or author.get("display_name")
                or author.get("author_name")
                or ""
            )

            if not name:
                given = author.get("given", "")
                family = author.get("family", "")
                name = (given + " " + family).strip()

            if not name and isinstance(author.get("author"), dict):
                name = author["author"].get("display_name", "")

        else:
            name = ""

        if name and name not in authors:
            authors.append(name)

    return authors


def clean_year(value):
    if isinstance(value, dict):
        date_parts = value.get("date-parts", [])
        if date_parts and date_parts[0]:
            value = date_parts[0][0]
        else:
            return ""

    match = re.search(r"\b(19\d{2}|20\d{2}|2100)\b", str(value))

    if match:
        return int(match.group(1))

    return ""


def clean_doi(value):
    doi = str(value or "").strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi.strip()


def clean_keywords(value):
    if not value:
        return []

    if isinstance(value, str):
        value = re.split(r";|,", value)

    if not isinstance(value, list):
        value = [value]

    keywords = []

    for item in value:
        if isinstance(item, str):
            keyword = item.strip()
        elif isinstance(item, dict):
            keyword = (
                item.get("display_name")
                or item.get("name")
                or item.get("term")
                or ""
            )
        else:
            keyword = ""

        if keyword and keyword not in keywords:
            keywords.append(keyword)

    return keywords


def rebuild_abstract(index):
    if not isinstance(index, dict):
        return ""

    words = []

    for word, positions in index.items():
        for position in positions:
            words.append((position, word))

    words.sort(key=lambda item: item[0])
    return " ".join(word for position, word in words)


def find_records(data):
    records = []

    def visit(item):
        if isinstance(item, list):
            for child in item:
                visit(child)

        elif isinstance(item, dict):
            title = get_value(
                item, ["title", "paper_title", "display_name", "ArticleTitle"]
            )

            if title:
                records.append(item)
            else:
                for child in item.values():
                    if isinstance(child, (dict, list)):
                        visit(child)

    visit(data)
    return records


def normalize_paper(record, number):
    title = clean_text(
        get_value(record, ["title", "paper_title", "display_name", "ArticleTitle"])
    )

    abstract_value = get_value(
        record, ["abstract", "summary", "abstractText", "AbstractText", "description"]
    )

    if not abstract_value:
        abstract_value = rebuild_abstract(
            record.get("abstract_inverted_index", {})
        )

    authors = clean_authors(
        get_value(
            record,
            ["authors", "author", "authorString", "author_string", "authorships"]
        )
    )

    year = clean_year(
        get_value(
            record,
            [
                "year", "publication_year", "published", "published_date",
                "publication_date", "firstPublicationDate", "pubdate",
                "publicationDate"
            ]
        )
    )

    doi = clean_doi(get_value(record, ["doi", "DOI", "DOI_URL"]))

    url = clean_text(get_value(record, ["url", "URL", "link"]))

    if not url and doi:
        url = "https://doi.org/" + doi

    journal = get_value(
        record, ["journal", "journalTitle", "container-title"]
    )

    if isinstance(journal, list):
        journal = journal[0] if journal else ""

    return {
        "paper_id": clean_text(
            get_value(record, ["paper_id", "pmid", "arxiv_id"])
        ) or "paper_" + str(number),
        "title": title,
        "authors": authors,
        "abstract": clean_text(abstract_value),
        "keywords": clean_keywords(
            get_value(record, ["keywords", "keyword", "mesh_terms", "subject", "concepts"])
        ),
        "year": year,
        "doi": doi,
        "url": url,
        "source": clean_text(get_value(record, ["source", "api", "database"])),
        "journal": clean_text(journal),
        "publication_type": clean_text(
            get_value(record, ["publication_type", "type", "document_type"])
        ),
        "query_id": clean_text(get_value(record, ["query_id"])),
        "search_query": clean_text(get_value(record, ["search_query", "query"]))
    }


def main():
    if not Path(INPUT_FILE).exists():
        print("File not found:", INPUT_FILE)
        print("Run 07_batch_queries.py first, or check your project folder.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    raw_records = find_records(data)
    papers = []

    for number, record in enumerate(raw_records, start=1):
        paper = normalize_paper(record, number)

        if paper["title"]:
            papers.append(paper)

    with open(JSON_OUTPUT, "w", encoding="utf-8") as file:
        json.dump(papers, file, indent=4, ensure_ascii=False)

    with open(CSV_OUTPUT, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()

        for paper in papers:
            row = paper.copy()
            row["authors"] = "; ".join(row["authors"])
            row["keywords"] = "; ".join(row["keywords"])
            writer.writerow(row)

    print("\nTASK 4 COMPLETED")
    print("Records normalized:", len(papers))
    print("Created:", JSON_OUTPUT)
    print("Created:", CSV_OUTPUT)


if __name__ == "__main__":
    main()