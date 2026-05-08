# Report Pipeline

## Purpose
Generate structured financial intelligence reports that aggregate long-term knowledge, summarize trends across sectors, and prioritize high-confidence evidence.

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
   - classify report objective:
     - structured summary
     - full report
     - comparative analysis
   - detect scope across company/industry/sector/timeframe.

2. **Memory Retrieval**
   - access global knowledge base for longitudinal validated insights.
   - retrieve vector memory evidence across multiple sectors and periods.
   - retrieve historical knowledge:
     - long-term trends
     - previous report conclusions
     - historical sentiment cycles
     - historical policy and macro shifts

3. **Metadata Filtering**
   - filter by:
     - `company`
     - `industry`
     - `year`
     - `source_type`
     - `document_type`
     - `recency`
   - ensure balanced coverage for comparative and sector-wide reporting.

4. **Source Ranking**
   - prioritize:
     - official reports
     - audited financial statements
     - government publications
     - trusted financial news
   - high-confidence sections must rely primarily on high-trust evidence.

5. **Retrieval Validation**
   - remove duplicate and low-relevance chunks.
   - validate trustworthiness and coverage depth for each report section.
   - isolate contradictory evidence and route to uncertainty notes.

6. **Reasoning**
   - run multi-skill synthesis:
     - `financial-report-analysis`
     - `news-sentiment-analysis`
     - `trend-analysis`
     - `financial-summary-generation`
   - produce cross-sector and longitudinal insights.

7. **Evaluation**
   - run evaluation checks:
     - retrieval quality
     - grounding coverage
     - hallucination detection
     - reasoning coherence
     - confidence validation
   - downgrade confidence for weakly grounded sections.

8. **Output Formatting**
   - generate report sections:
     - executive summary
     - key evidence
     - trend and sector analysis
     - risks/opportunities
     - confidence and assumptions
     - citations

## Retrieval Optimization Behavior
- Favor high-trust sources for section-level summary claims.
- Use historical memory to detect multi-period trend continuity and regime shifts.
- Enforce evidence quotas for each major report section before finalization.

## Required Skills
- `financial-report-analysis`
- `news-sentiment-analysis`
- `trend-analysis`
- `financial-summary-generation`

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
- `financial-analysis-rules.md`
- `output-format-rules.md`

## Output Contract

```json
{
  "report_type": "STRUCTURED_SUMMARY|FULL_REPORT|COMPARATIVE_ANALYSIS",
  "scope": {
    "company": "string|null",
    "industry": "string|null",
    "timeframe": "string|null"
  },
  "executive_summary": "string",
  "key_evidence": ["string"],
  "sector_trend_summary": ["string"],
  "long_term_knowledge": {
    "historical_trends": ["string"],
    "policy_regime_changes": ["string"],
    "sentiment_cycles": ["string"]
  },
  "risks": ["string"],
  "opportunities": ["string"],
  "confidence": {
    "overall": {
      "value": 0.0,
      "band": "HIGH|MEDIUM|LOW",
      "reasoning": "string"
    },
    "section_confidence": [
      {
        "section": "string",
        "value": 0.0,
        "band": "HIGH|MEDIUM|LOW"
      }
    ]
  },
  "assumptions": ["string"],
  "citations": ["source_type | entity | period | doc_id/chunk_id"]
}
```
