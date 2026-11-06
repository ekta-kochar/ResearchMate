import unittest

from researchmate.api_04_europepmc import parse_europepmc_record
from researchmate.api_05_openalex import parse_openalex_work
from researchmate.schema import validate_paper_record


class TestNewApiAdapters(unittest.TestCase):
    def test_europepmc_record_maps_metadata_and_provenance(self):
        paper = parse_europepmc_record(
            {
                "pmid": "12345",
                "pmcid": "PMC123",
                "doi": "10.1234/example",
                "title": "A paper",
                "authorString": "Jane Smith, John Doe",
                "abstractText": "An abstract.",
                "firstPublicationDate": "2025-01-10",
            },
            "test query",
        )

        validate_paper_record(paper)
        self.assertEqual(paper["source_id"], "12345")
        self.assertEqual(paper["authors"], ["Jane Smith", "John Doe"])
        self.assertEqual(paper["year"], "2025")
        self.assertEqual(paper["identifiers"]["pmcid"], "PMC123")
        self.assertEqual(paper["provenance"]["abstract"][0]["source"], "Europe PMC")

    def test_openalex_reconstructs_abstract_and_maps_work_identity(self):
        paper = parse_openalex_work(
            {
                "id": "https://openalex.org/W123",
                "doi": "https://doi.org/10.1234/example",
                "title": "A paper",
                "publication_year": 2024,
                "abstract_inverted_index": {"abstract": [2], "An": [0], "is": [1]},
                "authorships": [
                    {"author": {"display_name": "Jane Smith"}},
                ],
                "keywords": [{"display_name": "research"}],
                "primary_location": None,
            },
            "test query",
        )

        validate_paper_record(paper)
        self.assertEqual(paper["abstract"], "An is abstract")
        self.assertEqual(paper["source_id"], "W123")
        self.assertEqual(paper["doi"], "10.1234/example")
        self.assertEqual(paper["url"], "https://openalex.org/W123")

    def test_openalex_handles_missing_abstract_index(self):
        paper = parse_openalex_work({"id": "https://openalex.org/W1"}, "query")

        self.assertIsNone(paper["abstract"])
        validate_paper_record(paper)


if __name__ == "__main__":
    unittest.main()
