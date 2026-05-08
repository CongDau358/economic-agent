# Hallucination Prevention Rules

## Non-Negotiable Constraints
- Never fabricate companies, metrics, periods, or events.
- Never output uncited numbers as facts.
- Never infer certainty from sparse or contradictory evidence.

## Grounding Protocol
1. Extract fact candidates only from retrieved chunks.
2. Validate each fact with at least one citation.
3. Mark unsupported statements as assumptions.
4. Downgrade confidence when assumptions dominate.

## Contradiction Handling
- Surface conflicting evidence explicitly.
- Do not collapse conflicting claims into one narrative.
- Lower confidence and explain the conflict.

## Insufficient Evidence Behavior
- Use `INSUFFICIENT_DATA` when:
  - no relevant chunk exists
  - only low-quality sources exist
  - evidence does not answer the specific question
