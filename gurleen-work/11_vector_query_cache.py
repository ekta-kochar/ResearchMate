import json
import re
import hashlib
from datetime import datetime
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


# ==================================================
# 1. PROJECT SETTINGS
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

PAPERS_FILE = BASE_DIR / "papers_deduplicated.json"
CACHE_FILE = BASE_DIR / "query_cache_results.json"
VECTOR_DB_DIR = BASE_DIR / "researchmate_vectordb"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

SIMILARITY_THRESHOLD = 0.82
TOP_RESULTS = 10

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were",
    "for", "to", "of", "in", "on", "and", "or",
    "with", "by", "how", "what", "which", "can",
    "we", "using", "use", "from", "about", "find",
    "paper", "papers", "research", "study", "methods",
    "method", "approach", "approaches"
}


# ==================================================
# 2. GENERAL HELPER FUNCTIONS
# ==================================================

def clean_text(value):
    """Convert a value into readable text."""
    if value is None:
        return ""

    if isinstance(value, list):
        return "; ".join(clean_text(item) for item in value)

    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)

    return str(value).strip()


def get_first_value(record, possible_names):
    """Return the first non-empty value found in a record."""
    for name in possible_names:
        value = record.get(name)

        if value is not None and value != "":
            return value

    return None


def normalize_query(query):
    """Normalize spaces and letter case for exact matching."""
    return " ".join(query.lower().split())


def extract_keywords(text):
    """Extract basic keywords from a query."""
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())

    return {
        word for word in words
        if len(word) > 1 and word not in STOPWORDS
    }


def get_source_api(paper):
    """
    Read the API source from the paper record.
    This does not guess the source when it is missing.
    """
    source = get_first_value(
        paper,
        [
            "source",
            "api",
            "source_api",
            "provider",
            "database",
            "source_name"
        ]
    )

    if source is None:
        return "Unknown - not stored in record"

    return clean_text(source)


def get_title(paper):
    return clean_text(
        get_first_value(paper, ["title", "paper_title"])
    )


def get_abstract(paper):
    return clean_text(
        get_first_value(paper, ["abstract", "summary"])
    )


def get_doi(paper):
    return clean_text(
        get_first_value(paper, ["doi", "DOI"])
    )


def get_year(paper):
    value = get_first_value(
        paper,
        ["year", "publication_year", "published_year"]
    )

    try:
        year = int(str(value)[:4])

        if 1000 <= year <= datetime.now().year:
            return year
    except (TypeError, ValueError):
        pass

    return None


def get_paper_keywords(paper):
    return clean_text(
        get_first_value(
            paper,
            ["keywords", "keyword", "subjects", "tags"]
        )
    )


def paper_text(paper):
    """Combine paper fields for semantic ranking."""
    return (
        f"Title: {get_title(paper)}. "
        f"Abstract: {get_abstract(paper)}. "
        f"Keywords: {get_paper_keywords(paper)}"
    )


# ==================================================
# 3. LOAD THE EXISTING RESEARCH PAPERS
# ==================================================

