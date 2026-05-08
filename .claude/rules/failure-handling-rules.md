# Failure Handling Rules

## Principles

- The agent must never fabricate financial information.

## Retrieval Failure

IF:
- no relevant chunk found
- retrieval score below threshold

THEN:
- return `INSUFFICIENT_DATA`

## Conflicting Evidence

IF:
- multiple sources conflict

THEN:
- report inconsistency explicitly
- reduce confidence score

## Missing Financial Metrics

IF:
- required metrics are unavailable

THEN:
- state: `Financial data not available in current dataset.`
