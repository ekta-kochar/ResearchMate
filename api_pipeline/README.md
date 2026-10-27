# ResearchMate modular API code

This folder restructures the original notebook into reusable Python modules.

## Why the filenames contain letters before numbers

Python modules cannot be imported normally when their filenames start with a digit. Therefore the API files use names such as `api_01_pubmed.py` rather than `01_pubmed.py`. They still sort numerically while remaining valid Python modules.

## Structure

```text
researchmate_modular/
├── researchmate/
│   ├── __init__.py
│   ├── api_01_pubmed.py
│   ├── api_02_arxiv.py
│   ├── api_03_crossref.py
│   ├── queries_10.py
│   ├── pipeline_20.py
│   └── export_30.py
├── run_example.py
├── run_25_queries.py
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

## Add another API later

Create another module such as:

```text
researchmate/api_04_openalex.py
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

Then add that search function to `SEARCHERS` in `pipeline_20.py` and export it from `__init__.py`.
