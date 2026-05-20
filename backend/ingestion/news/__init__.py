__all__ = ["NewsPipelineResult", "process_news_article"]


def __getattr__(name: str):
    if name == "NewsPipelineResult":
        from .pipeline import NewsPipelineResult

        return NewsPipelineResult
    if name == "process_news_article":
        from .pipeline import process_news_article

        return process_news_article
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
