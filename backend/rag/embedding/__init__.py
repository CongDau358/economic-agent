from .normalizer import normalize_chunk_text, normalize_query_text

__all__ = [
    "EmbeddingBatchResult",
    "EmbeddingPipeline",
    "EmbeddedRecord",
    "normalize_chunk_text",
    "normalize_query_text",
]


def __getattr__(name: str):
    if name in {"EmbeddingBatchResult", "EmbeddingPipeline", "EmbeddedRecord"}:
        from .pipeline import EmbeddingBatchResult, EmbeddingPipeline, EmbeddedRecord

        return {
            "EmbeddingBatchResult": EmbeddingBatchResult,
            "EmbeddingPipeline": EmbeddingPipeline,
            "EmbeddedRecord": EmbeddedRecord,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
