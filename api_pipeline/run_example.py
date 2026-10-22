"""Small example: search one query across all current APIs."""

from researchmate import results_to_dataframe, search_all_sources

query = "climate change agriculture"
results = search_all_sources(query, max_results=5)
df = results_to_dataframe(results)

print(df[["source", "title", "year", "doi"]])
