# Memory Architecture

## Purpose
Provide persistent knowledge storage and retrieval support for the Financial Intelligence Agent.

## Memory Layers

### 1. Raw Data Layer
Stores:
- PDF
- Excel
- news
- reports
- text documents

### 2. Processed Chunk Layer
Stores:
- cleaned chunks
- normalized text
- structured segments

### 3. Embedding Layer
Stores:
- vector embeddings
- semantic representations

### 4. Metadata Layer
Stores:
- company
- industry
- year
- source
- document type

### 5. Knowledge Layer
Stores:
- inferred trends
- sector insights
- long-term patterns

## Retrieval Use
- Query-time retrieval starts from embedding similarity, then applies metadata filters.
- Knowledge layer outputs are advisory and must always map back to cited chunk evidence.

## Persistence Model
- Raw, processed, embeddings, and metadata are persisted.
- Knowledge artifacts are versioned snapshots derived from evidence and should be recomputable.
