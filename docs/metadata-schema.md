# Metadata Schema

## Purpose
Standardize document indexing and retrieval.

## Required Metadata

### Financial Reports
- company
- industry
- year
- quarter
- source
- document type

### News Articles
- title
- publisher
- publication date
- topic
- sentiment

## Importance

Metadata improves:
- retrieval precision
- filtering
- ranking
- reasoning quality

## Implementation Notes
- Metadata fields should be validated at ingestion time.
- Missing required metadata should trigger warning or rejection based on source type.
- Retrieval and reranking should prioritize metadata-aware filtering before final context assembly.
