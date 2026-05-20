# Embedding Rules

## Implementation
- `backend/rag/embedding/` (`normalizer.py`, `model.py`, `pipeline.py`)

## Model Consistency
- Use the same embedding model for ingestion and query-time retrieval.
- Track `embedding_model` and `embedding_version` in metadata.

## Embedding Scope
- Embed cleaned text only (remove boilerplate noise).
- Preserve key financial terms, numbers, and units before embedding.
- Keep language consistent; translate only if strategy explicitly allows.

## Update Policy
- Re-embed when:
  - embedding model changes
  - chunking policy changes
  - normalization pipeline changes materially
- Avoid unnecessary full re-embeds for minor metadata updates.

## Quality Controls
- Reject empty or near-empty chunks.
- Detect and skip duplicate chunk embeddings.
- Log embedding failures and retry with backoff.
