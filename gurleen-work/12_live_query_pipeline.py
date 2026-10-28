import csv
import hashlib
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer, util


# --------------------------------------------------
# 1. PROJECT SETTINGS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

CACHE_DIR = BASE_DIR / "researchmate_live_cache"
CACHE_DIR.mkdir(exist_ok=True)

CACHE_RESULTS_FILE = CACHE_DIR / "query_results.json"
CHROMA_DIR = CACHE_DIR / "chroma_db"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# A cached query is reused only when similarity reaches this value.
# This is a starting value and should be tested with real queries.
CACHE_THRESHOLD = 0.92

RESULTS_PER_API = 5
TOP_N = 10

API_FILES = [
    ("Crossref", "02_crossref_api.py", "search_crossref"),
    ("arXiv", "03_arxiv_api.py", "search_arxiv"),
    ("PubMed", "04_pubmed_api.py", "search_pubmed"),
    ("Europe PMC", "05_europepmc_api.py", "search_europepmc"),
    ("OpenAlex", "06_openalex_api.py", "search_openalex"),
]


# --------------------------------------------------
# 2. LOAD EXISTING API FUNCTIONS
# --------------------------------------------------

def load_api_function(filename, function_name):
    """Load a search function from an existing numbered Python file."""

    file_path = BASE_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Required API file was not found: {file_path}"
        )

    module_name = f"researchmate_{filename.replace('.', '_')}"

    spec = importlib.util.spec_from_file_location(
        module_name, file_path
    )

    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {filename}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    function = getattr(module, function_name, None)

    if not callable(function):
        raise AttributeError(
            f"{function_name}() was not found in {filename}"
        )

    return function


def fetch_from_all_apis(query):
    """Search all five APIs for the user's current query."""

    all_papers = []
    api_status = []

    for source, filename, function_name in API_FILES:
        try:
            search_function = load_api_function(
                filename, function_name
            )

            # Matches the call pattern used in 07_batch_queries.py.
            papers = search_function(query, limit=RESULTS_PER_API)

            if not isinstance(papers, list):
                papers = list(papers or [])

            for paper in papers:
                if isinstance(paper, dict):
                    paper = dict(paper)
                    paper["source"] = paper.get("source") or source
                    all_papers.append(paper)

            api_status.append(
                f"{source}: {len(papers)} records"
            )

        except Exception as error:
            # One API failure should not stop the other APIs.
            api_status.append(
                f"{source}: FAILED ({error})"
            )
            print(f"Warning: {api_status[-1]}")

    print("\nAPI retrieval summary:")
    for status in api_status:
        print(" -", status)

    return all_papers


# --------------------------------------------------
# 3. NORMALIZE PAPER METADATA
# --------------------------------------------------

def clean_text(value):
    if value is None:
        return ""

    if isinstance(value, list):
        value = ", ".join(str(item) for item in value)

    value = str(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_paper(paper):
    """Convert API records to a common, predictable structure."""

    authors = paper.get("authors", [])

    if isinstance(authors, str):
        authors = [
            author.strip()
            for author in authors.split(",")
            if author.strip()
        ]

    if not isinstance(authors, list):
        authors = []

    year = paper.get("year", "")

    try:
        year = int(str(year)[:4])
        if year < 1000 or year > datetime.now().year + 1:
            year = ""
    except (TypeError, ValueError):
        year = ""

    doi = clean_text(paper.get("doi", ""))
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi,
                 flags=re.IGNORECASE).strip().lower()

    title = clean_text(paper.get("title", ""))
    abstract = clean_text(paper.get("abstract", ""))

    return {
        "paper_id": clean_text(paper.get("paper_id", "")),
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "year": year,
        "doi": doi,
        "url": clean_text(paper.get("url", "")),
        "source": clean_text(paper.get("source", "")),
        "journal": clean_text(paper.get("journal", "")),
        "publication_type": clean_text(
            paper.get("publication_type", "")
        ),
    }


# --------------------------------------------------
# 4. RECOVER ABSTRACTS FROM MATCHING RECORDS
# --------------------------------------------------

def title_key(title):
    return re.sub(r"[^a-z0-9]", "", clean_text(title).lower())


