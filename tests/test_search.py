"""
tests/test_search.py
Tests cho search service và /search endpoint.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ── _highlight ────────────────────────────────────────────────────────────────

class TestHighlight:

    def test_highlights_keyword(self):
        from backend.services.search import _highlight
        text = "Doanh thu Vinamilk tăng mạnh trong Q3."
        h = _highlight(text, "tăng mạnh", window=100)
        assert "**tăng**" in h or "**mạnh**" in h

    def test_returns_snippet_when_no_match(self):
        from backend.services.search import _highlight
        text = "A" * 300
        h = _highlight(text, "xyz_not_found", window=100)
        assert len(h) <= 110   # window + ellipsis

    def test_adds_ellipsis_when_truncated(self):
        from backend.services.search import _highlight
        text = "Prefix text here. " + "B" * 400 + " keyword at end"
        h = _highlight(text, "keyword", window=50)
        assert "..." in h

    def test_short_text_no_ellipsis(self):
        from backend.services.search import _highlight
        text = "Short text with keyword inside."
        h = _highlight(text, "keyword", window=200)
        assert "..." not in h


# ── _keyword_score ────────────────────────────────────────────────────────────

class TestKeywordScore:

    def test_returns_zero_for_no_match(self):
        from backend.services.search import _keyword_score
        score = _keyword_score("Doanh thu tăng mạnh.", "xyz_not_here")
        assert score == 0.0

    def test_returns_positive_for_match(self):
        from backend.services.search import _keyword_score
        score = _keyword_score("Lợi nhuận tăng trưởng mạnh.", "lợi nhuận")
        assert score > 0.0

    def test_more_occurrences_higher_score(self):
        from backend.services.search import _keyword_score
        text_few  = "revenue up this quarter"
        text_many = "revenue up. revenue growth. revenue exceeded expectations."
        s1 = _keyword_score(text_few,  "revenue")
        s2 = _keyword_score(text_many, "revenue")
        assert s2 > s1

    def test_score_bounded_to_one(self):
        from backend.services.search import _keyword_score
        text = ("profit " * 100)
        score = _keyword_score(text, "profit")
        assert 0.0 <= score <= 1.0

    def test_short_words_ignored(self):
        from backend.services.search import _keyword_score
        # Words < 3 chars bị bỏ qua
        score = _keyword_score("a b c d e", "a b")
        assert score == 0.0


# ── SearchQuery dataclass ─────────────────────────────────────────────────────

class TestSearchQuery:

    def test_defaults(self):
        from backend.services.search import SearchQuery
        sq = SearchQuery(query="revenue growth")
        assert sq.top_k             == 10
        assert sq.score_threshold   == 0.3
        assert sq.hybrid            is True
        assert sq.company           is None

    def test_custom_values(self):
        from backend.services.search import SearchQuery
        sq = SearchQuery(
            query="lợi nhuận", company="Vinamilk",
            sector="CS", top_k=5, hybrid=False,
        )
        assert sq.company == "Vinamilk"
        assert sq.top_k   == 5
        assert sq.hybrid  is False


# ── search() function ─────────────────────────────────────────────────────────

class TestSearchFunction:

    def _make_mock_chroma(self, n_results: int = 3, distance: float = 0.2):
        """Helper tạo mock ChromaDB collection."""
        collection = MagicMock()
        collection.query.return_value = {
            "ids":       [["id1", "id2", "id3"][:n_results]],
            "documents": [[
                "Doanh thu Vinamilk tăng 8% trong Q3.",
                "Lợi nhuận gộp cải thiện nhờ tối ưu chi phí.",
                "Ban lãnh đạo nâng dự báo cả năm.",
            ][:n_results]],
            "metadatas": [[
                {"company": "Vinamilk", "sector": "CS",
                 "source": "Q3.pdf", "source_type": "pdf",
                 "ingested_at": "2024-10-01T00:00:00"},
                {"company": "Vinamilk", "sector": "CS",
                 "source": "report.txt", "source_type": "text",
                 "ingested_at": "2024-09-01T00:00:00"},
                {"company": "VCB", "sector": "Finance",
                 "source": "news.html", "source_type": "news",
                 "ingested_at": "2024-08-01T00:00:00"},
            ][:n_results]],
            "distances": [[distance] * n_results],
        }
        return collection

    def test_returns_list(self):
        from backend.services.search import search, SearchQuery
        sq = SearchQuery(query="revenue growth", top_k=5)

        with (
            patch("chromadb.PersistentClient") as MockClient,
            patch("langchain_openai.OpenAIEmbeddings") as MockEmb,
        ):
            MockClient.return_value.get_or_create_collection.return_value = self._make_mock_chroma()
            MockEmb.return_value.embed_query.return_value = [0.1] * 1536

            results = search(sq)

        assert isinstance(results, list)

    def test_filters_below_threshold(self):
        from backend.services.search import search, SearchQuery
        sq = SearchQuery(query="test", score_threshold=0.9)

        with (
            patch("chromadb.PersistentClient") as MockClient,
            patch("langchain_openai.OpenAIEmbeddings") as MockEmb,
        ):
            # distance=0.8 → similarity=0.2, below threshold 0.9
            MockClient.return_value.get_or_create_collection.return_value = \
                self._make_mock_chroma(distance=0.8)
            MockEmb.return_value.embed_query.return_value = [0.1] * 1536

            results = search(sq)

        assert results == []

    def test_result_has_required_keys(self):
        from backend.services.search import search, SearchQuery
        sq = SearchQuery(query="doanh thu", top_k=1)

        with (
            patch("chromadb.PersistentClient") as MockClient,
            patch("langchain_openai.OpenAIEmbeddings") as MockEmb,
        ):
            MockClient.return_value.get_or_create_collection.return_value = \
                self._make_mock_chroma(n_results=1, distance=0.1)
            MockEmb.return_value.embed_query.return_value = [0.1] * 1536

            results = search(sq)

        if results:
            r = results[0]
            for key in ("doc_id", "text", "company", "score", "highlight"):
                assert key in r

    def test_respects_top_k(self):
        from backend.services.search import search, SearchQuery
        sq = SearchQuery(query="test", top_k=2)

        with (
            patch("chromadb.PersistentClient") as MockClient,
            patch("langchain_openai.OpenAIEmbeddings") as MockEmb,
        ):
            MockClient.return_value.get_or_create_collection.return_value = \
                self._make_mock_chroma(n_results=3, distance=0.05)
            MockEmb.return_value.embed_query.return_value = [0.1] * 1536

            results = search(sq)

        assert len(results) <= 2

    def test_handles_chroma_exception(self):
        from backend.services.search import search, SearchQuery
        sq = SearchQuery(query="test")

        with (
            patch("chromadb.PersistentClient") as MockClient,
            patch("langchain_openai.OpenAIEmbeddings") as MockEmb,
        ):
            col = MagicMock()
            col.query.side_effect = Exception("ChromaDB error")
            MockClient.return_value.get_or_create_collection.return_value = col
            MockEmb.return_value.embed_query.return_value = [0.1] * 1536

            results = search(sq)

        assert results == []

    def test_hybrid_final_score_weighted(self):
        from backend.services.search import search, SearchQuery
        sq = SearchQuery(query="doanh thu tăng", hybrid=True, top_k=3, score_threshold=0.0)

        with (
            patch("chromadb.PersistentClient") as MockClient,
            patch("langchain_openai.OpenAIEmbeddings") as MockEmb,
        ):
            MockClient.return_value.get_or_create_collection.return_value = \
                self._make_mock_chroma(n_results=1, distance=0.2)
            MockEmb.return_value.embed_query.return_value = [0.1] * 1536

            results = search(sq)

        if results:
            r = results[0]
            assert "final_score" in r
            # final = 0.7 * sem + 0.3 * kw
            assert r["final_score"] >= r["score"] * 0.6


# ── /search endpoint ──────────────────────────────────────────────────────────

class TestSearchEndpoint:

    @pytest.mark.asyncio
    async def test_search_returns_200(self, auth_client):
        with patch("backend.services.search.search", return_value=[]):
            r = await auth_client.get("/search?q=revenue+growth")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_search_missing_query_returns_422(self, auth_client):
        r = await auth_client.get("/search")
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_search_with_company_filter(self, auth_client):
        with patch("backend.services.search.search", return_value=[]) as mock_search:
            await auth_client.get("/search?q=doanh+thu&company=Vinamilk")

        sq = mock_search.call_args[0][0]
        assert sq.company == "Vinamilk"

    @pytest.mark.asyncio
    async def test_search_response_structure(self, auth_client):
        mock_results = [
            {"doc_id": "id1", "text": "Revenue up...", "company": "VNM",
             "sector": "CS", "source": "report.pdf", "source_type": "pdf",
             "ingested_at": "2024-10-01", "score": 0.88, "final_score": 0.85,
             "highlight": "Revenue **up**..."},
        ]
        with patch("backend.services.search.search", return_value=mock_results):
            r = await auth_client.get("/search?q=revenue&top_k=5")

        data = r.json()
        assert "results"  in data
        assert "count"    in data
        assert "query"    in data
        assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_search_top_k_param(self, auth_client):
        with patch("backend.services.search.search", return_value=[]) as mock_search:
            await auth_client.get("/search?q=test&top_k=7")

        sq = mock_search.call_args[0][0]
        assert sq.top_k == 7

    @pytest.mark.asyncio
    async def test_search_hybrid_default_true(self, auth_client):
        with patch("backend.services.search.search", return_value=[]) as mock_search:
            await auth_client.get("/search?q=test")

        sq = mock_search.call_args[0][0]
        assert sq.hybrid is True

    @pytest.mark.asyncio
    async def test_search_hybrid_false(self, auth_client):
        with patch("backend.services.search.search", return_value=[]) as mock_search:
            await auth_client.get("/search?q=test&hybrid=false")

        sq = mock_search.call_args[0][0]
        assert sq.hybrid is False