def load_papers():
    if not PAPERS_FILE.exists():
        raise FileNotFoundError(
            f"Missing file: {PAPERS_FILE.name}\n"
            "Please run your existing normalization and "
            "deduplication scripts first."
        )

    with open(PAPERS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        for key in ("papers", "results", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break

    if not isinstance(data, list):
        raise ValueError(
            "The JSON file must contain a list of paper records."
        )

    papers = [
        paper for paper in data
        if isinstance(paper, dict) and get_title(paper)
    ]

    return papers


# ==================================================
# 4. INITIALIZE THE EMBEDDING MODEL AND VECTORDB
# ==================================================

print("Loading sentence-transformer model...")

model = SentenceTransformer(MODEL_NAME)

client = chromadb.PersistentClient(
    path=str(VECTOR_DB_DIR)
)

collection = client.get_or_create_collection(
    name="researchmate_query_history",
    metadata={"hnsw:space": "cosine"}
)

print("Embedding model loaded.")
print("Persistent VectorDB is ready.")


# ==================================================
# 5. LOAD AND SAVE QUERY RESULT CACHE
# ==================================================

def load_cache():
    if not CACHE_FILE.exists():
        return {}

    with open(CACHE_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            "The query cache JSON must contain a dictionary."
        )

    return data


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            cache,
            file,
            indent=2,
            ensure_ascii=False
        )


# ==================================================
# 6. SEARCH FOR A PREVIOUS QUERY
# ==================================================

def find_previous_query(query, query_vector):
    if collection.count() == 0:
        return None

    number_to_check = min(5, collection.count())

    search_result = collection.query(
        query_embeddings=[query_vector.tolist()],
        n_results=number_to_check,
        include=["distances", "metadatas"]
    )

    ids = search_result.get("ids", [[]])[0]
    distances = search_result.get("distances", [[]])[0]
    metadatas = search_result.get("metadatas", [[]])[0]

    current_keywords = extract_keywords(query)
    current_normalized = normalize_query(query)

    candidates = []

    for record_id, distance, metadata in zip(
        ids, distances, metadatas
    ):
        previous_query = metadata.get("query", "")
        previous_normalized = normalize_query(previous_query)

        # ChromaDB cosine distance = 1 - cosine similarity.
        similarity = max(
            -1.0,
            min(1.0, 1.0 - float(distance))
        )

        previous_keywords = set(
            metadata.get("keywords", "").split()
        )

        if current_keywords:
            overlap = (
                len(current_keywords & previous_keywords)
                / len(current_keywords)
            )
        else:
            overlap = 0.0

        exact_match = current_normalized == previous_normalized

        # Exact questions can use their saved results.
        # Similar questions need semantic similarity and
        # some keyword overlap, unless similarity is very high.
        suitable_match = (
            exact_match
            or (
                similarity >= SIMILARITY_THRESHOLD
                and (
                    overlap >= 0.20
                    or similarity >= 0.92
                )
            )
        )

        if suitable_match:
            candidates.append({
                "id": record_id,
                "query": previous_query,
                "similarity": similarity,
                "keyword_overlap": overlap,
                "exact_match": exact_match
            })

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item["similarity"],
        reverse=True
    )

    return candidates[0]


# ==================================================
# 7. RANK PAPERS FOR A NEW QUERY
# ==================================================

def rank_papers(query, papers):
    if not papers:
        return []

    query_vector = model.encode([query])

    paper_texts = [paper_text(paper) for paper in papers]

    paper_vectors = model.encode(
        paper_texts,
        show_progress_bar=False
    )

    semantic_scores = cosine_similarity(
        query_vector, paper_vectors
    )[0]

    query_keywords = extract_keywords(query)
    current_year = datetime.now().year

    ranked_papers = []

    for index, paper in enumerate(papers):
        title = get_title(paper)
        abstract = get_abstract(paper)
        keywords = get_paper_keywords(paper)

        searchable_text = (
            f"{title} {abstract} {keywords}"
        ).lower()

        # Keyword relevance.
        if query_keywords:
            matched_keywords = sum(
                1 for word in query_keywords
                if re.search(
                    r"\b" + re.escape(word) + r"\b",
                    searchable_text
                )
            )

            keyword_score = (
                matched_keywords / len(query_keywords)
            )
        else:
            keyword_score = 0.0

        keyword_score = min(keyword_score, 1.0)

        # Semantic similarity, clamped to 0-1.
        semantic_score = max(
            0.0, float(semantic_scores[index])
        )

        # Recency: linear score over the latest 10 years.
        year = get_year(paper)

        if year is None:
            recency_score = 0.0
        else:
            age = current_year - year
            recency_score = max(
                0.0, 1.0 - age / 10.0
            )

        # Weighted final score.
        final_score = (
            0.70 * semantic_score
            + 0.20 * keyword_score
            + 0.10 * recency_score
        )

        # Preserve original metadata, including the source.
        result = dict(paper)

        result["title"] = title
        result["doi"] = get_doi(paper)
        result["year"] = year if year is not None else ""
        result["abstract"] = abstract
        result["keywords"] = keywords

        # Keep the source if available. Do not invent it.
        result["source_api"] = get_source_api(paper)

        result["semantic_score"] = round(
            semantic_score, 4
        )
        result["keyword_score"] = round(
            keyword_score, 4
        )
        result["recency_score"] = round(
            recency_score, 4
        )
        result["final_score"] = round(
            final_score, 4
        )

        ranked_papers.append(result)

    ranked_papers.sort(
        key=lambda item: item["final_score"],
        reverse=True
    )

    ranked_papers = ranked_papers[:TOP_RESULTS]

    for rank, paper in enumerate(ranked_papers, start=1):
        paper["rank"] = rank

    return ranked_papers


