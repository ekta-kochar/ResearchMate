# ResearchMate API pipeline

This folder contains the reusable paper search, cleanup, enrichment,
deduplication, export, and persistent ChromaDB storage code.

## Structure

```text
api_pipeline/
├── researchmate/
│   ├── __init__.py
│   ├── api_01_pubmed.py
│   ├── api_02_arxiv.py
│   ├── api_03_crossref.py
│   ├── api_04_europepmc.py
│   ├── api_05_openalex.py
│   ├── queries_10.py
│   ├── pipeline_20.py
│   ├── export_30.py
│   ├── schema.py
│   ├── normalization.py
│   ├── enrichment.py
│   ├── deduplication.py
│   ├── vector_store.py
│   └── tests/
│       ├── test_api_adapters.py
│       ├── test_deduplication.py
│       ├── test_enrichment.py
│       ├── test_export.py
│       ├── test_normalization.py
│       ├── test_schema.py
│       ├── test_vector_store.py
│       └── test_pipeline.py
├── run_example.py
├── run_25_queries.py
├── app.py
├── requirements-app.txt
├── requirements.txt
└── README.md
```

## Install

From this folder:

```bash
pip install -r requirements.txt
```

## Use one API directly

```python
from researchmate import search_pubmed

results = search_pubmed("climate change agriculture", max_results=5)
```

The package also provides `search_europepmc` and `search_openalex`. They can be
called directly or selected through `search_all_sources`, for example:

```python
results = search_all_sources(
    "climate change agriculture",
    max_results=5,
    sources=("pubmed", "arxiv", "crossref", "europepmc", "openalex"),
)
```

These two adapters include optional `canonical_id`, `identifiers`, and
field-level `provenance` values in addition to the shared paper fields.
Records returned through `search_all_sources` also pass through a shared
standardization step that cleans text, DOI, year, author lists, and keywords;
it retains source evidence and records the normalization event in provenance.
If an abstract is missing, the pipeline tries exact identifiers first and then
requires a very close title match with a compatible publication year. Recovered
abstracts retain the provider, record ID, match method, and retrieval time in
field-level provenance; unmatched abstracts remain empty.
The combined results are then deduplicated by DOI or matching provider IDs. A
fallback merge requires the same normalized title, publication year, and first
author. Authors, keywords, identifiers, and provenance are combined; conflicting
metadata values are kept in `metadata_conflicts` for review.

## Persistent ChromaDB storage

Use Python 3.14 for the ChromaDB dependency in this environment.
Chroma's default embedding stack depends on `onnxruntime`, which currently
does not publish a Python 3.15 Windows wheel. The `chromadb` requirement is
limited to the compatible 1.x API range to avoid pip resolving obsolete major
versions.

Install the added dependency from this folder:

```bash
pip install -r requirements.txt
```

Search the APIs, validate and deduplicate the results, then store papers and
their embeddings in the local persistent collection:

```python
from researchmate import ChromaPaperStore, search_all_sources

papers = search_all_sources("climate change agriculture", max_results=2)
with ChromaPaperStore() as store:  # persists under api_pipeline/chroma_db
    print(f"Stored {store.upsert_records(papers)} unique papers")

    for match in store.query_papers("agriculture under climate stress", n_results=3):
        paper = match["record"]
        print(paper["title"], match["distance"])
```

Chroma uses its default embedding function unless one is injected. Its first
use may download the embedding model. The local database keeps paper records,
provenance, metadata conflicts, searchable text, and generated embeddings.
Re-running an upsert updates the same canonical ID.
The database directory is ignored by Git. Chroma's local `PersistentClient` is
intended for local development; a server-backed client is the documented choice
for a production deployment.

### View the local database

The read-only browser displays papers in a table, lets you filter by source,
search by semantic similarity, and inspect an individual record's abstract,
keywords, identifiers, provenance, and metadata conflicts. It reads the local
`chroma_db` collection and does not add, edit, or delete records.

Install the viewer dependency once, from this folder:

```powershell
python -m pip install -r requirements-viewer.txt
```

Then start the viewer:

```powershell
python -m streamlit run view_chroma.py
```

Streamlit opens the viewer in your browser. In VS Code, leave the terminal
running while browsing; press `Ctrl+C` in that terminal to stop it. If the
viewer reports an empty collection, first run the paper search/storage workflow
so records are upserted into `api_pipeline/chroma_db`.

### Run the ResearchMate prototype

The chat prototype combines the local paper collection with the teammate's
chat interface and weighted ranking approach. It searches the existing
`researchmate_papers` collection, reranks the retrieved records using 70%
semantic similarity, 20% keyword overlap, and 10% recency, then displays the
ranked papers. If a Groq key is configured, it also drafts an answer using the
top five records' abstracts and asks the model to cite them as `[1]`, `[2]`,
and so on. Without a key, paper search and ranking still work.

By default, each new question is also searched across PubMed, arXiv, Crossref,
Europe PMC, and OpenAlex. Returned records pass through the existing
standardization, abstract recovery, and deduplication pipeline, then are
upserted into `researchmate_papers` before the local search and ranking run.
The source APIs used here do not require user API keys. A second Chroma
collection, `researchmate_online_query_cache`, remembers successful exact
queries so the same question does not repeat all five online searches. The
app still searches ChromaDB locally each time. Use **Refresh online results
even for cached questions** in the sidebar to bypass that cache; turn off
**Search online sources automatically** to use only the local database.

Install the app dependencies from this folder:

```powershell
python -m pip install -r requirements-app.txt
```

Optionally create `api_pipeline/.env` with your own Groq credentials:

```text
GROQ_API_KEY=your_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

The `.env` file is ignored by Git. Then launch the app:

```powershell
python -m streamlit run app.py
```

The app writes newly retrieved online records and exact-query cache entries to
ChromaDB. It does not delete records. Its ranking formula is a first prototype
and should be checked against manually judged queries before being treated as
validated.

## Verification results

- The last verified offline suite passed: **31 tests** covering adapters,
  schema, standardization, abstract recovery, deduplication, CSV export, and
  Chroma persistence/upsert/query behavior. Two pipeline orchestration tests
  have since been added and still need a run.
- A live search smoke check returned one record from each of PubMed, arXiv,
  Crossref, Europe PMC, and OpenAlex. The five returned records had abstracts
  and provenance.
- The Chroma persistence tests use a deterministic local test embedder. A
  separate temporary-database smoke check also succeeded with Chroma's default
  embedding model and semantic query.

Run the tests from this folder with:

```bash
python -m unittest discover -s researchmate/tests -v
```

## Search all current APIs

```python
from researchmate import search_all_sources, results_to_dataframe

results = search_all_sources("climate change agriculture", max_results=5)
df = results_to_dataframe(results)
print(df)
```

## Run the 25-query experiment

```bash
python run_25_queries.py
```

This creates:

- `researchmate_25_queries.csv` — all normalized paper records
- `researchmate_api_comparison.csv` — result counts by query and API
- `chroma_db/` — persistent validated records and their embeddings

## Add another API later

Create the next numbered module, for example:

```text
researchmate/api_06_newsource.py
```

Make its search function return the same fields:

```python
{
    "query": ..., 
    "source": ...,
    "source_id": ...,
    "title": ...,
    "authors": [...],
    "abstract": ...,
    "keywords": [...],
    "year": ...,
    "doi": ...,
    "url": ...,
}
```

Then add the search function to `SEARCHERS` in `pipeline_20.py`, export it from
`__init__.py`, and add a parser test using a representative fixture.
