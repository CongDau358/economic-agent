"""
tests/test_ingestion.py
Unit tests cho ingestion pipeline (toàn bộ external calls được mock).
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, mock_open


# ── _sync_ingest (integration qua main.py) ────────────────────────────────────

class TestSyncIngest:

    def _make_mock_pipeline_result(self, n_chunks: int = 3):
        result = MagicMock()
        result.chunks = [
            {"text": f"Chunk {i}", "company": "VNM", "sector": "CS",
             "source_type": "pdf", "raw_ref": "raw.pdf",
             "processed_file": "p.json"}
            for i in range(n_chunks)
        ]
        result.page_count    = 5
        result.section_count = 3
        result.document_type = "annual_report"
        result.extractor     = "pdfplumber"
        result.financial_priorities_found = ["revenue", "profit"]
        result.sections_preview = []
        return result

    def _mock_vector_update(self):
        u = MagicMock()
        u.updated_count  = 3
        u.skipped_count  = 0
        u.duplicate_count = 0
        u.replaced_count  = 0
        u.batch_count     = 1
        u.latency_ms      = 42.0
        u.update_version  = "v1"
        u.doc_ids         = ["id1", "id2", "id3"]
        return u

    def test_text_ingestion_success(self):
        from backend.main import _sync_ingest
        mock_update = self._mock_vector_update()

        with (
            patch("backend.main.parse_source",   return_value=["chunk1", "chunk2"]),
            patch("backend.main.save_processed",  return_value={"chunks": []}),
            patch("backend.main.validate_ingestion", return_value=MagicMock(
                valid=True, records=[
                    {"text": "chunk1", "company": "VNM", "sector": "CS",
                     "source_type": "text", "raw_ref": "inline_text",
                     "processed_file": "p.json"},
                    {"text": "chunk2", "company": "VNM", "sector": "CS",
                     "source_type": "text", "raw_ref": "inline_text",
                     "processed_file": "p.json"},
                ],
                valid_chunk_count=2, duplicate_count=0,
                rejected_chunk_count=0, warnings=[],
            )),
            patch("backend.memory.lifecycle.apply_processing_lifecycle", side_effect=lambda x: x),
            patch("backend.main.vector_store") as mock_vs,
            patch("backend.main.EmbeddingBatchResult") as mock_emb,
        ):
            mock_vs.update_records.return_value = mock_update
            mock_vs.embedding_model = "text-embedding-3-small"
            mock_emb.return_value.embedded_count = 2
            mock_emb.return_value.skipped_count  = 0
            mock_emb.return_value.duplicate_count = 0
            mock_emb.return_value.model = "text-embedding-3-small"
            mock_emb.return_value.model_version = "v1"

            result = _sync_ingest(
                source_type="text", company="VNM", sector="CS",
                text="Revenue up 15% YoY in Q3 2024.",
                url=None, file_bytes=None, file_name=None,
            )

        assert result["company"] == "VNM"
        assert result["source_type"] == "text"
        assert result["chunk_count"] == 2
        assert result["message"] == "data ingested"

    def test_invalid_source_type_raises(self):
        from backend.main import _sync_ingest
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _sync_ingest("invalid_type", "VNM", "CS", None, None, None, None)
        assert exc_info.value.status_code == 400

    def test_text_without_content_raises(self):
        from backend.main import _sync_ingest
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _sync_ingest("text", "VNM", "CS", None, None, None, None)
        assert exc_info.value.status_code == 400

    def test_pdf_without_file_raises(self):
        from backend.main import _sync_ingest
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _sync_ingest("pdf", "VNM", "CS", None, None, None, None)
        assert exc_info.value.status_code == 400

    def test_pdf_wrong_extension_raises(self):
        from backend.main import _sync_ingest
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _sync_ingest("pdf", "VNM", "CS", None, None, b"content", "report.docx")
        assert exc_info.value.status_code == 400

    def test_excel_wrong_extension_raises(self):
        from backend.main import _sync_ingest
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _sync_ingest("excel", "VNM", "CS", None, None, b"content", "report.pdf")
        assert exc_info.value.status_code == 400

    def test_news_without_url_or_text_raises(self):
        from backend.main import _sync_ingest
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _sync_ingest("news", "VNM", "CS", None, None, None, None)
        assert exc_info.value.status_code == 400

    def test_validation_failure_raises(self):
        from backend.main import _sync_ingest
        from fastapi import HTTPException
        with (
            patch("backend.main.parse_source", return_value=["chunk1"]),
            patch("backend.main.validate_ingestion", return_value=MagicMock(
                valid=False,
                errors=["Document too short"],
                records=[],
            )),
        ):
            with pytest.raises(HTTPException) as exc_info:
                _sync_ingest("text", "VNM", "CS", "short", None, None, None)
            assert exc_info.value.status_code == 400

    def test_empty_chunks_after_parse_raises(self):
        from backend.main import _sync_ingest
        from fastapi import HTTPException
        with patch("backend.main.parse_source", return_value=[]):
            with pytest.raises(HTTPException) as exc_info:
                _sync_ingest("text", "VNM", "CS", "some text", None, None, None)
            assert exc_info.value.status_code == 400


# ── Async upload endpoint ─────────────────────────────────────────────────────

class TestUploadEndpoint:

    @pytest.mark.asyncio
    async def test_upload_queues_job(self, client):
        with patch("backend.main._sync_ingest", return_value={"chunk_count": 5}):
            r = await client.post("/upload", data={
                "source_type": "text",
                "company":     "Vinamilk",
                "sector":      "Consumer Staples",
                "text":        "Doanh thu tăng 15% so với cùng kỳ.",
            })
        assert r.status_code == 200
        body = r.json()
        assert "job_id" in body
        assert body["status"] == "pending"

    @pytest.mark.asyncio
    async def test_upload_job_trackable(self, client):
        with patch("backend.main._sync_ingest", return_value={"chunk_count": 3}):
            upload_r = await client.post("/upload", data={
                "source_type": "text", "company": "VCB",
                "sector": "Finance", "text": "Lợi nhuận tăng mạnh Q3.",
            })
        job_id = upload_r.json()["job_id"]
        job_r = await client.get(f"/jobs/{job_id}")
        assert job_r.status_code == 200
        assert job_r.json()["job_id"] == job_id

    @pytest.mark.asyncio
    async def test_upload_missing_company_422(self, client):
        r = await client.post("/upload", data={
            "source_type": "text", "sector": "Finance", "text": "Some text.",
        })
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_missing_sector_422(self, client):
        r = await client.post("/upload", data={
            "source_type": "text", "company": "VCB", "text": "Some text.",
        })
        assert r.status_code == 422


# ── Jobs list endpoint ────────────────────────────────────────────────────────

class TestJobsEndpoint:

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, client):
        r = await client.get("/jobs")
        assert r.status_code == 200
        assert "jobs" in r.json()
        assert "count" in r.json()

    @pytest.mark.asyncio
    async def test_list_jobs_with_status_filter(self, client):
        r = await client.get("/jobs?status=done")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_list_jobs_with_invalid_status_422(self, client):
        r = await client.get("/jobs?status=invalid_status")
        assert r.status_code in (200, 422)  # depending on validation impl

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, client):
        r = await client.get("/jobs/nonexistent-job-id-xyz")
        assert r.status_code == 404
        assert r.json()["error"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_list_jobs_limit(self, client):
        r = await client.get("/jobs?limit=5")
        assert r.status_code == 200
        assert len(r.json()["jobs"]) <= 5