# ==================================================
# 8. SAVE A NEW QUERY AND ITS RANKED RESULTS
# ==================================================

def save_new_query(query, query_vector, results):
    cache = load_cache()

    normalized = normalize_query(query)

    # Stable ID for the same normalized query.
    query_id = "QH_" + hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()[:16]

    cache[query_id] = {
        "query": query,
        "normalized_query": normalized,
        "keywords": sorted(extract_keywords(query)),
        "searched_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "results": results
    }

    save_cache(cache)

    metadata = {
        "query": query,
        "keywords": " ".join(
            sorted(extract_keywords(query))
        ),
        "query_id": query_id
    }

    existing = collection.get(
        ids=[query_id],
        include=["metadatas"]
    )

    if existing["ids"]:
        collection.update(
            ids=[query_id],
            embeddings=[query_vector.tolist()],
            metadatas=[metadata]
        )
    else:
        collection.add(
            ids=[query_id],
            embeddings=[query_vector.tolist()],
            metadatas=[metadata]
        )

    print(f"Saved query ID: {query_id}")


# ==================================================
# 9. DISPLAY RANKED RESULTS INCLUDING SOURCE API
# ==================================================

def display_results(results):
    if not results:
        print("No research papers were found.")
        return

    print("\nTOP RANKED RESEARCH PAPERS")
    print("=" * 70)

    for paper in results:
        print(f"\nRank: {paper.get('rank', 'N/A')}")
        print("Title:", get_title(paper) or "N/A")
        print("DOI:", get_doi(paper) or "N/A")

        year = get_year(paper)
        print("Year:", year if year else "N/A")

        # Source API is shown for every result.
        print(
            "Source API:",
            clean_text(
                paper.get("source_api")
                or get_source_api(paper)
            )
        )

        print(
            "Semantic score:",
            paper.get("semantic_score", "N/A")
        )
        print(
            "Keyword score:",
            paper.get("keyword_score", "N/A")
        )
        print(
            "Recency score:",
            paper.get("recency_score", "N/A")
        )
        print(
            "Final ranking score:",
            paper.get("final_score", "N/A")
        )

        print("-" * 70)


# ==================================================
# 10. MAIN INTERACTIVE SEARCH
# ==================================================

def main():
    papers = load_papers()

    print(f"\nLoaded {len(papers)} research papers.")

    unknown_sources = sum(
        1 for paper in papers
        if get_source_api(paper)
        == "Unknown - not stored in record"
    )

    if unknown_sources:
        print(
            f"Notice: {unknown_sources} papers do not have "
            "a recognized source field in the dataset."
        )
        print(
            "For these papers, check your API collection "
            "scripts and saved JSON metadata."
        )

    print("\nResearchMate VectorDB Query Cache")
    print("Enter 'exit' to stop the program.")

    while True:
        query = input(
            "\nEnter your research query: "
        ).strip()

        if query.lower() in {"exit", "quit"}:
            print("\nResearchMate stopped.")
            break

        if not query:
            print("Please enter a valid query.")
            continue

        print("\nGenerating query embedding...")

        query_vector = model.encode([query])[0]

        match = find_previous_query(query, query_vector)

        cache = load_cache()

        if match and match["id"] in cache:
            cached_entry = cache[match["id"]]

            print("\nPREVIOUS QUERY MATCH FOUND")
            print("Saved query:", match["query"])
            print(
                "Semantic similarity:",
                round(match["similarity"], 4)
            )
            print(
                "Keyword overlap:",
                round(match["keyword_overlap"], 4)
            )

            print("Using cached ranked results.")

            results = cached_entry.get("results", [])

        else:
            print("\nNO SUITABLE QUERY MATCH FOUND")
            print(
                "Ranking papers from the local dataset..."
            )

            results = rank_papers(query, papers)

            save_new_query(
                query,
                query_vector,
                results
            )

        display_results(results)


if __name__ == "__main__":
    main()