__all__ = ["PdfPipelineResult", "process_pdf_document"]


def __getattr__(name: str):
    if name == "PdfPipelineResult":
        from .pipeline import PdfPipelineResult

        return PdfPipelineResult
    if name == "process_pdf_document":
        from .pipeline import process_pdf_document

        return process_pdf_document
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
