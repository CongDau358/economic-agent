import tempfile
import unittest
from pathlib import Path

from backend.ingestion.excel.extractor import ExtractedTable, _table_from_matrix
from backend.ingestion.excel.metrics import map_metrics
from backend.ingestion.excel.normalizer import normalize_table
from backend.ingestion.excel.tagger import tag_chunks


class ExcelPipelineTests(unittest.TestCase):
    def test_normalize_preserves_row_column_alignment(self):
        table = ExtractedTable(
            sheet_name="Revenue",
            headers=["Period", "Revenue", "Net Income"],
            rows=[["2024-Q1", "1200", "180"], ["2024-Q2", "1300", "195"]],
            row_start=2,
            row_end=3,
            col_count=3,
        )
        normalized = normalize_table(table)
        self.assertEqual(len(normalized.rows), 2)
        self.assertIn("date", normalized.canonical_columns.values())
        self.assertEqual(normalized.rows[0][normalized.columns[0]], "2024-Q1")

    def test_metric_mapping_balance_sheet(self):
        table = ExtractedTable(
            sheet_name="Balance Sheet",
            headers=["Date", "Assets", "Liabilities", "Equity"],
            rows=[["2024", "5000", "3000", "2000"]],
            row_start=2,
            row_end=2,
            col_count=4,
        )
        mapped = map_metrics(normalize_table(table))
        self.assertEqual(mapped.data_type, "balance_sheet")
        self.assertEqual(mapped.rows[0].metrics.get("assets"), "5000")

    def test_tag_chunks_keep_table_structure(self):
        table = ExtractedTable(
            sheet_name="Trade",
            headers=["Date", "Exports", "Imports"],
            rows=[["2024-01", "100", "80"], ["2024-02", "110", "85"]],
            row_start=2,
            row_end=3,
            col_count=3,
        )
        mapped = map_metrics(normalize_table(table))
        chunks = tag_chunks(mapped, doc_id="doc-1")
        self.assertEqual(len(chunks), 1)
        self.assertIn("[TABLE]", chunks[0].text)
        self.assertIn("exports=", chunks[0].text)
        self.assertEqual(chunks[0].date_alignment, "unique")

    def test_extract_csv(self):
        from backend.ingestion.excel.extractor import _extract_csv

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            f.write("Period,Revenue\n2024-Q1,100\n")
            path = f.name
        try:
            wb = _extract_csv(path)
            self.assertEqual(wb.file_format, "csv")
            self.assertEqual(len(wb.tables), 1)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_table_from_matrix_empty_headers(self):
        self.assertIsNone(_table_from_matrix("Sheet1", [["", ""], ["a", "b"]]))


if __name__ == "__main__":
    unittest.main()
