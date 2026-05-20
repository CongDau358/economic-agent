from __future__ import annotations

import os
from typing import Tuple

from langchain_community.embeddings import FakeEmbeddings
from langchain_core.embeddings import Embeddings

from .constants import (
    EMBEDDING_DIMENSION_FALLBACK,
    EMBEDDING_DIMENSION_OPENAI,
    EMBEDDING_MODEL_FALLBACK,
    EMBEDDING_MODEL_OPENAI,
)


def resolve_embedding_model() -> Tuple[str, Embeddings, int]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        try:
            from langchain_openai import OpenAIEmbeddings  # noqa: PLC0415

            return (
                EMBEDDING_MODEL_OPENAI,
                OpenAIEmbeddings(model=EMBEDDING_MODEL_OPENAI, api_key=api_key),
                EMBEDDING_DIMENSION_OPENAI,
            )
        except ImportError:
            from langchain_community.embeddings import OpenAIEmbeddings  # noqa: PLC0415

            return (
                EMBEDDING_MODEL_OPENAI,
                OpenAIEmbeddings(model=EMBEDDING_MODEL_OPENAI, openai_api_key=api_key),
                EMBEDDING_DIMENSION_OPENAI,
            )

    return (
        EMBEDDING_MODEL_FALLBACK,
        FakeEmbeddings(size=EMBEDDING_DIMENSION_FALLBACK),
        EMBEDDING_DIMENSION_FALLBACK,
    )
