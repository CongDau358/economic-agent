# Global Memory System

## Purpose
Create a shared persistent knowledge base across all users and workflows.

## Principles

### Shared Knowledge
All validated financial and economic data may become part of the global knowledge base.

### Persistent Retrieval
Knowledge remains retrievable after ingestion.

### Source Grounding
All stored memory must:
- map to source documents
- contain metadata
- preserve traceability

## Restrictions

The system must never:
- overwrite trusted data without validation
- store hallucinated content
- store unsupported conclusions

## Implementation Notes
- New memory writes must pass validation and grounding checks before persistence.
- Trusted records should use versioned updates, not blind replacement.
- Unsupported conclusions must be kept out of persistent memory and treated as temporary reasoning only.
