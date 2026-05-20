# Step Title
Phase 1 Step 12 - Retrieval Governance Rules

## Objective
Enforce retrieval-first governance so grounded evidence and trusted sources outweigh response length, with explicit handling of low-confidence retrieval.

## Problem Addressed
Without retrieval governance, the agent could produce fluent but unsupported financial claims or hide weak evidence behind high-confidence wording.

## Components Added
- rules: `retrieval-governance-rules.md`
- backend: `backend/services/retrieval_governance.py`
- tests: `tests/test_retrieval_governance.py`
- `/ask` pipeline applies rerank, trust scoring, quality gates, and warnings

## Architecture Changes
Added a governance layer between vector retrieval and RAG answer generation:
1. similarity search with distance scores
2. rerank + deduplicate by relevance and source trust
3. evidence sufficiency assessment
4. confidence band + mandatory warnings for low-trust or low-confidence retrieval

## Workflow Changes
`/ask` now returns:
- `retrieval_quality` (status, chunk counts, warnings)
- `confidence.band` and `confidence.warnings`
- `citations` aligned with evidence chunks

## Benefits
- Unsupported financial claims blocked at quality gates
- Low-confidence retrieval always surfaced to the user
- Shorter, evidence-first answers preferred over speculative length

## Status
`COMPLETED`
