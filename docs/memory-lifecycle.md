# Memory Lifecycle

## Purpose
Define how knowledge enters, evolves, and expires.

## Lifecycle Stages

### 1. Ingestion
Document added to system.

### 2. Processing
- extraction
- chunking
- embedding
- metadata tagging

### 3. Retrieval
Document becomes searchable (`lifecycle_state=active`).

### 4. Validation
Evidence quality evaluated at ingest-time and during retrieval ranking.

### 5. Archival
Outdated information downgraded in retrieval ranking (`lifecycle_state=archived`).

## Implementation

- `backend/memory/lifecycle.py`
- `.claude/rules/memory-lifecycle-rules.md`

## Lifecycle States

| State | Retrieval |
|-------|-----------|
| `ingestion` | not searchable |
| `processing` | not searchable |
| `active` | full rank |
| `review` | 0.75x rank |
| `archived` | 0.45x rank |

## Age Thresholds

- `review`: content year ≥ 3 years old
- `archived`: content year ≥ 5 years old (news ≥ 2 years)

## Metadata Fields

- `lifecycle_state`
- `lifecycle_updated_at`
- `lifecycle_reason`
- `retrieval_rank_multiplier`

## Rules

- Validation runs at ingest-time (`validation.py`) and retrieval-time (`retrieval_governance.py`).
- Archival downgrades ranking; records are not deleted immediately.
- Lifecycle is traceable via metadata flags and timestamps.
