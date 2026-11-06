import gc
import importlib.util
import tempfile
import unittest

from researchmate.vector_store import ChromaPaperStore


class DeterministicEmbeddingFunction:
    """Small offline embedding function for Chroma storage tests."""

    @staticmethod
    def name():
        return "researchmate_test_embedding"

    @staticmethod
    def build_from_config(config):
        return DeterministicEmbeddingFunction()

    def get_config(self):
        return {}

    def is_legacy(self):
        return False

    def embed_query(self, input):
        return self(input)

    def default_space(self):
        return "cosine"

    def supported_spaces(self):
        return ["cosine", "l2", "ip"]

    def __call__(self, input):
        return [
            [float(len(text) % 23 + 1), float(sum(map(ord, text)) % 97 + 1), 1.0]
            for text in input
        ]


@unittest.skipUnless(importlib.util.find_spec("chromadb"), "chromadb is not installed")
class TestChromaPaperStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.stores = []
        self.embedding_function = DeterministicEmbeddingFunction()
        self.paper = {
            "query": "machine learning healthcare",
            "source": "PubMed",
            "source_id": "12345",
            "title": "Machine Learning in Healthcare",
            "authors": ["Jane Smith"],
            "abstract": "A study of machine learning in healthcare.",
            "keywords": ["machine learning", "healthcare"],
            "year": "2025",
            "doi": "10.1234/example",
            "url": "https://example.com/paper",
        }

    def tearDown(self):
        for store in self.stores:
            store.close()
        gc.collect()
        self.temp_dir.cleanup()

    def make_store(self):
        store = ChromaPaperStore(
            persist_directory=self.temp_dir.name,
            collection_name="researchmate_test",
            embedding_function=self.embedding_function,
        )
        self.stores.append(store)
        return store

    def test_upsert_query_and_persistence_round_trip(self):
        store = self.make_store()

        self.assertEqual(store.upsert_records([self.paper]), 1)
        self.assertEqual(store.count(), 1)
        matches = store.query_papers("healthcare research", n_results=1)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["record"]["doi"], self.paper["doi"])
        self.assertIsInstance(matches[0]["distance"], (int, float))
        self.assertEqual(store.upsert_records([self.paper]), 1)
        store.close()

        reopened = self.make_store()
        records = reopened.get_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], self.paper["title"])

    def test_invalid_record_is_rejected_before_storage(self):
        store = self.make_store()
        invalid = dict(self.paper)
        invalid.pop("title")

        with self.assertRaisesRegex(ValueError, "Missing paper fields"):
            store.upsert_records([invalid])


if __name__ == "__main__":
    unittest.main()
