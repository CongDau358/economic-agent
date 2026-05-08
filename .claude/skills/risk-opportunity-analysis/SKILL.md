---
name: risk-opportunity-analysis
description: Converts scored signals into explicit risks and opportunities with causal explanations.
---

# Risk Opportunity Analysis

## When to Use

- Immediately after trend-analysis.
- User asks for downside and upside insights.

## Steps

1. Read scored signals and trend.
2. Map negative signals to risks.
3. Map positive signals to opportunities.
4. Remove duplicates and keep evidence alignment.

## Output Format

```json
{
  "risks": [],
  "opportunities": [],
  "cause_effect": []
}
```
