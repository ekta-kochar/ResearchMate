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


def search_europepmc(query, limit=5):

    api_url = (
        "https://www.ebi.ac.uk/europepmc/"
        "webservices/rest/search"
    )

    params = {
        "query": query,
        "format": "json",
        "pageSize": limit,
        "resultType": "core"
    }

    response = requests.get(
        api_url,
        params=params,
        timeout=30
    )

    print("Europe PMC HTTP Status:", response.status_code)
    response.raise_for_status()

    data = response.json()
    results = data.get("resultList", {}).get("result", [])

    papers = []

    for item in results:

        title = (item.get("title") or "").strip()
        abstract = (item.get("abstractText") or "").strip()

        # Convert publication date into a year.
        date = item.get("firstPublicationDate") or ""
        year_match = re.search(r"\b\d{4}\b", date)
        year = int(year_match.group()) if year_match else None

        # Split the API's author string into a list.
        author_string = item.get("authorString") or ""
        authors = [
            name.strip()
            for name in author_string.split(",")
            if name.strip()
        ]

        doi = item.get("doi") or ""
        pmid = item.get("pmid") or ""
        pmcid = item.get("pmcid") or ""

        # Prefer the DOI link, then a PubMed Central link.
        if doi:
            paper_url = "https://doi.org/" + doi
        elif pmcid:
            paper_url = "https://pmc.ncbi.nlm.nih.gov/articles/" + pmcid + "/"
        elif pmid:
            paper_url = "https://pubmed.ncbi.nlm.nih.gov/" + pmid + "/"
        else:
            paper_url = ""

        paper_id = (
            item.get("id")
            or doi
            or pmid
            or pmcid
            or paper_url
        )

        papers.append(create_paper(
            paper_id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            doi=doi,
            url=paper_url,
            source="Europe PMC",
            journal=item.get("journalTitle") or "",
            publication_type=item.get("pubType") or ""
        ))

    return papers


if __name__ == "__main__":

    query = input("Enter your research question: ")

    try:
        results = search_europepmc(query, limit=5)

        print("\nEUROPE PMC RESULTS")
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
        print("Europe PMC request failed:", error)
    except ValueError as error:
        print("Could not read the API response:", error)