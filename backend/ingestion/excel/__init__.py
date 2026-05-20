__all__ = ["ExcelPipelineResult", "process_excel_document"]


def __getattr__(name: str):
    if name == "ExcelPipelineResult":
        from .pipeline import ExcelPipelineResult

        return ExcelPipelineResult
    if name == "process_excel_document":
        from .pipeline import process_excel_document

        return process_excel_document
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
