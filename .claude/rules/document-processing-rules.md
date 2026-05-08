# Document Processing Rules

## Intake Rules
- Validate source type before processing (`pdf`, `excel`, `news`, `social`, `text`).
- Record ingestion timestamp and source provenance.
- Reject unsupported file types with explicit errors.

## Normalization Rules
- Standardize:
  - date formats
  - currency notation
  - percentage formatting
  - unit abbreviations
- Preserve original values in lineage fields for auditability.

## Source-Specific Rules
- PDF: capture page references and table locations.
- Excel: capture sheet names and cell ranges for citations.
- News/social: capture author, URL, publisher, and publish time.

## Reliability Rules
- Assign source reliability labels (`high`, `medium`, `low`).
- Penalize low reliability during reranking and confidence scoring.
- Deduplicate records before chunking and embedding.

## Lineage Rules
- Maintain chain:
  - raw source -> normalized document -> chunk -> embedding -> citation
