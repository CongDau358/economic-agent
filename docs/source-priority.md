# Source Priority

## High Trust Sources
- official financial reports
- government publications
- audited reports

## Medium Trust Sources
- major financial news
- industry analysis

## Low Trust Sources
- unverified blogs
- anonymous sources

## Retrieval Behavior

Higher trust sources:
- receive ranking boost
- increase confidence score

## Implementation Notes
- Trust level should be assigned during ingestion and stored in metadata.
- Retrieval reranking should apply source-priority weighting before final context assembly.
- Confidence scoring should include a positive adjustment when evidence is dominated by high-trust sources.
