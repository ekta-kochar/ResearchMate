import csv
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime


def load_queries():
    with open("queries.csv", "r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def search_arxiv(query, limit=5):
    api_url = "https://export.arxiv.org/api/query"

    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit
    }

    response = requests.get(
        api_url,
        params=params,
        timeout=60
    )
    print("arXiv HTTP Status:", response.status_code)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}

    papers = []

    for entry in root.findall("atom:entry", namespace):
        title_element = entry.find("atom:title", namespace)
        summary_element = entry.find("atom:summary", namespace)
        published_element = entry.find("atom:published", namespace)
        id_element = entry.find("atom:id", namespace)

        title = (
            " ".join(title_element.itertext()).strip()
            if title_element is not None else ""
        )
        abstract = (
            " ".join(summary_element.itertext()).strip()
            if summary_element is not None else ""
        )
        published = (
            published_element.text.strip()
            if published_element is not None and published_element.text
            else ""
        )
        paper_url = (
            id_element.text.strip()
            if id_element is not None and id_element.text
            else ""
        )

        try:
            year = datetime.strptime(
                published[:10], "%Y-%m-%d"
            ).year
        except ValueError:
            year = None

        authors = []
        for author_element in entry.findall("atom:author", namespace):
            name_element = author_element.find("atom:name", namespace)
            if name_element is not None and name_element.text:
                authors.append(name_element.text.strip())

        doi_element = entry.find(
            "{http://arxiv.org/schemas/atom}doi"
        )
        doi = (
            doi_element.text.strip()
            if doi_element is not None and doi_element.text
            else ""
        )

        papers.append({
            "paper_id": paper_url,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "year": year,
            "doi": doi,
            "url": paper_url,
            "source": "arXiv",
            "journal": "",
            "publication_type": "preprint"
        })

    return papers


if __name__ == "__main__":
    try:
        queries = load_queries()

        for query_item in queries:
            query_id = query_item["query_id"]
            query = query_item["query"]

            print(f"\n{'=' * 55}")
            print(f"{query_id}: {query}")
            print("=" * 55)

            results = search_arxiv(query, limit=5)

            print("Papers found:", len(results))

            for number, paper in enumerate(results, start=1):
                print(f"\nPaper {number}: {paper['title']}")
                print("Authors:", paper["authors"])
                print("Year:", paper["year"])
                print("DOI:", paper["doi"] or "Not available")
                print("URL:", paper["url"])

            # Pause between searches to avoid sending requests too quickly.
            time.sleep(3)

    except (requests.RequestException, ET.ParseError, ValueError) as error:
        print("arXiv search failed:", error)
    except FileNotFoundError:
        print("Error: queries.csv was not found in this folder.")