from __future__ import annotations

from typing import Dict, Tuple

CHUNK_MAX_CHARS = 1400
CHUNK_OVERLAP_CHARS = 160

TOPIC_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "earnings": ("earnings", "profit", "revenue", "quarterly results", "lợi nhuận", "doanh thu"),
    "macro": ("inflation", "interest rate", "gdp", "central bank", "fed", "lạm phát", "lãi suất"),
    "regulation": ("regulation", "regulatory", "compliance", "law", "quy định", "nghị định"),
    "trade": ("export", "import", "tariff", "trade war", "xuất khẩu", "nhập khẩu"),
    "markets": ("stock", "market", "index", "shares", "thị trường", "cổ phiếu"),
    "m_and_a": ("acquisition", "merger", "takeover", "m&a", "sáp nhập"),
    "risk": ("risk", "default", "bankruptcy", "downgrade", "rủi ro"),
    "policy": ("policy", "stimulus", "fiscal", "chính sách"),
}

POSITIVE_TERMS = (
    "growth",
    "surge",
    "gain",
    "beat",
    "upgrade",
    "positive",
    "strong",
    "record high",
    "tăng",
    "tích cực",
    "vượt kỳ vọng",
)

NEGATIVE_TERMS = (
    "decline",
    "fall",
    "drop",
    "loss",
    "downgrade",
    "negative",
    "weak",
    "default",
    "bankruptcy",
    "giảm",
    "tiêu cực",
    "sụt giảm",
)

SOCIAL_MAX_CHARS = 2000
