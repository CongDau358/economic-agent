# Financial Report Analysis Skill

## When to Use
- Analyze quarterly/annual reports or statement extracts.
- Explain company financial condition from retrieved evidence.
- Build trend signals from structured financial text/table context.

## Inputs
- Retrieved report chunks with metadata
- Optional focus area (`profitability`, `liquidity`, `leverage`, `growth`)
- Optional period scope

## Workflow
1. Extract cited facts: revenue, margin, cash flow, debt, working capital.
2. Compare directional changes across periods when available.
3. Convert facts to financial signals (`positive`, `neutral`, `negative`).
4. Identify key drivers behind each signal.
5. Output concise analysis with citations and confidence notes.

## Output Schema
- `facts`
- `financial_signals`
- `driver_analysis`
- `risk_flags`
- `citations`

## Guardrails
- Do not compute unavailable metrics from missing denominator values.
- Use `INSUFFICIENT_DATA` when period comparability is missing.
