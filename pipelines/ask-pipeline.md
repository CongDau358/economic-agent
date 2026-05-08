# Ask Pipeline

## Purpose
Handle factual financial and economic queries with high-precision retrieval, strict grounding, and confidence-aware responses.

## Architecture Flow

User Query  
-> Intent Detection  
-> Memory Retrieval  
-> Metadata Filtering  
-> Source Ranking  
-> Retrieval Validation  
-> Reasoning  
-> Evaluation  
-> Output Formatting

## Execution Flow

1. **Intent Detection**
   - classify query as:
     - factual query
     - metric lookup
     - document retrieval
   - extract retrieval entities (company, industry, year, metric, document type).

2. **Memory Retrieval**
   - access global knowledge base for validated facts and prior references.
   - query vector memory for semantic nearest chunks.
   - access historical knowledge memory for prior report and sentiment context.

3. **Metadata Filtering**
   - apply strict filters using:
     - `company`
     - `industry`
     - `year`
     - `source_type`
     - `document_type`
     - `recency`
   - if key metadata is missing, keep broad candidates but lower confidence ceiling.

4. **Source Ranking**
   - prioritize evidence by trust tier:
     - official reports
     - audited financial statements
     - government publications
     - trusted financial news
   - include lower-trust sources only as secondary support.

5. **Retrieval Validation**
   - remove duplicate and near-duplicate chunks.
   - remove low-relevance chunks by score threshold.
   - validate source trustworthiness against source-priority policy.
   - if insufficient evidence remains, return `INSUFFICIENT_DATA`.

6. **Reasoning**
   - run `rag-query-reasoning`.
   - generate answer from retrieved evidence only.
   - separate:
     - facts
     - inferred signals
     - assumptions

7. **Evaluation**
   - run response checks for:
     - grounding coverage
     - hallucination risk
     - evidence consistency
     - confidence calibration

8. **Output Formatting**
   - return:
     - `answer`
     - `evidence_snapshot`
     - `confidence`
     - `citations`
   - enforce citation mapping for material claims.

## Retrieval Optimization Behavior
- Prefer metadata-constrained retrieval over broad search for factual questions.
- Use historical knowledge only as context enhancer, never as uncited fact source.
- Penalize stale evidence for time-sensitive queries.

## Required Skills
- `rag-query-reasoning`

## Required Rules
- `intent-classification-rules.md`
- `rag-rules.md`
- `retrieval-rules.md`
- `retrieval-indexing-strategy-rules.md`
- `source-priority-rules.md`
- `metadata-schema-rules.md`
- `global-memory-system-rules.md`
- `memory-lifecycle-rules.md`
- `failure-handling-rules.md`
- `hallucination-prevention.md`
- `confidence-scoring-rules.md`
- `output-format-rules.md`

## Output Contract

```json
{
  "answer": "string",
  "evidence_snapshot": ["string"],
  "confidence": {
    "value": 0.0,
    "band": "HIGH|MEDIUM|LOW",
    "reasoning": "string"
  },
  "assumptions": ["string"],
  "citations": ["source_type | company | period | doc_id/chunk_id"]
}
```
