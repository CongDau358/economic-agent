---
name: trend-analysis
description: Deterministic trend synthesis from financial, sentiment, and macro signals with confidence controls.
---

# Trend Analysis

## When to Use

- Build a 1-6 month outlook from mixed evidence.
- Standardize directional forecasting for `/predict` and strategic reports.

## Inputs

- `financial_signals`
- `sentiment_signals`
- `macro_signals`
- optional evidence-quality modifiers

## Steps

1. Map every signal to score (`+1`, `0`, `-1`).
2. Aggregate by category and compute weighted total:
   - Financial: `0.50`
   - Sentiment: `0.30`
   - Macro: `0.20`
3. Infer trend:
   - score > `0.15` -> `UP`
   - score < `-0.15` -> `DOWN`
   - otherwise -> `NEUTRAL`
4. Apply confidence penalties for:
   - stale evidence
   - low source reliability
   - conflicting signals
5. Return trend with rationale and assumptions.

## Output Format

```json
{
  "summary": "string",
  "signals": {
    "financial": [],
    "sentiment": [],
    "macro": []
  },
  "score": {
    "financial": 0.0,
    "sentiment": 0.0,
    "macro": 0.0,
    "total": 0.0
  },
  "trend": "UP|DOWN|NEUTRAL|INSUFFICIENT_DATA",
  "confidence": {
    "value": 0.0,
    "band": "HIGH|MEDIUM|LOW",
    "reasoning": "string"
  },
  "assumptions": []
}
```

## Guardrails

- Keep scoring deterministic and reproducible.
- Do not alter category weights without explicit system governance.
- Use `INSUFFICIENT_DATA` when evidence quantity/quality fails minimum threshold.
