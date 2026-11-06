import unittest
from unittest.mock import patch

from researchmate.pipeline_20 import SEARCHERS, search_all_sources


def make_record(source, source_id, abstract, doi="10.1234/shared"):
    return {
        "query": "pipeline test",
        "source": source,
        "source_id": source_id,
        "title": "A shared paper about pipeline testing",
        "authors": ["A Researcher"],
        "abstract": abstract,
        "keywords": ["testing"],
        "year": "2025",
        "doi": doi,
        "url": None,
    }


class TestSearchPipeline(unittest.TestCase):
    def test_all_five_sources_are_registered(self):
        self.assertEqual(
            set(SEARCHERS),
            {"pubmed", "arxiv", "crossref", "europepmc", "openalex"},
        )

    def test_pipeline_enriches_and_deduplicates_mocked_results(self):
        source_results = {
            "pubmed": [make_record("PubMed", "12345", None)],
            "crossref": [
                make_record("Crossref", "10.1234/shared", "A verified abstract.")
            ],
        }
        searchers = {
            key: (lambda query, max_results, records=records: records)
            for key, records in source_results.items()
        }

        with patch.dict("researchmate.pipeline_20.SEARCHERS", searchers, clear=True):
            result = search_all_sources(
                "pipeline test", max_results=1, sources=("pubmed", "crossref")
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["abstract"], "A verified abstract.")
        abstract_methods = {
            entry["method"] for entry in result[0]["provenance"]["abstract"]
        }
        self.assertIn("exact_identifier", abstract_methods)
        self.assertIn("Crossref", {entry["source"] for entry in result[0]["provenance"]["abstract"]})


if __name__ == "__main__":
    unittest.main()
