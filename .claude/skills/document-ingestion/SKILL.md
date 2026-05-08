# Document Ingestion Skill

## When to Use
- Add new sources to the financial knowledge base.
- Process PDF, Excel, news URL, social feed entries, and raw text.

## Inputs
- `source_type`
- source payload (`file`, `url`, `text`)
- entity metadata (`company`, `sector`, `ticker`, `period`)

## Workflow
1. Validate source and required fields.
2. Extract raw content using source-specific parser.
3. Normalize text/tables and enrich metadata.
4. Chunk by source-aware strategy with overlap.
5. Generate embeddings.
6. Upsert chunks into vector store.
7. Persist processed artifact for lineage/audit.

## Output Schema
- `ingestion_status`
- `source_summary`
- `chunk_count`
- `embedding_status`
- `vector_upsert_status`
- `lineage_ref`

## Guardrails
- Reject unsupported source types early.
- Do not ingest empty or duplicate documents.
- Always preserve source reference for citation.
