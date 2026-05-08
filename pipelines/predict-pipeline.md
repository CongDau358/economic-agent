# Predict Pipeline

## Purpose
Generate short-term financial/economic trend outlooks using historical trend memory, policy context, and retrieval-grounded signals.

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
   - classify as trend prediction / short-term outlook.
   - detect target scope (company, industry, market segment, timeframe).
   - constrain output horizon to short-term only.

2. **Memory Retrieval**
   - access global knowledge memory for validated historical patterns.
   - retrieve from vector memory:
     - historical trend records
     - prior performance reports
     - historical sentiment trajectories
     - historical policy signals
   - retrieve macroeconomic context memory:
     - rates, inflation, liquidity, regulation signals

3. **Metadata Filtering**
   - apply filters using:
     - `company`
     - `industry`
     - `year`
     - `source_type`
     - `document_type`
     - `recency`
   - enforce temporal alignment for historical trend comparisons.

4. **Source Ranking**
   - prioritize:
     - official reports
     - audited financial statements
     - government publications
     - trusted financial news
   - treat low-trust sources as weak secondary indicators.

5. **Retrieval Validation**
   - remove duplicate/near-duplicate chunks.
   - remove low-relevance chunks.
   - validate source trustworthiness and historical coverage adequacy.
   - if historical grounding is insufficient, return `INSUFFICIENT_DATA`.

6. **Reasoning**
   - run `trend-analysis`.
   - synthesize:
     - current financial signals
     - historical trend memory
     - policy change signals
     - macroeconomic context
   - produce directional short-term outlook only.

7. **Evaluation**
   - evaluate:
     - grounding completeness
     - consistency across historical and current evidence
     - forecast uncertainty under conflicting signals
   - compute confidence with penalties for stale/contradictory evidence.

8. **Output Formatting**
   - include:
     - short-term trend outlook
     - score breakdown
     - risks and opportunities
     - confidence and assumptions
     - citations

## Retrieval Optimization Behavior
- Boost policy and macro documents when query contains regulatory or macro keywords.
- Require minimum historical depth for trend prediction reliability.
- Suppress long-term extrapolation beyond short-term horizon.

## Required Skills
- `trend-analysis`
- `news-sentiment-analysis`
- `financial-report-analysis`

## Required Rules
- `intent-classification-rules.md`
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
  "scope": {
    "company": "string|null",
    "industry": "string|null",
    "timeframe": "string"
  },
  "short_term_outlook": "UP|DOWN|NEUTRAL|INSUFFICIENT_DATA",
  "score_breakdown": {
    "financial": 0.0,
    "sentiment": 0.0,
    "macro": 0.0,
    "total": 0.0
  },
  "historical_support": {
    "past_trends": ["string"],
    "historical_sentiment": ["string"],
    "policy_signals": ["string"],
    "macro_context": ["string"]
  },
  "risks": ["string"],
  "opportunities": ["string"],
  "confidence": {
    "value": 0.0,
    "band": "HIGH|MEDIUM|LOW",
    "reasoning": "string"
  },
  "assumptions": ["string"],
  "citations": ["source_type | company_or_industry | period | doc_id/chunk_id"]
}
```
