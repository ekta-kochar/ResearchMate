import unittest

from researchmate.deduplication import deduplicate_paper_records


def paper(source, source_id, **overrides):
    record = {
        "query": "research",
        "source": source,
        "source_id": source_id,
        "title": "A study of robust scientific methods",
        "authors": ["Jane Smith"],
        "abstract": None,
        "keywords": [],
        "year": "2024",
        "doi": "10.1234/shared",
        "url": None,
    }
    record.update(overrides)
    return record


class TestPaperDeduplication(unittest.TestCase):
    def test_doi_duplicates_merge_metadata_and_provenance(self):
        first = paper("PubMed", "123", keywords=["health"], abstract=None)
        second = paper(
            "Crossref",
            "10.1234/shared",
            keywords=["health", "methods"],
            abstract="A useful abstract.",
            provenance={
                "abstract": [
                    {"source": "Crossref", "source_id": "10.1234/shared", "method": "source_record"}
                ]
            },
        )

        result = deduplicate_paper_records([first, second])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["abstract"], "A useful abstract.")
        self.assertEqual(result[0]["keywords"], ["health", "methods"])
        self.assertIn("pmid", result[0]["identifiers"])
        self.assertTrue(any(item["source"] == "Crossref" for item in result[0]["provenance"]["abstract"]))

    def test_different_dois_do_not_merge_even_with_same_title(self):
        first = paper("Crossref", "a", doi="10.1234/one")
        second = paper("Crossref", "b", doi="10.1234/two")

        self.assertEqual(len(deduplicate_paper_records([first, second])), 2)

    def test_title_fallback_requires_year_and_first_author(self):
        first = paper("PubMed", "1", doi=None)
        same = paper("OpenAlex", "W2", doi=None)
        wrong_author = paper("OpenAlex", "W3", doi=None, authors=["Other Author"])
        wrong_year = paper("OpenAlex", "W4", doi=None, year="2020")

        result = deduplicate_paper_records([first, same, wrong_author, wrong_year])

        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
