---
description: Handle factual financial/economic questions with grounded RAG retrieval and confidence-scored outputs.
---

# /ask

## Maps To

- Agent: `economic-intelligence-agent`
- Skills:
  - `rag-query-reasoning`
- Rules:
  - `intent-classification-rules.md`
  - `rag-rules.md`
  - `retrieval-rules.md`
  - `retrieval-governance-rules.md`
  - `hallucination-prevention.md`
  - `output-format-rules.md`

## Ask Pipeline

### Purpose
Handle factual financial and economic queries using grounded RAG retrieval.

### Execution Flow

1. **Input Validation**
   - Ensure query is not empty.
   - Detect language.
   - Normalize financial terminology (company aliases, ticker, metric names).

2. **Intent Detection**
   - Classify request as:
     - factual query
     - metric query
     - document query

3. **Retrieval Strategy Selection**
   - If query contains company, financial metric, or date/year:
     - apply metadata filtering (`company`, `sector`, `period`, `source_type`)
   - Otherwise:
     - use broad semantic retrieval first, then rerank

4. **Vector Retrieval**
   - semantic similarity search
   - top-k retrieval (`4-8` default)
   - metadata-aware ranking (relevance + source reliability + recency)

5. **Retrieval Governance** (`retrieval-governance-rules.md`)
   - rerank by relevance + source trust; deduplicate chunks
   - enforce quality gates (factual vs strategic claim thresholds)
   - never use low-confidence retrieval without `confidence.warnings`
   - prefer shorter grounded answers over long unsupported prose

6. **Relevance Validation**
   - remove low-relevance chunks
   - remove duplicate/near-duplicate chunks
   - keep only evidence that directly supports the asked intent

7. **Hallucination Prevention**
   - If evidence is insufficient or low quality:
     - return `INSUFFICIENT_DATA`
   - Never output uncited factual or numeric claims

8. **Reasoning**
   - apply `rag-query-reasoning` skill
   - generate grounded answer only from retrieved or user-provided evidence

9. **Confidence Scoring**
   - compute confidence from:
     - retrieval quality
     - source reliability
     - evidence consistency
   - downgrade for stale, conflicting, or sparse evidence

10. **Output Formatting**
   - include:
     - `answer`
     - `evidence` / `evidence_snapshot`
     - `retrieval_quality`
     - `confidence` (with `band` and `warnings`)
     - `citations`

## Output Contract

```json
{
  "answer": "string",
  "evidence": [],
  "retrieval_quality": {
    "status": "OK|LOW_CONFIDENCE|INSUFFICIENT_DATA",
    "chunk_count": 0,
    "warnings": []
  },
  "confidence": {
    "value": 0.0,
    "band": "HIGH|MEDIUM|LOW|INSUFFICIENT",
    "reasoning": "string",
    "warnings": []
  },
  "citations": ["source_type | company | sector"]
}
```
