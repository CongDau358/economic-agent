"""Tests for retrieval governance enforcement."""

import unittest

from backend.services.retrieval_governance import (
    apply_retrieval_governance,
    assess_retrieval,
    rerank_and_deduplicate,
    source_trust,
)


class RetrievalGovernanceTests(unittest.TestCase):
    def test_source_trust_prefers_pdf_over_news(self):
        self.assertGreater(source_trust("pdf"), source_trust("news"))
        self.assertLess(source_trust("unknown"), source_trust("text"))

    def test_deduplicate_removes_near_duplicate_chunks(self):
        contexts = [
            {"text": "Revenue increased 12 percent in Q1.", "source_type": "pdf", "company": "Acme"},
            {"text": "Revenue increased 12 percent in Q1.", "source_type": "news", "company": "Acme"},
            {"text": "Policy support expanded for manufacturing.", "source_type": "pdf", "company": "Acme"},
        ]
        governed = rerank_and_deduplicate(contexts, distances=[0.2, 0.25, 0.5])
        self.assertEqual(len(governed), 2)
        self.assertGreaterEqual(governed[0].trust_score, governed[1].trust_score)

    def test_strategic_question_insufficient_with_single_chunk(self):
        contexts = [{"text": "Costs rose.", "source_type": "news", "company": "Acme"}]
        governed, assessment = apply_retrieval_governance(
            "What are the key risks for Acme next quarter?",
            contexts,
            distances=[0.3],
        )
        self.assertEqual(assessment.status, "INSUFFICIENT_DATA")
        self.assertLessEqual(len(governed), 1)

    def test_low_trust_adds_warning_but_may_answer_factual(self):
        contexts = [
            {"text": "Revenue up 5%.", "source_type": "news", "company": "Acme"},
            {"text": "Margin stable.", "source_type": "news", "company": "Acme"},
        ]
        governed, assessment = apply_retrieval_governance(
            "What was revenue change?",
            contexts,
            distances=[0.15, 0.2],
        )
        self.assertIn(assessment.status, {"OK", "LOW_CONFIDENCE"})
        self.assertTrue(any("low-trust" in w.lower() for w in assessment.warnings))

    def test_assess_empty_returns_insufficient(self):
        assessment = assess_retrieval("What is revenue?", [])
        self.assertEqual(assessment.status, "INSUFFICIENT_DATA")
        self.assertEqual(assessment.confidence_band, "INSUFFICIENT")


if __name__ == "__main__":
    unittest.main()
