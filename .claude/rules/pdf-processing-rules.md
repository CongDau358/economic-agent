# PDF Processing Pipeline

## Purpose

Extract and normalize financial information from PDF documents for grounded retrieval.

## Supported Documents

- financial reports
- annual reports
- government reports
- policy documents

## Processing Flow

```
PDF
 ↓
Text Extraction (pdfplumber preferred; pypdf fallback)
 ↓
Text Cleaning (preserve tables, headings, page markers)
 ↓
Section Detection (heading-aware blocks)
 ↓
Chunking (financial-priority, section context)
 ↓
Embedding (via vector store on ingest)
 ↓
Vector Storage (Chroma + metadata lineage)
```

Backend implementation: `backend/ingestion/pdf/`

## Extraction Rules

The system must:

- preserve tables when possible (`[TABLE]...[/TABLE]` blocks via pdfplumber)
- preserve headings (section titles attached to chunks)
- preserve financial metrics (detect revenue, profit, debt, cash flow, growth)
- record `page_ref`, `section_title`, `doc_id`, `chunk_id` for citations

## Financial Priorities

Prioritize detection and chunk ranking for:

- revenue
- profit
- debt
- cash flow
- growth indicators

Store detected priorities in chunk metadata: `financial_priorities`.

## Chunking Policy

- Target 350–700 tokens (~1400–2800 chars), overlap ~400 chars
- Never split inside `[TABLE]` blocks
- Prefix chunks with `[Section: {title} | Pages: {ref}]`
- Sort chunks by financial `priority_score` before embedding

## Related Rules

- `chunking-rules.md`
- `document-processing-rules.md`
- `metadata-schema-rules.md`
- `source-priority-rules.md` (PDF = high trust)
