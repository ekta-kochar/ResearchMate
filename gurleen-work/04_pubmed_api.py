import csv
import requests
import xml.etree.ElementTree as ET


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


def load_queries():
    with open("queries.csv", "r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def search_pubmed(query, limit=5):
    # Step 1: Search PubMed and collect paper IDs.
    search_url = BASE_URL + "esearch.fcgi"

    search_params = {
        "db": "pubmed",
        "term": query,
        "retmax": limit,
        "retmode": "json"
    }

    response = requests.get(
        search_url,
        params=search_params,
        timeout=30
    )
    response.raise_for_status()

    search_data = response.json()
    paper_ids = (
        search_data.get("esearchresult", {}).get("idlist", [])
    )

    if not paper_ids:
        return []

    # Step 2: Fetch the details for the returned paper IDs.
    fetch_url = BASE_URL + "efetch.fcgi"

    fetch_params = {
        "db": "pubmed",
        "id": ",".join(paper_ids),
        "retmode": "xml"
    }

    response = requests.get(
        fetch_url,
        params=fetch_params,
        timeout=30
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    papers = []

    for article in root.findall(".//PubmedArticle"):
        citation = article.find("MedlineCitation")
        if citation is None:
            continue

        article_data = citation.find("Article")
        if article_data is None:
            continue

        pmid_element = citation.find("PMID")
        pmid = (
            pmid_element.text.strip()
            if pmid_element is not None and pmid_element.text
            else ""
        )

        title_element = article_data.find("ArticleTitle")
        title = (
            "".join(title_element.itertext()).strip()
            if title_element is not None else ""
        )

        # Collect author names.
        authors = []
        author_list = article_data.find("AuthorList")

        if author_list is not None:
            for author in author_list.findall("Author"):
                collective = author.find("CollectiveName")

                if collective is not None and collective.text:
                    authors.append(collective.text.strip())
                    continue

                last = author.find("LastName")
                first = author.find("ForeName")

                name_parts = []
                if first is not None and first.text:
                    name_parts.append(first.text.strip())
                if last is not None and last.text:
                    name_parts.append(last.text.strip())

                if name_parts:
                    authors.append(" ".join(name_parts))

        # Collect abstract text.
        abstract_parts = []
        abstract_element = article_data.find("Abstract")

        if abstract_element is not None:
            for part in abstract_element.findall("AbstractText"):
                text = "".join(part.itertext()).strip()
                if text:
                    abstract_parts.append(text)

        abstract = " ".join(abstract_parts)

        # Get publication year.
        year = None
        date_candidates = [
            article_data.find("Journal/JournalIssue/PubDate"),
            article_data.find("Journal/JournalIssue/PubDate/MedlineDate")
        ]

        for date_element in date_candidates:
            if date_element is None:
                continue

            year_element = date_element.find("Year")

            if year_element is not None and year_element.text:
                try:
                    year = int(year_element.text.strip())
                    break
                except ValueError:
                    pass

            date_text = "".join(date_element.itertext())
            import re
            match = re.search(r"\b(19|20)\d{2}\b", date_text)

            if match:
                year = int(match.group())
                break

        # Get journal name.
        journal_element = article_data.find("Journal/Title")
        journal = (
            journal_element.text.strip()
            if journal_element is not None and journal_element.text
            else ""
        )

        # DOI is stored in ArticleIdList when available.
        doi = ""
        pubmed_data = article.find("PubmedData")

        if pubmed_data is not None:
            id_list = pubmed_data.find("ArticleIdList")

            if id_list is not None:
                for article_id in id_list.findall("ArticleId"):
                    if article_id.get("IdType") == "doi":
                        doi = (article_id.text or "").strip()
                        break

        publication_types = []
        type_list = article_data.find("PublicationTypeList")

        if type_list is not None:
            for item in type_list.findall("PublicationType"):
                if item.text:
                    publication_types.append(item.text.strip())

        papers.append({
            "paper_id": pmid,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "year": year,
            "doi": doi,
            "url": (
                f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                if pmid else ""
            ),
            "source": "PubMed",
            "journal": journal,
            "publication_type": ", ".join(publication_types)
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

            results = search_pubmed(query, limit=5)

            print("Papers found:", len(results))

            for number, paper in enumerate(results, start=1):
                print(f"\nPaper {number}: {paper['title']}")
                print("Authors:", paper["authors"])
                print("Year:", paper["year"])
                print("Journal:", paper["journal"])
                print("DOI:", paper["doi"] or "Not available")
                print("URL:", paper["url"])

    except (requests.RequestException, ET.ParseError, ValueError) as error:
        print("PubMed search failed:", error)
    except FileNotFoundError:
        print("Error: queries.csv was not found in this folder.")