# Retrieval Rules

## Query Preparation
- Normalize query text (company aliases, ticker symbols, period phrases).
- Classify query intent before retrieval.
- Expand query with domain synonyms only when precision is preserved.

## Retrieval Strategy
- Default `top_k`: 4-8 based on query complexity.
- Apply metadata filters first for `company`, `sector`, `period`, `source_type`.
- Retrieve from mixed sources, then rerank by reliability and recency.
- Remove near-duplicate chunks from final context set.

## Reranking Policy
- Blend:
  - semantic relevance
  - source reliability
  - recency score
- Penalize noisy or low-trust sources.

## Quality Gate
- Minimum evidence threshold:
  - at least 2 supporting chunks for strategic claims
  - at least 1 high-quality chunk for factual claims
- If threshold fails, return `INSUFFICIENT_DATA`.

## Governance
- Enforced in detail by `retrieval-governance-rules.md` (backend: `retrieval_governance.py`).
