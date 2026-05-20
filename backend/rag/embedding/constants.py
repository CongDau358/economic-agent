from __future__ import annotations

EMBEDDING_MODEL_OPENAI = "text-embedding-3-small"
EMBEDDING_MODEL_FALLBACK = "fake-embeddings-256"
EMBEDDING_VERSION = "1.0.0"
EMBEDDING_DIMENSION_OPENAI = 1536
EMBEDDING_DIMENSION_FALLBACK = 256
MIN_EMBED_CHARS = 50

FINANCIAL_TERMS = (
    "revenue",
    "profit",
    "ebitda",
    "ebit",
    "net income",
    "cash flow",
    "balance sheet",
    "assets",
    "liabilities",
    "equity",
    "debt",
    "margin",
    "yoy",
    "qoq",
    "cagr",
    "eps",
    "roe",
    "roa",
    "fcf",
    "exports",
    "imports",
)
