# Phase 1 Foundation System Blueprint

## 1) System Architecture (Phase 1 Complete Design)

### 1.1 Target Outcome
Build a single-agent Financial Intelligence System that can:
- Ingest financial reports, news, and social signals
- Store chunked evidence in a vector database
- Retrieve high-relevance context with metadata filters
- Produce grounded financial analysis with citations and confidence

### 1.2 Core Components
- `Agent Runtime`: orchestrates retrieval + reasoning + output formatting
- `Document Pipeline`: extraction, normalization, chunking, metadata enrichment
- `Embedding Service`: transforms chunks/questions into vectors
- `Vector Store`: semantic retrieval + metadata filtering + persistence
- `Knowledge Memory`: global and query-scoped memory views
- `Output Engine`: structured response templates, confidence scoring, citations

### 1.3 Retrieval Pipeline
1. User query received with optional filters (`company`, `sector`, `time_range`, `source_type`).
2. Query normalization and intent tagging (`risk`, `trend`, `valuation`, `sentiment`, `macro`).
3. Query embedding generated.
4. Hybrid retrieval:
   - Semantic similarity top-k from vector DB
   - Optional lexical rerank (keyword overlap / BM25 style if available)
5. Metadata filtering and recency weighting.
6. Evidence reranking with score blending:
   - semantic score
   - recency score
   - source reliability score
7. Final context window assembly (token budget aware, deduplicated).

### 1.4 Document Processing Flow
1. Source intake (`pdf`, `excel`, `news`, `social`).
2. Extraction by source type.
3. Cleanup and normalization:
   - encoding cleanup
   - table normalization
   - number/unit standardization
4. Entity enrichment:
   - company
   - sector
   - period
   - currency
   - source quality
5. Chunking with overlap and section-aware boundaries.
6. Embedding generation.
7. Upsert to vector DB with metadata and lineage fields.

### 1.5 Query Flow
1. Validate query and classify intent.
2. Retrieve top evidence chunks.
3. Verify evidence sufficiency.
4. Run financial reasoning chain:
   - facts
   - signals
   - implications
   - risks/opportunities
5. Generate structured output with citations.
6. Attach confidence and uncertainty notes.

## 2) Data Pipeline Design

### 2.1 PDF Extraction Workflow
- Parse PDF text by page and section headings.
- Detect tables and preserve row/column semantics when possible.
- Store page references for citation traceability.
- Mark low-confidence OCR regions for confidence penalties.

### 2.2 Excel Processing Workflow
- Parse sheet-by-sheet and map named financial statements:
  - income statement
  - balance sheet
  - cash flow
- Normalize time columns, units, and currencies.
- Convert tables to JSON records and narrative chunks.
- Preserve cell provenance (`sheet`, `row`, `column`, `range`).

### 2.3 News + Social Ingestion Workflow
- Pull article/post body, title, author, timestamp, URL.
- Deduplicate by URL + near-duplicate hash.
- Run sentiment and event tagging.
- Tag source credibility and potential bias.

### 2.4 Chunking Strategy
- Financial reports: section-aware chunks (350-700 tokens, overlap 80-120).
- News/social: shorter chunks (180-350 tokens, overlap 40-80).
- Keep headline + lead paragraph linked to each chunk.
- Never split rows from the same financial table across unrelated chunks.

### 2.5 Embedding Workflow
- Use one embedding model consistently for corpus + query.
- Batch embeddings by source and date for throughput.
- Store embedding version in metadata.
- Re-embed only when model version or chunking policy changes.

## 3) Memory System

### 3.1 Global Knowledge Base
- Long-lived vector index shared across all sessions.
- Contains normalized chunks from reports, news, and social data.
- Retains provenance and ingestion lineage.

### 3.2 Vector DB Schema
- `documents` collection:
  - `id`
  - `text`
  - `embedding`
  - `metadata` object
- `metadata` minimum fields:
  - `doc_id`
  - `chunk_id`
  - `source_type`
  - `company`
  - `sector`
  - `ticker`
  - `reporting_period`
  - `published_at`
  - `language`
  - `embedding_model`
  - `ingested_at`
  - `source_url_or_path`
  - `quality_score`
  - `sentiment_label` (optional)

### 3.3 Retrieval Indexing Strategy
- Primary: cosine similarity ANN index.
- Secondary: metadata index for filter-first retrieval.
- Recency-aware reranking and source reliability boosting.
- Rolling index compaction to remove stale duplicate chunks.

## 4) Output System

### 4.1 Response Template (Default)
1. Executive Summary
2. Evidence Snapshot
3. Financial Signals
4. Trend Outlook (1-3 months, 3-6 months)
5. Risks
6. Opportunities
7. Confidence + Assumptions
8. Citations

