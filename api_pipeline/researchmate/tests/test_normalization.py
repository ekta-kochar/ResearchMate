import unittest

from researchmate.normalization import standardize_paper_record
from researchmate.schema import validate_paper_record


class TestPaperNormalization(unittest.TestCase):
    def setUp(self):
        self.paper = {
            "query": "  machine learning  ",
            "source": "Crossref",
            "source_id": "  https://doi.org/10.1234/ABC ",
            "title": "  A <i>study</i> &amp; its results  ",
            "authors": [" Jane Smith ", "", "John   Doe"],
            "abstract": " An   abstract. ",
            "keywords": "['Machine learning', ' Health ', 'machine learning']",
            "year": "Published: 2024-03-01",
            "doi": " DOI: 10.1234/ABC. ",
            "url": " https://example.org/paper ",
        }

    def test_standardizes_text_doi_year_authors_and_keywords(self):
        paper = standardize_paper_record(self.paper)

        self.assertEqual(paper["title"], "A study & its results")
        self.assertEqual(paper["authors"], ["Jane Smith", "John Doe"])
        self.assertEqual(paper["keywords"], ["Machine learning", "Health"])
        self.assertEqual(paper["year"], "2024")
        self.assertEqual(paper["doi"], "10.1234/abc")
        self.assertEqual(paper["canonical_id"], "doi:10.1234/abc")
        validate_paper_record(paper)

    def test_normalization_does_not_mutate_the_input(self):
        original_keywords = self.paper["keywords"]

        standardize_paper_record(self.paper)

        self.assertEqual(self.paper["keywords"], original_keywords)
        self.assertNotIn("provenance", self.paper)

    def test_keyword_string_with_separators_is_cleaned(self):
        paper = dict(self.paper, keywords="climate; agriculture | climate\nsoil")

        normalized = standardize_paper_record(paper)

        self.assertEqual(normalized["keywords"], ["climate", "agriculture", "soil"])

    def test_field_provenance_is_added(self):
        paper = standardize_paper_record(self.paper)

        event = paper["provenance"]["abstract"][-1]
        self.assertEqual(event["method"], "standardized")
        self.assertEqual(event["source"], "Crossref")

    def test_repeated_standardization_does_not_duplicate_provenance(self):
        once = standardize_paper_record(self.paper)
        twice = standardize_paper_record(once)

        self.assertEqual(
            len(twice["provenance"]["abstract"]),
            len(once["provenance"]["abstract"]),
        )

    def test_standardization_collapses_existing_duplicate_events(self):
        paper = standardize_paper_record(self.paper)
        event = paper["provenance"]["abstract"][-1]
        paper["provenance"]["abstract"].append(dict(event))

        normalized = standardize_paper_record(paper)

        self.assertEqual(
            sum(entry["method"] == "standardized" for entry in normalized["provenance"]["abstract"]),
            1,
        )


if __name__ == "__main__":
    unittest.main()
