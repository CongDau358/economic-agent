# News Sentiment Analysis Skill

## When to Use
- Analyze market sentiment from financial news and social data.
- Detect narrative shifts affecting company or sector outlook.

## Inputs
- Retrieved news/social chunks
- Entity scope (`company`, `sector`, `ticker`)
- Optional time window

## Workflow
1. Classify sentiment per chunk (`positive`, `neutral`, `negative`).
2. Extract event triggers (regulation, earnings, funding, controversy).
3. Weight sentiment by source reliability and recency.
4. Detect momentum (improving, stable, deteriorating).
5. Produce sentiment summary with cited events.

## Output Schema
- `sentiment_distribution`
- `event_triggers`
- `momentum_assessment`
- `confidence`
- `citations`

## Guardrails
- Separate sentiment from factual business performance.
- Penalize noisy social signals if unsupported by credible sources.
