from .metadata import (
    REQUIRED_STORAGE_FIELDS,
    build_chroma_filter,
    extract_year,
    normalize_storage_metadata,
    validate_storage_metadata,
)

__all__ = [
    "REQUIRED_STORAGE_FIELDS",
    "StorageStats",
    "StoredRetrievalResult",
    "VectorStorageSystem",
    "build_chroma_filter",
    "extract_year",
    "normalize_storage_metadata",
    "validate_storage_metadata",
]


def __getattr__(name: str):
    if name in {"StorageStats", "StoredRetrievalResult", "VectorStorageSystem"}:
        from .store import StorageStats, StoredRetrievalResult, VectorStorageSystem

        return {
            "StorageStats": StorageStats,
            "StoredRetrievalResult": StoredRetrievalResult,
            "VectorStorageSystem": VectorStorageSystem,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
