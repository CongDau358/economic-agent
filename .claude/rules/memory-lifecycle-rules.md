# Memory Lifecycle Rules

## Purpose
Define how knowledge enters, evolves, and expires.

## Implementation
- `backend/memory/lifecycle.py`
- `docs/memory-lifecycle.md`

## Lifecycle Stages

### 1. Ingestion
Document added to system (`lifecycle_state=ingestion`).

### 2. Processing
- extraction
- chunking
- embedding
- metadata tagging
- state `processing`

### 3. Retrieval
Document becomes searchable when `lifecycle_state=active`.

### 4. Validation
Evidence quality evaluated at ingest-time and retrieval-time.

### 5. Archival
Outdated information receives `lifecycle_state=archived` and reduced `retrieval_rank_multiplier`.

## State Metadata
- `lifecycle_state`: ingestion | processing | active | review | archived
- `lifecycle_updated_at`
- `lifecycle_reason`
- `retrieval_rank_multiplier`

## Governance
- Do not delete archived memory immediately.
- Downrank archived and review states during retrieval reranking.
- Re-validate when embedding model, chunking policy, or normalization changes materially.
