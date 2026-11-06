# ResearchMate

ResearchMate is an academic-paper discovery and indexing project. Its reusable
Python pipeline searches PubMed, arXiv, Crossref, Europe PMC, and OpenAlex;
standardizes records; recovers abstracts when a strict match is available;
deduplicates records while retaining provenance; and stores papers and
embeddings in a persistent ChromaDB collection.

## Repository layout

```text
ResearchMate/
├── api_pipeline/                 # Reusable Python package and pipeline
│   ├── researchmate/              # API clients, schema, pipeline, storage
│   │   └── tests/                 # Offline unit and persistence tests
│   ├── run_example.py             # Small multi-source search example
│   ├── run_25_queries.py          # Batch retrieval, CSV export, Chroma upsert
│   ├── requirements.txt
│   └── README.md                  # Setup, API, storage, and test instructions
├── model_exploration/             # Cleaning, deduplication, embedding notebooks
└── preliminary_tests/             # Earlier API experiments and sample exports
```

## Quick start

Use Python 3.14 for the ChromaDB dependency on Windows. From `api_pipeline`:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s researchmate/tests -v
python run_example.py
```

See [api_pipeline/README.md](api_pipeline/README.md) for database usage and
batch indexing. The local Chroma collection is written to
`api_pipeline/chroma_db/`, which is excluded from Git.