def recover_abstracts(papers):
    """
    Recover an abstract only from a matching publication:
    same DOI, or an identical cleaned title when DOI is unavailable.
    """

    abstract_by_doi = {}
    abstract_by_title = {}

    for paper in papers:
        abstract = paper["abstract"]

        if not abstract:
            continue

        if paper["doi"]:
            abstract_by_doi.setdefault(
                paper["doi"], abstract
            )

        key = title_key(paper["title"])
        if key:
            abstract_by_title.setdefault(key, abstract)

    for paper in papers:
        if paper["abstract"]:
            continue

        if paper["doi"] and paper["doi"] in abstract_by_doi:
            paper["abstract"] = abstract_by_doi[paper["doi"]]
            continue

        key = title_key(paper["title"])
        if key and key in abstract_by_title:
            paper["abstract"] = abstract_by_title[key]

    return papers


# --------------------------------------------------
# 5. DEDUPLICATE PAPERS
# --------------------------------------------------

def deduplicate_papers(papers):
    """Prefer DOI matching; use normalized title if DOI is absent."""

    unique_papers = {}
    result = []

    for paper in papers:
        doi = paper["doi"]
        key_title = title_key(paper["title"])

        if doi:
            key = "doi:" + doi
        elif key_title:
            key = "title:" + key_title
        else:
            # Do not accidentally merge records without identifiers.
            key = "record:" + hashlib.sha256(
                json.dumps(paper, sort_keys=True).encode("utf-8")
            ).hexdigest()

        if key not in unique_papers:
            unique_papers[key] = paper
            result.append(paper)
        else:
            # Fill missing fields in the retained record.
            existing = unique_papers[key]

            for field in (
                "abstract", "url", "year", "journal",
                "publication_type", "paper_id"
            ):
                if not existing.get(field) and paper.get(field):
                    existing[field] = paper[field]

            if not existing.get("authors") and paper.get("authors"):
                existing["authors"] = paper["authors"]

    return result


# --------------------------------------------------
# 6. SEMANTIC SEARCH AND RANKING
# --------------------------------------------------

def paper_text(paper):
    return (
        clean_text(paper.get("title", "")) + " " +
        clean_text(paper.get("abstract", ""))
    ).strip()


def keyword_score(query, paper):
    query_words = set(re.findall(r"\b\w+\b", query.lower()))
    paper_words = set(
        re.findall(r"\b\w+\b", paper_text(paper).lower())
    )

    if not query_words:
        return 0.0

    return len(query_words & paper_words) / len(query_words)


def recency_score(year):
    try:
        year = int(year)
    except (TypeError, ValueError):
        return 0.0

    age = max(0, datetime.now().year - year)

    # Newer papers receive a higher score.
    return max(0.0, 1.0 - age / 20.0)


def rank_papers(query, papers, model):
    if not papers:
        return []

    texts = [paper_text(paper) for paper in papers]

    # Empty text cannot provide meaningful semantic similarity.
    query_embedding = model.encode(
        query, convert_to_tensor=True
    )
    paper_embeddings = model.encode(
        texts, convert_to_tensor=True
    )

    semantic_scores = util.cos_sim(
        query_embedding, paper_embeddings
    )[0]

    ranked = []

    for index, paper in enumerate(papers):
        semantic = max(
            0.0, float(semantic_scores[index].item())
        )
        keywords = keyword_score(query, paper)
        recency = recency_score(paper.get("year", ""))

        final_score = (
            0.70 * semantic
            + 0.20 * keywords
            + 0.10 * recency
        )

        item = dict(paper)
        item["semantic_score"] = round(semantic, 4)
        item["keyword_score"] = round(keywords, 4)
        item["recency_score"] = round(recency, 4)
        item["final_score"] = round(final_score, 4)

        ranked.append(item)

    ranked.sort(
        key=lambda item: item["final_score"],
        reverse=True
    )

    return ranked[:TOP_N]


# --------------------------------------------------
# 7. SET UP THE VECTOR QUERY CACHE
# --------------------------------------------------

client = chromadb.PersistentClient(path=str(CHROMA_DIR))

collection = client.get_or_create_collection(
    name="researchmate_live_queries",
    metadata={"hnsw:space": "cosine"}
)


def load_saved_results():
    if not CACHE_RESULTS_FILE.exists():
        return {}

    try:
        with open(CACHE_RESULTS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}


def save_results(results):
    with open(CACHE_RESULTS_FILE, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)


