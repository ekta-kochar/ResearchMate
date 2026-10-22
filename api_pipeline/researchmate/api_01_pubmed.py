"""PubMed API client for ResearchMate.

Public functions
----------------
search_pubmed(query, max_results=5)
    Search PubMed and return normalized paper dictionaries.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import requests

SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def parse_pubmed_article(article: ET.Element, query: str) -> dict[str, Any]:
    """Convert one PubMed XML article into the common ResearchMate schema."""
    title_node = article.find(".//ArticleTitle")
    title = "".join(title_node.itertext()).strip() if title_node is not None else None

    abstract_nodes = article.findall(".//Abstract/AbstractText")
    abstract_parts: list[str] = []
    for node in abstract_nodes:
        text = "".join(node.itertext()).strip()
        label = node.attrib.get("Label")
        if text:
            abstract_parts.append(f"{label}: {text}" if label else text)
    abstract = " ".join(abstract_parts) if abstract_parts else None

    authors: list[str] = []
    for author in article.findall(".//Author"):
        first = author.findtext("ForeName")
        last = author.findtext("LastName")
        name = " ".join(part for part in (first, last) if part)
        if name:
            authors.append(name)

    keywords = [
        "".join(node.itertext()).strip()
        for node in article.findall(".//Keyword")
        if "".join(node.itertext()).strip()
    ]

    year_node = article.find(".//JournalIssue/PubDate/Year")
    year = year_node.text if year_node is not None else None

    pmid = article.findtext(".//PMID")

    doi = None
    for node in article.findall(".//ELocationID"):
        if node.attrib.get("EIdType") == "doi":
            doi = node.text
            break

    if doi is None:
        for node in article.findall(".//ArticleId"):
            if node.attrib.get("IdType") == "doi":
                doi = node.text
                break

    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None

    return {
        "query": query,
        "source": "PubMed",
        "source_id": pmid,
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "keywords": keywords,
        "year": year,
        "doi": doi,
        "url": url,
    }


def search_pubmed(query: str, max_results: int = 5, timeout: int = 30) -> list[dict[str, Any]]:
    """Search PubMed and return normalized results."""
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
    }

    search_response = requests.get(SEARCH_URL, params=search_params, timeout=timeout)
    search_response.raise_for_status()

    pmids = search_response.json()["esearchresult"]["idlist"]
    if not pmids:
        return []

    fetch_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }

    fetch_response = requests.get(FETCH_URL, params=fetch_params, timeout=timeout)
    fetch_response.raise_for_status()

    root = ET.fromstring(fetch_response.content)
    articles = root.findall(".//PubmedArticle")

    return [parse_pubmed_article(article, query) for article in articles]
