---
name: data-ingestion
description: Ingests PDF, news URL, and raw text sources into raw storage, processed JSON, and vector chunks.
---

# Data Ingestion

## When to Use

- User uploads report files.
- User submits economic news URLs.
- User provides plain text market notes.

## Steps

1. Read source content (PDF/URL/text).
2. Normalize into chunked text blocks.
3. Save processed JSON with metadata.
4. Add chunk embeddings to vector DB.
5. Return ingestion stats and references.

## Output Format

```json
{
  "message": "data ingested",
  "company": "string",
  "sector": "string",
  "source_type": "pdf|news|text",
  "processed_file": "string",
  "chunk_count": 0
}
```