def find_cached_query(query, model):
    """Find the most similar previously saved query."""

    if collection.count() == 0:
        return None

    query_embedding = model.encode(query).tolist()

    stored = collection.get(
        include=["embeddings", "metadatas"]
    )

    if not stored["ids"] or stored["embeddings"] is None:
        return None

    best_id = None
    best_similarity = -1.0

    for item_id, embedding in zip(
        stored["ids"], stored["embeddings"]
    ):
        similarity = float(
            util.cos_sim(query_embedding, embedding).item()
        )

        if similarity > best_similarity:
            best_similarity = similarity
            best_id = item_id

    if best_id is None or best_similarity < CACHE_THRESHOLD:
        return None

    saved_results = load_saved_results()
    cached = saved_results.get(best_id)

    # A vector match without its saved results is not a cache hit.
    if not cached or not cached.get("papers"):
        return None

    print(
        f"Cache hit: matched a previous query "
        f"(similarity {best_similarity:.3f})."
    )

    return cached["papers"]


def save_query_to_cache(query, papers, model):
    query_id = hashlib.sha256(
        query.strip().lower().encode("utf-8")
    ).hexdigest()

    embedding = model.encode(query).tolist()

    collection.upsert(
        ids=[query_id],
        embeddings=[embedding],
        metadatas=[{"query": query}]
    )

    saved_results = load_saved_results()
    saved_results[query_id] = {
        "query": query,
        "saved_at": datetime.now().isoformat(),
        "papers": papers
    }

    save_results(saved_results)


# --------------------------------------------------
# 8. SAVE OUTPUTS
# --------------------------------------------------

def save_papers_csv(papers, filename):
    if not papers:
        print("No papers to save.")
        return

    fields = [
        "paper_id", "title", "authors", "abstract", "year",
        "doi", "url", "source", "journal", "publication_type",
        "semantic_score", "keyword_score", "recency_score",
        "final_score"
    ]

    with open(
        BASE_DIR / filename, "w",
        newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for paper in papers:
            row = dict(paper)
            row["authors"] = "; ".join(
                str(author) for author in row.get("authors", [])
            )
            writer.writerow({
                field: row.get(field, "") for field in fields
            })


# --------------------------------------------------
# 9. MAIN PIPELINE
# --------------------------------------------------

def main():
    query = input(
        "\nEnter your research question: "
    ).strip()

    if not query:
        print("Please enter a research question.")
        return

    print("\nLoading semantic model...")
    model = SentenceTransformer(MODEL_NAME)

    # FIRST: Check the vector query cache.
    cached_papers = find_cached_query(query, model)

    if cached_papers is not None:
        print("\nUsing saved results from the query cache.")
        results = cached_papers

    else:
        # CACHE MISS: Go back to the initial API retrieval phase.
        print("\nCache miss. Fetching fresh papers from all five APIs...")

        raw_papers = fetch_from_all_apis(query)

        if not raw_papers:
            print(
                "\nNo papers were retrieved. Check your internet "
                "connection, API modules, and API error messages."
            )
            return

        print(f"\nRetrieved records: {len(raw_papers)}")

        normalized = [
            normalize_paper(paper) for paper in raw_papers
        ]

        normalized = [
            paper for paper in normalized if paper["title"]
        ]

        recovered = recover_abstracts(normalized)
        deduplicated = deduplicate_papers(recovered)

        print(f"After deduplication: {len(deduplicated)} papers")

        # Save the current query's processed dataset separately.
        with open(
            BASE_DIR / "live_query_papers.json",
            "w", encoding="utf-8"
        ) as file:
            json.dump(
                deduplicated, file, indent=2, ensure_ascii=False
            )

        results = rank_papers(query, deduplicated, model)

        # Save and cache only the final ranked results.
        save_papers_csv(results, "live_query_ranked_papers.csv")
        save_query_to_cache(query, results, model)

    print("\nTOP RESEARCH PAPERS")
    print("=" * 70)

    for index, paper in enumerate(results, start=1):
        print(f"\n{index}. {paper.get('title', 'Untitled')}")
        print(f"   Year: {paper.get('year', 'Unknown')}")
        print(f"   Source: {paper.get('source', 'Unknown')}")
        print(f"   DOI: {paper.get('doi') or 'Not available'}")
        print(f"   Score: {paper.get('final_score', 'N/A')}")
        print(f"   URL: {paper.get('url') or 'Not available'}")

    if results:
        save_papers_csv(results, "live_query_ranked_papers.csv")
        print(
            "\nSaved ranked results to "
            "'live_query_ranked_papers.csv'."
        )

    print("\nPipeline finished.")


if __name__ == "__main__":
    main()