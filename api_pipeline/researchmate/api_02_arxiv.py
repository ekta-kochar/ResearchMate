"""arXiv API client for ResearchMate."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import Any

import requests

ARXIV_URL = "https://export.arxiv.org/api/query"
NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}
USER_AGENT = "ResearchMate/1.0"


def parse_arxiv_entry(entry: ET.Element, query: str, ns: dict[str, str] | None = None) -> dict[str, Any]:
    """Convert one arXiv Atom entry into the common ResearchMate schema."""
    ns = ns or NAMESPACES

    title = entry.findtext("atom:title", default=None, namespaces=ns)
    abstract = entry.findtext("atom:summary", default=None, namespaces=ns)

    authors = [
        author.findtext("atom:name", default=None, namespaces=ns)
        for author in entry.findall("atom:author", ns)
    ]
    authors = [author for author in authors if author]

    published = entry.findtext("atom:published", default=None, namespaces=ns)
    year = published[:4] if published else None

    doi = entry.findtext("arxiv:doi", default=None, namespaces=ns)

    # arXiv categories are subject categories, not author-supplied keywords.
    keywords = [
        node.attrib.get("term")
        for node in entry.findall("atom:category", ns)
        if node.attrib.get("term")
    ]

    source_url = entry.findtext("atom:id", default=None, namespaces=ns)

    return {
        "query": query,
        "source": "arXiv",
        "source_id": source_url,
        "title": title.strip() if title else None,
        "authors": authors,
        "abstract": abstract.strip() if abstract else None,
        "keywords": keywords,
        "year": year,
        "doi": doi,
        "url": source_url,
    }


def search_arxiv(
    query: str,
    max_results: int = 5,
    wait_seconds: int = 3,
    retries: int = 3,
    timeout: int = 60,
) -> list[dict[str, Any]]:
    """Search arXiv with basic rate-limit and timeout handling."""
    params = {
        "search_query": f'all:"{query}"',
        "start": 0,
        "max_results": max_results,
    }
    headers = {"User-Agent": USER_AGENT}

    for attempt in range(retries):
        try:
            time.sleep(wait_seconds)
            response = requests.get(
                ARXIV_URL,
                params=params,
                headers=headers,
                timeout=timeout,
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() else 15
                print(f"arXiv rate limit reached. Waiting {delay} seconds...")
                time.sleep(delay)
                continue

            response.raise_for_status()
            root = ET.fromstring(response.content)
            entries = root.findall("atom:entry", NAMESPACES)

            return [
                parse_arxiv_entry(entry, query, NAMESPACES)
                for entry in entries
            ]

        except requests.exceptions.Timeout:
            print(f"arXiv timed out (attempt {attempt + 1}/{retries})")
            time.sleep(10)

        except requests.exceptions.RequestException as exc:
            print(f"arXiv request failed (attempt {attempt + 1}/{retries}): {exc}")
            time.sleep(10)

    print("arXiv failed after all retries.")
    return []
