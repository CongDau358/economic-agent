import tempfile
import unittest
from pathlib import Path

from backend.ingestion.validation import (
    ExtractionStats,
    detect_duplicates,
    validate_chunk_record,
    validate_document_file,
    validate_ingestion,
)


class IngestionValidationTests(unittest.TestCase):
    def test_reject_invalid_pdf_header(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"NOTPDF-content")
            path = f.name
        try:
            errors = validate_document_file(path, "pdf")
            self.assertTrue(any("invalid PDF" in e for e in errors))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_reject_empty_chunk(self):
        errors = validate_chunk_record(
            {
                "text": "",
                "chunk_id": "1",
                "doc_id": "d1",
                "company": "Acme",
                "sector": "Tech",
                "source_type": "text",
                "raw_ref": "inline",
                "processed_file": "f.json",
            },
            "text",
        )
        self.assertTrue(any("empty chunk" in e for e in errors))

    def test_reject_missing_news_metadata(self):
        errors = validate_chunk_record(
            {
                "text": "A" * 60,
                "chunk_id": "1",
                "doc_id": "d1",
                "company": "Acme",
                "sector": "Tech",
                "source_type": "news",
                "raw_ref": "url",
                "processed_file": "f.json",
            },
            "news",
        )
        self.assertTrue(any("missing metadata" in e for e in errors))

    def test_duplicate_detection(self):
        record = {
            "text": "Revenue increased 12 percent in the first quarter.",
            "chunk_id": "abc",
            "doc_id": "d1",
            "company": "Acme",
            "sector": "Tech",
            "source_type": "text",
            "raw_ref": "inline",
            "processed_file": "f.json",
        }
        unique, dupes = detect_duplicates([record, dict(record)])
        self.assertEqual(len(unique), 1)
        self.assertEqual(dupes, 1)

    def test_validate_ingestion_success(self):
        records = [
            {
                "text": "Revenue increased 12 percent with stable cash flow in Q1.",
                "chunk_id": "c1",
                "doc_id": "doc",
                "company": "Acme",
                "sector": "Tech",
                "source_type": "text",
                "raw_ref": "inline",
                "processed_file": "f.json",
            }
        ]
        result = validate_ingestion(
            source_type="text",
            records=records,
            doc_id="doc",
            extraction_stats=ExtractionStats(char_count=120),
            sample_text=records[0]["text"],
        )
        self.assertTrue(result.valid)
        self.assertEqual(len(result.records), 1)

    def test_validate_ingestion_rejects_low_extraction(self):
        result = validate_ingestion(
            source_type="text",
            records=[],
            doc_id="doc",
            extraction_stats=ExtractionStats(char_count=10),
            sample_text="tiny",
        )
        self.assertFalse(result.valid)


if __name__ == "__main__":
    unittest.main()
