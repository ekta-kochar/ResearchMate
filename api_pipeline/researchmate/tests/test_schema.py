
import unittest

from researchmate.schema import validate_paper_record


class TestPaperSchema(unittest.TestCase):
    def setUp(self):
        self.paper = {
            "query": "machine learning healthcare",
            "source": "PubMed",
            "source_id": "12345",
            "title": "Machine Learning in Healthcare",
            "authors": ["Jane Smith", "John Doe"],
            "abstract": "A study of machine learning.",
            "keywords": ["machine learning", "healthcare"],
            "year": "2025",
            "doi": "10.1234/example",
            "url": "https://example.com/paper",
        }

    def test_valid_record(self):
        validate_paper_record(self.paper)

    def test_missing_field(self):
        paper = self.paper.copy()
        del paper["title"]

        with self.assertRaisesRegex(ValueError, "Missing paper fields"):
            validate_paper_record(paper)

    def test_optional_metadata_can_be_none(self):
        paper = self.paper.copy()
        paper["abstract"] = None
        paper["doi"] = None
        paper["year"] = None

        validate_paper_record(paper)

    def test_query_cannot_be_empty(self):
        paper = self.paper.copy()
        paper["query"] = "   "

        with self.assertRaisesRegex(ValueError, "query"):
            validate_paper_record(paper)

    def test_authors_must_be_a_list(self):
        paper = self.paper.copy()
        paper["authors"] = "Jane Smith"

        with self.assertRaisesRegex(TypeError, "authors"):
            validate_paper_record(paper)

    def test_author_items_must_be_strings(self):
        paper = self.paper.copy()
        paper["authors"] = ["Jane Smith", 123]

        with self.assertRaisesRegex(TypeError, "Every item"):
            validate_paper_record(paper)

    def test_year_must_be_string_or_none(self):
        paper = self.paper.copy()
        paper["year"] = 2025

        with self.assertRaisesRegex(TypeError, "year"):
            validate_paper_record(paper)

    def test_legacy_record_remains_valid_without_extensions(self):
        validate_paper_record(self.paper)

    def test_identifier_and_field_provenance_extensions(self):
        paper = self.paper.copy()
        paper.update(
            {
                "canonical_id": "doi:10.1234/example",
                "identifiers": {"doi": "10.1234/example", "pmid": "12345"},
                "provenance": {
                    "abstract": [
                        {
                            "source": "Europe PMC",
                            "source_id": "12345",
                            "method": "pmid_exact",
                            "retrieved_at": "2026-11-04T12:00:00Z",
                        }
                    ]
                },
            }
        )

        validate_paper_record(paper)

    def test_identifier_values_must_be_non_empty_strings(self):
        paper = self.paper.copy()
        paper["identifiers"] = {"doi": "  "}

        with self.assertRaisesRegex(ValueError, "non-empty"):
            validate_paper_record(paper)

    def test_provenance_requires_source_and_method(self):
        paper = self.paper.copy()
        paper["provenance"] = {"abstract": [{"source": "Crossref"}]}

        with self.assertRaisesRegex(ValueError, "method"):
            validate_paper_record(paper)


if __name__ == "__main__":
    unittest.main()
