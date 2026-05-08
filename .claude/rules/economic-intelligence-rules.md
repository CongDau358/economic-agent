# Economic Intelligence Rules

## Core Rules

- No hallucination.
- Always use retrieved or user-supplied data.
- Always separate:
  - facts
  - signals
  - predictions
- Always assign confidence with reasoning.
- Return `INSUFFICIENT_DATA` when evidence is too sparse.

## Trend Compliance

- Apply deterministic scoring (+1, 0, -1).
- Use fixed weights (0.5, 0.3, 0.2).
- Use fixed thresholds for trend inference.
- Keep outputs reproducible for identical inputs.
