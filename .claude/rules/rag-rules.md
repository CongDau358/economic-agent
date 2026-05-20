# RAG Rules

## Objective
Ensure every answer is grounded in retrieved evidence from the financial knowledge base.

## Rules
- Retrieval must run before analysis unless user explicitly provides complete context.
- Use both semantic relevance and metadata filters whenever possible.
- Keep context windows token-budget aware and deduplicated.
- Include only chunks relevant to the active question intent.
- If retrieval returns weak evidence, answer with `INSUFFICIENT_DATA`.

## Evidence Policy
- All material claims must map to at least one retrieved chunk.
- Prioritize primary financial reports over secondary commentary when available.
- Prefer newer evidence if older evidence is stale or contradicted.

## Failure Behavior
- If no credible evidence is found, do not speculate.
- Ask for additional data sources when needed.

## Governance
- Apply `retrieval-governance-rules.md` for quality gates, trust prioritization, and low-confidence warnings.
