# RAG Query Reasoning Skill

## When to Use
- Answer user financial questions using retrieved evidence.
- Generate grounded multi-source explanations with citations.

## Inputs
- user query
- optional metadata filters
- retrieved chunks from vector DB

## Workflow
1. Classify query intent and scope.
2. Retrieve and rerank evidence chunks.
3. Check evidence sufficiency threshold.
4. Build response in layers:
   - facts
   - signals
   - interpretation
   - outlook
5. Attach citations to all material claims.
6. Provide confidence score and uncertainty notes.

## Output Schema
- `answer`
- `evidence_snapshot`
- `confidence`
- `assumptions`
- `citations`

## Guardrails
- No uncited numeric claims.
- If evidence is weak, return `INSUFFICIENT_DATA` plus data request guidance.
