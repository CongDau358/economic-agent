# Chunking Rules

## Goals
- Preserve financial context and citation traceability.
- Optimize retrieval relevance and reduce semantic drift.

## Size and Overlap
- Financial report chunks: 350-700 tokens, overlap 80-120.
- News/social chunks: 180-350 tokens, overlap 40-80.
- Table-heavy content may use smaller semantic units.

## Boundary Policy
- Split by semantic boundaries:
  - section headings
  - paragraph transitions
  - table blocks
- Never split a table row into unrelated chunks.
- Keep heading context attached to child chunks.

## Metadata Requirements per Chunk
- `doc_id`, `chunk_id`, `source_type`, `company`, `sector`
- `published_at`, `reporting_period`, `page_or_sheet_ref`
- `quality_score`, `language`
