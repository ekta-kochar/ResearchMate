import csv
import json
import re
import html
from pathlib import Path
from datetime import datetime

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


# --------------------------------------------------
# 1. FILE PATHS AND SETTINGS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

PAPERS_FILE = BASE_DIR / "papers_deduplicated.json"
QUERIES_FILE = BASE_DIR / "queries.csv"

OUTPUT_CSV = BASE_DIR / "ranked_papers.csv"
OUTPUT_JSON = BASE_DIR / "ranking_results.json"
TOP_N_CSV = BASE_DIR / "top_10_papers.csv"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

TOP_N = 10

# Ranking weights
SEMANTIC_WEIGHT = 0.70
KEYWORD_WEIGHT = 0.20
RECENCY_WEIGHT = 0.10

# A paper 10 or more years old gets a recency score of 0.
RECENCY_WINDOW_YEARS = 10

CURRENT_YEAR = datetime.now().year


# --------------------------------------------------
# 2. CLEAN TEXT
# --------------------------------------------------

def clean_text(value):
    """Convert text, lists, and HTML-containing values into clean text."""

    if value is None:
        return ""

    if isinstance(value, list):
        value = " ".join(str(item) for item in value if item)

    if isinstance(value, dict):
        value = " ".join(str(item) for item in value.values())

    value = str(value)
    value = html.unescape(value)

    # Remove HTML tags
    value = re.sub(r"<[^>]+>", " ", value)

    # Replace repeated whitespace with one space
    value = re.sub(r"\s+", " ", value)

    return value.strip()


# --------------------------------------------------
# 3. LOAD PAPERS AND QUERIES
# --------------------------------------------------

def load_papers():
    if not PAPERS_FILE.exists():
        raise FileNotFoundError(
            f"File not found: {PAPERS_FILE.name}\n"
            "Run your deduplication script first."
        )

    with open(PAPERS_FILE, "r", encoding="utf-8") as file:
        papers = json.load(file)

    if not isinstance(papers, list):
        raise ValueError(
            "papers_deduplicated.json must contain a list of papers."
        )

    return papers


def load_queries():
    if not QUERIES_FILE.exists():
        raise FileNotFoundError(
            f"File not found: {QUERIES_FILE.name}"
        )

    with open(
        QUERIES_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:
        queries = list(csv.DictReader(file))

    # Keep only rows containing both required fields
    queries = [
        row for row in queries
        if clean_text(row.get("query_id"))
        and clean_text(row.get("query"))
    ]

    if not queries:
        raise ValueError(
            "No valid queries found in queries.csv."
        )

    return queries


# --------------------------------------------------
# 4. PREPARE PAPER TEXT
# --------------------------------------------------

def get_paper_text(paper):
    """
    Combine title, abstract, and keywords.
    These fields will be used to generate embeddings.
    """

    title = clean_text(paper.get("title"))
    abstract = clean_text(paper.get("abstract"))
    keywords = clean_text(paper.get("keywords"))

    return (
        f"Title: {title}. "
        f"Abstract: {abstract}. "
        f"Keywords: {keywords}"
    ).strip()


# --------------------------------------------------
# 5. KEYWORD RELEVANCE SCORE
# --------------------------------------------------

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were",
    "of", "for", "to", "in", "on", "by", "with",
    "and", "or", "using", "use", "based", "from",
    "how", "what", "which", "this", "that",
    "paper", "papers", "research", "study"
}


def tokenize(text):
    """Convert text into useful lowercase word tokens."""

    words = re.findall(r"[a-z0-9]+", clean_text(text).lower())

    return {
        word for word in words
        if len(word) > 1 and word not in STOPWORDS
    }


def calculate_keyword_score(query, paper):
    """
    Keyword score = matching query terms / all query terms.

    Search terms are checked against title, abstract,
    and keywords. The result ranges from 0 to 1.
    """

    query_words = tokenize(query)

    if not query_words:
        return 0.0

    title = clean_text(paper.get("title"))
    abstract = clean_text(paper.get("abstract"))
    keywords = clean_text(paper.get("keywords"))

    paper_words = tokenize(
        f"{title} {abstract} {keywords}"
    )

    matched_words = query_words.intersection(paper_words)

    return len(matched_words) / len(query_words)


# --------------------------------------------------
# 6. RECENCY SCORE
# --------------------------------------------------

def calculate_recency_score(paper):
    """
    Latest year gets a score close to 1.
    A paper 10 or more years old gets 0.
    Missing or invalid years get 0.
    """

    try:
        year_text = clean_text(paper.get("year"))

        if not year_text:
            return 0.0

        # Handles values such as "2024" and "2024.0"
        year = int(float(year_text))

        if year <= 0 or year > CURRENT_YEAR:
            return 0.0

        age = CURRENT_YEAR - year

        score = 1 - (age / RECENCY_WINDOW_YEARS)

        return max(0.0, min(1.0, score))

    except (ValueError, TypeError):
        return 0.0


# --------------------------------------------------
# 7. FINAL WEIGHTED SCORE
# --------------------------------------------------

def calculate_final_score(
    semantic_score,
    keyword_score,
    recency_score
):
    """
    Final score =
        70% semantic similarity
      + 20% keyword relevance
      + 10% recency
    """

    final_score = (
        SEMANTIC_WEIGHT * semantic_score
        + KEYWORD_WEIGHT * keyword_score
        + RECENCY_WEIGHT * recency_score
    )

    return final_score


