---
name: report-generation
description: Produces final structured economic intelligence report for stakeholders and downstream APIs.
---

# Report Generation

## When to Use

- User runs `/report`.
- User asks for complete structured output.

## Steps

1. Collect summary, signals, score, trend.
2. Merge risks and opportunities.
3. Add confidence with rationale.
4. Emit stable machine-readable format.

## Output Format

```json
{
  "summary": "string",
  "signals": {},
  "score": {},
  "trend": "string",
  "risks": [],
  "opportunities": [],
  "confidence": {}
}
```
