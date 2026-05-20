import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.rag.storage.metadata import (
    build_chroma_filter,
    extract_year,
    normalize_storage_metadata,
    validate_storage_metadata,
)


class VectorStorageTests(unittest.TestCase):
    def test_normalize_required_metadata(self):
        meta = normalize_storage_metadata(
            {
                "text": "Revenue rose in 2024 for the manufacturing segment.",
                "company": "Acme Corp",
                "sector": "Manufacturing",
                "source_type": "pdf",
                "document_type": "annual_report",
                "chunk_id": "abc123",
                "raw_ref": "/data/raw/report.pdf",
                "processed_file": "report.json",
            }
        )
        self.assertEqual(meta["company"], "Acme Corp")
        self.assertEqual(meta["industry"], "Manufacturing")
        self.assertEqual(meta["year"], "2024")
        self.assertEqual(meta["source"], "pdf")
        self.assertEqual(meta["document_type"], "annual_report")
        self.assertEqual(meta["chunk_id"], "abc123")
        self.assertEqual(meta["source_ref"], "/data/raw/report.pdf")

    def test_extract_year_from_publication_date(self):
        year = extract_year({"publication_date": "2023-08-15"}, "")
        self.assertEqual(year, "2023")

    def test_validate_storage_metadata_missing_chunk_id(self):
        meta = normalize_storage_metadata(
            {
                "text": "x" * 60,
                "company": "Acme",
                "sector": "Tech",
                "source_type": "news",
            }
        )
        errors = validate_storage_metadata(meta)
        self.assertTrue(any("chunk_id" in e for e in errors))

    def test_build_chroma_filter_and_clause(self):
        clause = build_chroma_filter(company="Acme", year="2024")
        self.assertEqual(clause, {"$and": [{"company": "Acme"}, {"year": "2024"}]})

    def test_build_chroma_filter_single(self):
        clause = build_chroma_filter(source="pdf")
        self.assertEqual(clause, {"source": "pdf"})


if __name__ == "__main__":
    unittest.main()
