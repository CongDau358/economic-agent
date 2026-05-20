# Chunking Rules

## Goals
- Preserve financial context and citation traceability.
- Optimize retrieval relevance and reduce semantic drift.

## Implementation
- `backend/ingestion/chunking/strategy.py`

## Chunk Types
- `financial_metric` — revenue, profit, cash flow sections
- `financial_table` — intact table blocks (PDF/Excel)
- `news_event` — policy updates, market events
- `general` — fallback

## Size and Overlap
- Financial report: 900–2800 chars, overlap 400
- News/social: 400–1400 chars, overlap 160
- Excel tables: row batches inside single `[TABLE]` block

## Boundary Policy
- Split by semantic boundaries: section headings, paragraph transitions
- Never split inside `[TABLE]...[/TABLE]`
- Merge undersized fragments; avoid oversized single paragraphs where possible
- Keep heading/context header attached to child chunks

## Metadata Requirements per Chunk
- `doc_id`, `chunk_id`, `chunk_type`, `source_type`, `company`, `sector`
- `published_at`, `reporting_period`, `page_or_sheet_ref`
- `quality_score`, `language`
