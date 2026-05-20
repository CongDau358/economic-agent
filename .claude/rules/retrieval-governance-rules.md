# Retrieval Governance Rules

## Principles

Retrieval quality has higher priority than response length.

---

## The system must

- prioritize grounded evidence over fluent but unsupported prose
- prefer trusted sources (official reports, audited filings, government publications) over secondary commentary
- avoid weak retrieval generation: do not expand answers when evidence is sparse, stale, or low-trust
- run retrieval and quality gates before any financial claim or numeric statement
- rerank by semantic relevance, source reliability, and recency; deduplicate near-duplicate chunks
- return `INSUFFICIENT_DATA` when evidence fails minimum thresholds instead of speculating
- attach citations for every material financial claim
- surface explicit warnings when using low-confidence or low-trust retrieval

---

## The system must never

- generate unsupported financial claims (metrics, trends, risks, opportunities) without retrieved evidence
- use low-confidence retrieval without a visible warning in the response (`confidence.warnings` or `retrieval_quality.warnings`)
- mask uncertainty with confident language when evidence is weak or conflicting
- prefer longer answers over shorter, better-grounded answers
- invent companies, periods, metrics, or events not present in retrieved chunks or user-supplied context

---

## Quality gates

| Claim type | Minimum evidence |
|------------|------------------|
| Factual (single metric or event) | ≥ 1 high- or medium-trust chunk directly supporting the claim |
| Strategic (outlook, risk, opportunity) | ≥ 2 supporting chunks, with at least 1 medium-trust or higher |
| Numeric output | Must cite chunk id / source metadata; otherwise omit or mark `INSUFFICIENT_DATA` |

If gates fail → `INSUFFICIENT_DATA` + guidance to upload or filter by `company` / `sector`.

---

## Confidence and warnings

- **HIGH** (≥ 0.70): multiple trusted sources, consistent evidence, strong relevance
- **MEDIUM** (0.45–0.69): partial evidence; answer allowed with assumptions listed
- **LOW** (< 0.45): insufficient or conflicting evidence → prefer `INSUFFICIENT_DATA`; if answering, mandatory warning

Low-trust source dominance (e.g. only `news` or `unknown`) must add a retrieval warning even when an answer is returned.

---

## Related rules

- `rag-rules.md` — grounding and evidence policy
- `retrieval-rules.md` — query preparation and reranking
- `source-priority-rules.md` — trust tiers
- `confidence-scoring-rules.md` — band definitions
- `failure-handling-rules.md` — `INSUFFICIENT_DATA` behavior
- `hallucination-prevention.md` — non-negotiable constraints
