---
name: rag-query
description: Retrieves relevant chunks from vector DB and answers economic questions with evidence grounding.
---

# RAG Query

## When to Use

- User asks data-grounded financial questions.
- User asks why a trend was inferred.
- User requests source-backed analysis.

## Steps

1. Parse question intent and filters.
2. Retrieve top-k chunks from vector DB.
3. Apply company/sector filters.
4. Build answer strictly from retrieved data.
5. Return confidence and evidence snippets.

## Output Format

```json
{
  "answer": "string",
  "evidence": [],
  "confidence": {
    "value": 0.0,
    "reasoning": "string"
  }
}
```