### 4.2 Citation Behavior
- Every critical claim must map to at least one retrieved chunk.
- Citation format:
  - `[source_type | company | period | doc_id/chunk_id]`
- If no citation exists, statement must be moved to assumptions.

### 4.3 Confidence Scoring
- Base confidence = weighted evidence quality + retrieval relevance.
- Penalize confidence for:
  - weak source reliability
  - stale data
  - contradictory evidence
  - sparse evidence
- Confidence bands:
  - `HIGH` >= 0.75
  - `MEDIUM` 0.50-0.74
  - `LOW` < 0.50

### 4.4 Financial Reasoning Format
- Separate four layers:
  - `Facts` (retrieved, cited)
  - `Signals` (derived metrics/sentiment)
  - `Interpretation` (what signals imply)
  - `Forecast` (bounded outlook with confidence)

## 5) Project Structure (Ideal for Phase 1)

```text
economic-agent/
├── AGENT.md
├── README.md
├── .claude/
│   ├── agents/
│   │   └── economic-intelligence-agent.md
│   ├── rules/
│   │   ├── rag-rules.md
│   │   ├── retrieval-rules.md
│   │   ├── hallucination-prevention.md
│   │   ├── financial-analysis-rules.md
│   │   ├── output-format-rules.md
│   │   ├── chunking-rules.md
│   │   ├── embedding-rules.md
│   │   └── document-processing-rules.md
│   ├── skills/
│   │   ├── financial-report-analysis/SKILL.md
│   │   ├── news-sentiment-analysis/SKILL.md
│   │   ├── trend-analysis/SKILL.md
│   │   ├── document-ingestion/SKILL.md
│   │   ├── rag-query-reasoning/SKILL.md
│   │   └── financial-summary-generation/SKILL.md
│   ├── prompts/
│   │   ├── system/
│   │   └── tasks/
│   └── commands/
├── backend/
│   ├── main.py
│   ├── ingestion/
│   ├── rag/
│   ├── services/
│   └── trend_engine.py
├── data/
│   ├── raw/
│   │   ├── pdf/
│   │   ├── excel/
│   │   ├── news/
│   │   └── social/
│   ├── processed/
│   │   ├── normalized/
│   │   └── features/
│   ├── embeddings/
│   └── vector/
├── pipelines/
│   ├── pdf_pipeline.md
│   ├── excel_pipeline.md
│   ├── news_pipeline.md
│   └── embedding_pipeline.md
└── docs/
    └── phase-1-foundation-system.md
```

## 6) Detailed Implementation Roadmap (Phase 1)

### Milestone 1: Foundation Contracts (Priority P0)
- Finalize metadata schema and citation format.
- Lock chunking + embedding policies.
- Finalize all rules and skill definitions.

### Milestone 2: Ingestion Reliability (Priority P0)
- Harden PDF and Excel extraction quality checks.
- Add deduplication and source reliability tagging.
- Persist normalized outputs for traceability.

### Milestone 3: Retrieval Quality (Priority P1)
- Add filter-first retrieval (`company`, `sector`, `period`).
- Introduce reranking with recency + source quality.
- Add evidence sufficiency gate before answer generation.

### Milestone 4: Reasoning + Output Discipline (Priority P1)
- Enforce facts/signals/forecast separation.
- Add confidence penalty rules and uncertainty reporting.
- Standardize output templates for all analysis routes.

### Milestone 5: MVP Hardening (Priority P1)
- Add evaluation set (10-20 representative financial questions).
- Measure retrieval precision, groundedness, citation coverage.
- Tune chunk size, top-k, and confidence thresholds.

## 7) MVP Checklist

- [ ] All required rules exist and are active.
- [ ] All required skills exist and are reusable.
- [ ] `AGENT.md` defines role, limitations, and workflow.
- [ ] PDF, Excel, and news/social ingestion paths documented and usable.
- [ ] Metadata schema enforced on all vector writes.
- [ ] Responses include citations and confidence.
- [ ] Hallucination guardrails applied (`INSUFFICIENT_DATA` fallback).
- [ ] At least one end-to-end query path verified per data source.

## 8) Best Practices (ECC-style for Financial RAG)

- Keep rules modular and narrowly scoped.
- Keep skills reusable and workflow-driven.
- Prefer retrieval-first reasoning over parametric memory.
- Use strict output contracts to reduce hallucinations.
- Track lineage (`raw -> processed -> chunk -> citation`) for trust.
- Design metadata and indexes now for future multi-agent expansion.
