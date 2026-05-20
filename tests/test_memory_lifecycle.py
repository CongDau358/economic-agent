import unittest
from datetime import datetime, timezone

from backend.memory.lifecycle import (
    apply_post_validation_lifecycle,
    lifecycle_rank_multiplier,
    resolve_lifecycle_state,
)


class MemoryLifecycleTests(unittest.TestCase):
    def test_active_recent_document(self):
        decision = resolve_lifecycle_state(
            {"source": "pdf", "year": str(2025), "lifecycle_state": ""}
        )
        self.assertEqual(decision.state, "active")
        self.assertEqual(decision.rank_multiplier, 1.0)

    def test_review_old_document(self):
        year = str(datetime.now(timezone.utc).year - 4)
        decision = resolve_lifecycle_state({"source": "pdf", "year": year})
        self.assertEqual(decision.state, "review")

    def test_archived_very_old_document(self):
        year = str(datetime.now(timezone.utc).year - 6)
        decision = resolve_lifecycle_state({"source": "pdf", "year": year})
        self.assertEqual(decision.state, "archived")
        self.assertLess(lifecycle_rank_multiplier({"source": "pdf", "year": "2010"}), 0.5)

    def test_post_validation_stamps_metadata(self):
        record = apply_post_validation_lifecycle(
            {
                "text": "sample " * 20,
                "company": "Acme",
                "industry": "Tech",
                "year": "2024",
                "source": "news",
                "document_type": "news_article",
                "chunk_id": "abc",
            }
        )
        self.assertIn("lifecycle_state", record)
        self.assertIn("retrieval_rank_multiplier", record)


if __name__ == "__main__":
    unittest.main()
