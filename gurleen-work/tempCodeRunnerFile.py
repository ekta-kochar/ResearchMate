import csv
import requests


def load_queries():
    with open("queries.csv", "r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def search_crossref(query, limit=5):
    url = "https://api.crossref.org/v1/works"

    params = {
        "query": query,
        "rows": limit
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    items = response.json().get("message", {}).get("items", [])
    papers = []

    for item in items:
        title_list = item.get("title") or []
        title = title_list[0] if title_list else ""

        authors = []
        for author in item.get("author", []):
            name = " ".join(
                part for part in [
                    author.get("given", ""),
                    author.get("family", "")
                ] if part
            )
            if name:
                authors.append(name)

        doi = item.get("DOI") or ""
        url_value = item.get("URL") or ""

        papers.append({
            "paper_id": doi or url_value or title,
            "title": title,
            "authors": authors,
            "abstract": item.get("abstract") or "",
            "year": (
                (item.get("published", {}).get("date-parts") or [[None]])[0][0]
            ),
            "doi": doi,
            "url": url_value,
            "source": "Crossref",
            "journal": (
                (item.get("container-title") or [""])[0]
            ),
            "publication_type": item.get("type") or ""
        })

    return papers


if __name__ == "__main__":
    for query_item in load_queries():
        query_id = query_item["query_id"]
        query = query_item["query"]

        print(f"\n{query_id}: {query}")
        try:
            results = search_crossref(query, limit=5)
            print("Papers found:", len(results))

            for number, paper in enumerate(results, start=1):
                print(f"{number}. {paper['title']}")
                print("   DOI:", paper["doi"])
                print("   URL:", paper["url"])

        except (requests.RequestException, ValueError) as error:
            print("Crossref search failed:", error)