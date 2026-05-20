# Metadata Schema Rules

## Purpose
Standardize document indexing and retrieval.

## Implementation
- `backend/rag/storage/metadata.py`
- `backend/rag/storage/store.py`

## Required Metadata (vector storage)
- company
- industry
- year
- source
- document_type
- chunk_id

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
