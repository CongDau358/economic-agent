# Hybrid Retrieval System

## Purpose
Combine multiple retrieval strategies to improve context relevance and grounding quality.

## Retrieval Components

### 1. Semantic Search
Use:
- embedding similarity
- vector retrieval

Purpose:
- understand meaning
- retrieve semantically related chunks

### 2. Keyword Search
Use:
- exact financial terms
- company names
- metrics
- dates

Purpose:
- improve precision
- reduce semantic drift

### 3. Metadata Filtering
Use:
- company
- industry
- year
- source type
- document type

Purpose:
- narrow retrieval scope
- improve relevance

## Final Retrieval

Combine:
- semantic score
- keyword score
- metadata relevance
- source trust

## Implementation Notes
- Use semantic retrieval for candidate generation, keyword search for precision correction, and metadata filtering for scope control.
- Apply source trust weighting during reranking before final context selection.
- If combined score quality is below threshold, return `INSUFFICIENT_DATA`.
