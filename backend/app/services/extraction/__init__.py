"""Text extraction pipeline (native text first, OCR only where needed)."""
from .base import ExtractionResult, PageText
from .extractor import extract_document
from .ocr import ocr_available, ocr_status, reset_engine_cache

__all__ = ["ExtractionResult", "PageText", "extract_document", "ocr_available", "ocr_status",
           "reset_engine_cache"]
