"""Tests for PDF processing pipeline (no binary PDF required)."""

import unittest

from backend.ingestion.pdf.chunker import chunk_sections, detect_financial_priorities
from backend.ingestion.pdf.cleaner import clean_extracted_text
from backend.ingestion.pdf.pipeline import infer_document_type
from backend.ingestion.pdf.sections import detect_sections


SAMPLE_REPORT = """
[PAGE 1]
ANNUAL REPORT 2024

## FINANCIAL HIGHLIGHTS

Revenue increased 12 percent to $1.2 billion.
Net income rose 8 percent.

[TABLE]
Item | 2024 | 2023
Revenue | 1200 | 1070
Net income | 180 | 165
[/TABLE]

[PAGE 2]
## CASH FLOW

Operating cash flow improved.
Debt ratio declined.
"""


class PdfPipelineTests(unittest.TestCase):
    def test_clean_preserves_table_blocks(self):
        cleaned = clean_extracted_text(SAMPLE_REPORT)
        self.assertIn("[TABLE]", cleaned)
        self.assertIn("Revenue | 1200", cleaned)

    def test_section_detection_finds_headings(self):
        cleaned = clean_extracted_text(SAMPLE_REPORT)
        sections = detect_sections(cleaned)
        titles = [s.title for s in sections]
        self.assertTrue(any("FINANCIAL" in t.upper() or "CASH" in t.upper() for t in titles))

    def test_financial_priorities_detected(self):
        priorities = detect_financial_priorities(SAMPLE_REPORT)
        self.assertIn("revenue", priorities)
        self.assertIn("profit", priorities)
        self.assertIn("cash_flow", priorities)
        self.assertIn("debt", priorities)

    def test_chunks_include_section_context(self):
        cleaned = clean_extracted_text(SAMPLE_REPORT)
        sections = detect_sections(cleaned)
        chunks = chunk_sections(sections, doc_id="test-doc")
        self.assertGreater(len(chunks), 0)
        self.assertIn("[Section:", chunks[0].text)

    def test_infer_annual_report_type(self):
        doc_type = infer_document_type(SAMPLE_REPORT, filename="acme_annual_report.pdf")
        self.assertEqual(doc_type, "annual_report")


if __name__ == "__main__":
    unittest.main()
