# Analyze Pipeline

## Purpose
Perform structured financial and trend analysis with memory-aware evidence synthesis across current and historical signals.

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
   - classify request as company analysis, sector analysis, or financial evaluation.
   - detect:
     - company
     - sector/industry
     - timeframe
   - map analysis goals (performance, risk, trend, sentiment).

2. **Memory Retrieval**
   - access global knowledge base for validated insights.
   - retrieve current-period evidence from vector memory.
   - retrieve historical knowledge:
     - past trends
     - previous reports
     - historical sentiment
     - historical policy signals

3. **Metadata Filtering**
   - apply filters using:
     - `company`
     - `industry`
     - `year`
     - `source_type`
     - `document_type`
     - `recency`
   - enforce temporal windows for current vs historical comparison.

4. **Source Ranking**
   - prioritize:
     - official reports
     - audited financial statements
     - government publications
     - trusted financial news
   - demote low-trust sources for strategic conclusions.

5. **Retrieval Validation**
   - remove duplicate/near-duplicate chunks.
   - remove low-relevance chunks.
   - validate source trustworthiness.
   - require adequate evidence for both current and historical perspectives.

6. **Reasoning - Financial Analysis**
   - run `financial-report-analysis`
   - evaluate:
     - revenue growth
     - profitability
     - debt
     - liquidity
   - compare current findings against historical baseline.

7. **Reasoning - Sentiment and Signal Correlation**
   - run `news-sentiment-analysis`
   - classify:
     - positive
     - neutral
     - negative
   - correlate:
     - financial data
     - sentiment momentum
     - policy impact

8. **Reasoning - Trend Synthesis**
   - run `trend-analysis`
   - produce current-vs-historical interpretation.
   - identify:
     - trends
     - risks
     - opportunities

9. **Evaluation**
   - validate:
     - grounding coverage
     - evidence consistency
     - contradiction handling
   - compute confidence using:
     - retrieval quality
     - source reliability
     - metadata match quality
     - evidence consistency
     - recency profile
   - downgrade confidence for sparse or conflicting evidence

10. **Structured Output**
   - format output by `output-format-rules.md`
   - include citations for all material claims

## Required Skills
- `financial-report-analysis`
- `news-sentiment-analysis`
- `trend-analysis`

## Required Rules
- `intent-classification-rules.md`
- `financial-analysis-rules.md`
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
  "executive_summary": "string",
  "detected_scope": {
    "company": "string|null",
    "industry": "string|null",
    "timeframe": "string|null"
  },
  "evidence_snapshot": ["string"],
  "historical_context": {
    "past_trends": ["string"],
    "previous_reports": ["string"],
    "historical_sentiment": ["string"],
    "historical_policy_signals": ["string"]
  },
  "financial_analysis": {
    "revenue_growth": "string",
    "profitability": "string",
    "debt": "string",
    "liquidity": "string"
  },
  "sentiment_analysis": {
    "positive": 0,
    "neutral": 0,
    "negative": 0
  },
  "signal_correlation": ["string"],
  "trend_outlook": {
    "near_term": "string",
    "mid_term": "string",
    "historical_comparison": "string"
  },
  "risks": ["string"],
  "opportunities": ["string"],
  "confidence": {
    "value": 0.0,
    "band": "HIGH|MEDIUM|LOW",
    "reasoning": "string"
  },
  "citations": ["source_type | company_or_sector | period | doc_id/chunk_id"]
}
```
