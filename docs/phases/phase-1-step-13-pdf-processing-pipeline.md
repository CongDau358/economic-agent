# Step Title
Phase 1 Step 13 - PDF Processing Pipeline

## Objective
Replace naive PDF text splitting with a structured pipeline that preserves tables, headings, and financial metrics.

## Components Added
- `backend/ingestion/pdf/` (extractor, cleaner, sections, chunker, pipeline)
- rules: `pdf-processing-rules.md`
- dependency: `pdfplumber` for table extraction

## Workflow
`POST /upload` with `source_type=pdf` runs:
extract → clean → section detect → priority chunk → embed → vector store

## Status
`COMPLETED`
