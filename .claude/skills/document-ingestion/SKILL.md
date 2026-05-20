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
3. **PDF:** run `pdf-processing-rules.md` pipeline (extract → clean → sections → priority chunk).
4. Normalize text/tables and enrich metadata.
5. Chunk by source-aware strategy with overlap (non-PDF).
6. Generate embeddings.
7. Upsert chunks into vector store.
8. Persist processed artifact for lineage/audit.

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
