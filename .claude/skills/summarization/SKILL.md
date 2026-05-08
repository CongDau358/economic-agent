---
name: summarization
description: Produces concise economic summaries while separating facts, signals, and interpretation.
---

# Summarization

## When to Use

- After ingestion completes.
- Before trend prediction or reporting.
- When user asks for a concise overview.

## Steps

1. Extract explicit facts from retrieved chunks.
2. Derive candidate signals from facts.
3. Keep predictions separate from observations.
4. Return a compact summary with evidence references.

## Output Format

```json
{
  "facts": [],
  "signals": {
    "financial": [],
    "sentiment": [],
    "macro": []
  },
  "summary": "string",
  "notes": "facts and predictions are explicitly separated"
}
```
