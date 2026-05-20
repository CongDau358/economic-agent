import unittest

from backend.ingestion.chunking.strategy import (
    ChunkType,
    merge_chunks,
    split_semantic_text,
    infer_chunk_type,
    build_semantic_chunks,
)
from backend.ingestion.chunking.strategy import PROFILES


SAMPLE_WITH_TABLE = """
Revenue grew 10 percent in the quarter.

[TABLE]
Metric | Q1 | Q2
Revenue | 100 | 110
Profit | 20 | 22
[/TABLE]

Operating cash flow improved.
"""


class ChunkingStrategyTests(unittest.TestCase):
    def test_table_not_split_across_chunks(self):
        parts = split_semantic_text(SAMPLE_WITH_TABLE, PROFILES["financial_report"])
        table_parts = [p for p in parts if "[TABLE]" in p]
        self.assertEqual(len(table_parts), 1)
        self.assertIn("Profit | 20 | 22", table_parts[0])

    def test_infer_financial_metric_type(self):
        self.assertEqual(
            infer_chunk_type("Net income and revenue increased in the income statement"),
            ChunkType.FINANCIAL_METRIC,
        )

    def test_infer_news_event_type(self):
        self.assertEqual(
            infer_chunk_type("[NEWS | Topic: policy] Central bank policy update moved markets"),
            ChunkType.NEWS_EVENT,
        )

    def test_merge_avoids_tiny_chunks(self):
        profile = PROFILES["news"]
        merged = merge_chunks(["Short.", "Another short line."], profile)
        self.assertEqual(len(merged), 1)

    def test_build_semantic_chunks_with_header(self):
        chunks = build_semantic_chunks(
            doc_id="doc",
            body="Policy update affects trade and market sentiment.",
            profile_name="news",
            context_header="[NEWS | Topic: policy]",
            source_hint="policy",
        )
        self.assertGreater(len(chunks), 0)
        self.assertTrue(chunks[0].text.startswith("[NEWS"))


if __name__ == "__main__":
    unittest.main()
