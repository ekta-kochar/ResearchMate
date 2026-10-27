
import unittest

from researchmate.export_30 import COLUMNS, results_to_dataframe


class TestResearchMateExport(unittest.TestCase):
    def setUp(self):
        self.paper = {
            "query": "machine learning healthcare",
            "source": "PubMed",
            "source_id": "12345",
            "title": "Machine Learning in Healthcare",
            "authors": ["Jane Smith"],
            "abstract": None,
            "keywords": ["machine learning"],
            "year": "2025",
            "doi": None,
            "url": "https://example.com/paper",
        }

    def test_empty_results_preserve_all_columns(self):
        df = results_to_dataframe([])

        self.assertEqual(df.columns.tolist(), COLUMNS)
        self.assertEqual(len(df), 0)

    def test_valid_record_converts_to_dataframe(self):
        df = results_to_dataframe([self.paper])

        self.assertEqual(len(df), 1)
        self.assertEqual(df.columns.tolist(), COLUMNS)
        self.assertEqual(df.iloc[0]["title"], self.paper["title"])

    def test_invalid_record_is_rejected(self):
        paper = self.paper.copy()
        del paper["title"]

        with self.assertRaisesRegex(
            ValueError, "Invalid paper record at index 0"
        ):
            results_to_dataframe([paper])


if __name__ == "__main__":
    unittest.main()
