import unittest

from backend.rag.embedding.normalizer import normalize_chunk_text, normalize_query_text


class EmbeddingPipelineTests(unittest.TestCase):
    def test_normalize_preserves_numbers_and_context(self):
        text = "Revenue grew 12.5% to $1,200bn in Manufacturing."
        meta = {
            "company": "Acme",
            "sector": "Manufacturing",
            "chunk_type": "financial_metric",
            "financial_priorities": "revenue,growth",
        }
        out = normalize_chunk_text(text, meta)
        self.assertIn("12.5", out)
        self.assertIn("company:Acme", out)
        self.assertIn("metrics:revenue,growth", out)
        self.assertIn("Revenue grew", out)

    def test_normalize_query(self):
        q = normalize_query_text("  What is   Q1 2024  revenue?  ")
        self.assertIn("2024", q)
        self.assertNotIn("  ", q)

    def test_prepare_skips_empty(self):
        try:
            from backend.rag.embedding.pipeline import EmbeddingPipeline
        except ImportError:
            self.skipTest("langchain not installed")
        pipeline = EmbeddingPipeline(persist_directory="/tmp/econ_test_embed")
        prepared, skipped, _ = pipeline.prepare_records([{"text": "short"}])
        self.assertEqual(len(prepared), 0)
        self.assertEqual(skipped, 1)

    def test_embed_and_store_fake(self):
        try:
            from backend.rag.embedding.pipeline import EmbeddingPipeline
        except ImportError:
            self.skipTest("langchain not installed")
        pipeline = EmbeddingPipeline(persist_directory="/tmp/econ_test_embed_store")
        records = [
            {
                "text": "[Section: Revenue | Pages: 1]\n\nRevenue increased 12 percent to 1.2 billion USD.",
                "chunk_id": "c1",
                "company": "Acme",
                "sector": "Tech",
                "source_type": "pdf",
                "chunk_type": "financial_metric",
            }
        ]
        result = pipeline.embed_and_store(records)
        self.assertEqual(result.embedded_count, 1)
        hits = pipeline.query_normalized("Acme revenue growth", top_k=1)
        self.assertEqual(len(hits), 1)


if __name__ == "__main__":
    unittest.main()
