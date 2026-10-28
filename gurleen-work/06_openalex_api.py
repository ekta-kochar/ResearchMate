import os
import requests
import re


def create_paper(
    paper_id="",
    title="",
    authors=None,
    abstract="",
    year=None,
    doi="",
    url="",
    source="",
    journal="",
    publication_type=""
):
    return {
        "paper_id": paper_id,
        "title": title,
        "authors": authors or [],
        "abstract": abstract,
        "year": year,
        "doi": doi,
        "url": url,
        "source": source,
        "journal": journal,
        "publication_type": publication_type
    }


def reconstruct_abstract(inverted_index):
    """Convert OpenAlex's abstract index into readable text."""

    if not inverted_index:
        return ""

    words = {}

    for word, positions in inverted_index.items():
        for position in positions:
            words[position] = word

    if not words:
        return ""

    return " ".join(
        words[position]
        for position in sorted(words)
    )


def search_openalex(query, limit=5):

    api_url = "https://api.openalex.org/works"

    params = {
        "search": query,
        "per_page": limit
    }

    # Optional: use a free API key if one is available.
    api_key = os.getenv("OPENALEX_API_KEY")

    if api_key:
        params["api_key"] = api_key

    response = requests.get(
        api_url,
        params=params,
        timeout=30
    )

    print("OpenAlex HTTP Status:", response.status_code)
    response.raise_for_status()

    data = response.json()
    results = data.get("results", [])

    papers = []

    for item in results:

        title = (item.get("title") or "").strip()

        authors = []

        for authorship in item.get("authorships", []):
            author = authorship.get("author") or {}
            name = author.get("display_name", "")

            if name:
                authors.append(name)

        year = item.get("publication_year")

        doi_value = item.get("doi") or ""
        doi = re.sub(
            r"^https?://doi\.org/",
            "",
            doi_value,
            flags=re.IGNORECASE
        )

        primary_location = item.get("primary_location") or {}
        landing_page = primary_location.get("landing_page_url") or ""
        source_info = primary_location.get("source") or {}

        paper_url = landing_page or doi_value or item.get("id") or ""

        abstract = reconstruct_abstract(
            item.get("abstract_inverted_index")
        )

        papers.append(create_paper(
            paper_id=item.get("id") or doi or paper_url,
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            doi=doi,
            url=paper_url,
            source="OpenAlex",
            journal=source_info.get("display_name") or "",
            publication_type=item.get("type") or ""
        ))

    return papers


if __name__ == "__main__":

    query = input("Enter your research question: ")

    try:
        results = search_openalex(query, limit=5)

        print("\nOPENALEX RESULTS")
        print("=" * 40)

        for i, paper in enumerate(results, start=1):
            print(f"\nPaper {i}")
            print("Title:", paper["title"])
            print("Authors:", paper["authors"])
            print("Year:", paper["year"])
            print("DOI:", paper["doi"])
            print("Abstract:", paper["abstract"][:250])
            print("URL:", paper["url"])

        print("\nTotal papers found:", len(results))

    except requests.RequestException as error:
        print("OpenAlex request failed:", error)
    except ValueError as error:
        print("Could not read the API response:", error)