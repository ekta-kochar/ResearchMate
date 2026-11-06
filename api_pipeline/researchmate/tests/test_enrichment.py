import unittest

from researchmate.enrichment import recover_missing_abstracts


def paper(**overrides):
    record = {
        "query": "test query",
        "source": "PubMed",
        "source_id": "123",
        "title": "A reliable title for matching",
        "authors": ["A Researcher"],
        "abstract": None,
        "keywords": [],
        "year": "2024",
        "doi": "10.1234/test",
        "url": "https://example.org/paper",
    }
    record.update(overrides)
    return record


class TestAbstractRecovery(unittest.TestCase):
    def test_recovers_abstract_from_exact_doi_and_records_provenance(self):
        candidate = paper(
            source="Crossref",
            source_id="10.1234/test",
            abstract="Recovered abstract.",
            identifiers={"doi": "10.1234/test"},
        )
        calls = []

        def lookup(query, max_results):
            calls.append(query)
            return [candidate]

        result = recover_missing_abstracts(
            [paper()], {"crossref": lookup}
        )[0]

        self.assertEqual(result["abstract"], "Recovered abstract.")
        self.assertEqual(result["provenance"]["abstract"][-1]["method"], "exact_identifier")
        self.assertTrue(calls)

    def test_does_not_accept_title_match_when_year_conflicts(self):
        candidate = paper(
            source="OpenAlex",
            source_id="W9",
            abstract="Wrong edition.",
            doi="10.9999/other",
            year="2020",
            identifiers={"openalex": "W9", "doi": "10.9999/other"},
        )
        result = recover_missing_abstracts(
            [paper(doi=None)],
            {"openalex": lambda query, max_results: [candidate]},
        )[0]

        self.assertIsNone(result["abstract"])

    def test_leaves_abstract_missing_when_no_strict_match_exists(self):
        candidate = paper(
            source="Europe PMC",
            source_id="999",
            abstract="Unrelated abstract.",
            title="A different work",
            doi="10.9999/other",
            identifiers={"pmid": "999", "doi": "10.9999/other"},
        )
        result = recover_missing_abstracts(
            [paper()],
            {"europepmc": lambda query, max_results: [candidate]},
        )[0]

        self.assertIsNone(result["abstract"])


if __name__ == "__main__":
    unittest.main()
