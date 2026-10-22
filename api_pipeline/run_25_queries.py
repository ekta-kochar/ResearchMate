"""Run the default 25-query experiment and save outputs."""

from researchmate import (
    DEFAULT_QUERIES,
    query_source_comparison,
    results_to_dataframe,
    run_query_batch,
)

results = run_query_batch(
    DEFAULT_QUERIES,
    max_results=5,
    sources=("pubmed", "arxiv", "crossref"),
    delay_between_queries=5,
)

df = results_to_dataframe(results)
df.to_csv("researchmate_25_queries.csv", index=False)

comparison = query_source_comparison(df)
comparison.to_csv("researchmate_api_comparison.csv")

print("\nSaved researchmate_25_queries.csv")
print("Saved researchmate_api_comparison.csv")
print("\nResults by source:")
print(df["source"].value_counts())
