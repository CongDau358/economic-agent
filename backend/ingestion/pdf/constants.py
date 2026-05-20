from __future__ import annotations

from typing import Dict, List, Tuple

# Supported document categories (inferred from content / filename)
SUPPORTED_DOCUMENT_TYPES = (
    "financial_report",
    "annual_report",
    "government_report",
    "policy_document",
    "general_pdf",
)

# Approximate token targets (chars ≈ 4 per token)
CHUNK_MIN_CHARS = 1400
CHUNK_MAX_CHARS = 2800
CHUNK_OVERLAP_CHARS = 400

HEADING_PATTERNS = (
    r"^(?:\d+\.?\s+)?(?:CHAPTER|SECTION|PART)\s+[\dIVXLC]+",
    r"^\d+\.\s+[A-Z]",
    r"^[A-Z][A-Z0-9\s,&\-]{4,}$",
)

SECTION_TITLE_HINTS = (
    "income statement",
    "balance sheet",
    "cash flow",
    "financial highlights",
    "management discussion",
    "revenue",
    "profit",
    "debt",
    "liquidity",
    "macroeconomic",
    "policy",
    "annual report",
)

FINANCIAL_PRIORITIES: Dict[str, Tuple[str, ...]] = {
    "revenue": (
        "revenue",
        "sales",
        "turnover",
        "doanh thu",
        "net sales",
    ),
    "profit": (
        "profit",
        "net income",
        "earnings",
        "ebitda",
        "ebit",
        "lợi nhuận",
        "operating income",
    ),
    "debt": (
        "debt",
        "liabilities",
        "leverage",
        "borrowing",
        "nợ",
        "interest-bearing",
    ),
    "cash_flow": (
        "cash flow",
        "operating cash",
        "free cash flow",
        "fcf",
        "dòng tiền",
    ),
    "growth": (
        "growth",
        "yoy",
        "year-over-year",
        "cagr",
        "increase",
        "expansion",
        "tăng trưởng",
    ),
}

DOCUMENT_TYPE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "annual_report": ("annual report", "báo cáo thường niên", "form 10-k", "10-k"),
    "financial_report": ("financial statement", "quarterly report", "10-q", "báo cáo tài chính"),
    "government_report": ("government", "ministry", "central bank", "chính phủ", "bộ tài chính"),
    "policy_document": ("policy", "regulation", "directive", "chính sách", "nghị định"),
}