# --------------------------------------------------
# 8. SAVE RESULTS
# --------------------------------------------------

def save_results(results):
    fields = [
        "query_id",
        "search_query",
        "rank",
        "paper_id",
        "title",
        "doi",
        "abstract",
        "keywords",
        "year",
        "url",
        "source",
        "journal",
        "publication_type",
        "semantic_score",
        "keyword_score",
        "recency_score",
        "final_score",
        "final_score_percent"
    ]

    # Save all ranked papers as CSV
    with open(
        OUTPUT_CSV,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    # Save all ranked papers as JSON
    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(results, file, indent=4, ensure_ascii=False)

    # Save the top N papers for every query
    top_results = [
        result for result in results
        if result["rank"] <= TOP_N
    ]

    with open(
        TOP_N_CSV,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(top_results)

    print("\nOutput files created:")
    print(f"1. {OUTPUT_CSV.name}")
    print(f"2. {OUTPUT_JSON.name}")
    print(f"3. {TOP_N_CSV.name}")


# --------------------------------------------------
# 9. MAIN SEMANTIC SEARCH PROGRAM
# --------------------------------------------------

def main():
    print("=" * 60)
    print("ResearchMate - Semantic Search and Weighted Ranking")
    print("=" * 60)

    papers = load_papers()
    queries = load_queries()

    # Remove records that have no useful paper text
    valid_papers = [
        paper for paper in papers
        if (
            clean_text(paper.get("title"))
            or clean_text(paper.get("abstract"))
            or clean_text(paper.get("keywords"))
        )
    ]

    if not valid_papers:
        raise ValueError(
            "No papers with usable titles, abstracts, or keywords."
        )

    print(f"\nPapers loaded: {len(papers)}")
    print(f"Papers with usable text: {len(valid_papers)}")
    print(f"Queries loaded: {len(queries)}")

    print("\nLoading embedding model...")
    model = SentenceTransformer(MODEL_NAME)

    # Generate paper embeddings once, then reuse them
    paper_texts = [
        get_paper_text(paper)
        for paper in valid_papers
    ]

    print("\nGenerating paper embeddings...")

    paper_embeddings = model.encode(
        paper_texts,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    all_results = []

    # Process every query in queries.csv
    for query_number, query_row in enumerate(queries, start=1):

        query_id = clean_text(query_row.get("query_id"))
        query_text = clean_text(query_row.get("query"))

        print(
            f"\nProcessing query {query_number}/{len(queries)}: "
            f"{query_id} - {query_text}"
        )

        # Generate query embedding
        query_embedding = model.encode(
            [query_text],
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        # Calculate cosine similarity against all papers
        similarities = cosine_similarity(
            query_embedding,
            paper_embeddings
        )[0]

        query_results = []

        for index, paper in enumerate(valid_papers):

            # 1. Semantic similarity score
            # Clamp to 0-1 for the weighted formula
            semantic_score = max(
                0.0,
                min(1.0, float(similarities[index]))
            )

            # 2. Keyword relevance score
            keyword_score = calculate_keyword_score(
                query_text,
                paper
            )

            # 3. Recency score
            recency_score = calculate_recency_score(paper)

            # 4. Calculate the weighted final score
            final_score = calculate_final_score(
                semantic_score,
                keyword_score,
                recency_score
            )

            result = {
                "query_id": query_id,
                "search_query": query_text,
                "paper_id": clean_text(paper.get("paper_id")),
                "title": clean_text(paper.get("title")),
                "doi": clean_text(paper.get("doi")),
                "abstract": clean_text(paper.get("abstract")),
                "keywords": clean_text(paper.get("keywords")),
                "year": clean_text(paper.get("year")),
                "url": clean_text(paper.get("url")),
                "source": clean_text(paper.get("source")),
                "journal": clean_text(paper.get("journal")),
                "publication_type": clean_text(
                    paper.get("publication_type")
                ),
                "semantic_score": round(semantic_score, 4),
                "keyword_score": round(keyword_score, 4),
                "recency_score": round(recency_score, 4),
                "final_score": round(final_score, 4),
                "final_score_percent": round(
                    final_score * 100, 2
                )
            }

            query_results.append(result)

        # Sort by weighted final score, highest first
        query_results.sort(
            key=lambda item: item["final_score"],
            reverse=True
        )

        # Assign ranks separately for each query
        for rank, result in enumerate(query_results, start=1):
            result["rank"] = rank

        all_results.extend(query_results)

        if query_results:
            best = query_results[0]

            print(f"  Papers ranked: {len(query_results)}")
            print(f"  Top result: {best['title']}")
            print(f"  Semantic score: {best['semantic_score']}")
            print(f"  Keyword score: {best['keyword_score']}")
            print(f"  Recency score: {best['recency_score']}")
            print(f"  Final score: {best['final_score']}")
            print(f"  Final score (%): {best['final_score_percent']}%")

    # Save all results after processing all queries
    save_results(all_results)

    print("\n" + "=" * 60)
    print("SEMANTIC SEARCH AND RANKING COMPLETED")
    print("=" * 60)
    print(f"Queries processed: {len(queries)}")
    print(f"Total ranked rows: {len(all_results)}")
    print(f"Ranking formula: 70% + 20% + 10%")
    print("Ranking basis: Weighted final score")


if __name__ == "__main__":
    main()