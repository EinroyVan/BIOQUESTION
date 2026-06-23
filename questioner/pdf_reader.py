"""Extract text from PDF files with native parsing and OCR fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import fitz
import numpy as np

MIN_NATIVE_CHARS = 40
OCR_ZOOM = 2.0

_ocr_engine = None


@dataclass
class PdfExtractionResult:
    text: str
    page_count: int
    native_text_pages: int
    ocr_pages: int

    @property
    def summary(self) -> str:
        if self.ocr_pages == 0:
            return f"{self.page_count} page(s), all text-native PDF"
        if self.native_text_pages == 0:
            return f"{self.page_count} page(s), all processed via OCR"
        return (
            f"{self.page_count} page(s): {self.native_text_pages} text-extracted, "
            f"{self.ocr_pages} OCR"
        )


def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr_engine = RapidOCR()
    return _ocr_engine


def _ocr_page(page: fitz.Page) -> str:
    matrix = fitz.Matrix(OCR_ZOOM, OCR_ZOOM)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, 3
    )
    lines, _ = _get_ocr_engine()(image)
    if not lines:
        return ""
    return "\n".join(str(line[1]).strip() for line in lines if line[1])


def extract_text_from_pdf(
    pdf_bytes: bytes,
    *,
    use_ocr: bool = True,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> PdfExtractionResult:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_count = doc.page_count
    chunks: list[str] = []
    native_pages = 0
    ocr_pages = 0

    for index in range(page_count):
        page = doc[index]
        native_text = page.get_text("text").strip()

        if len(native_text) >= MIN_NATIVE_CHARS:
            chunks.append(native_text)
            native_pages += 1
            if on_progress:
                on_progress(index + 1, page_count, "text")
        elif use_ocr:
            if on_progress:
                on_progress(index + 1, page_count, "ocr")
            ocr_text = _ocr_page(page).strip()
            chunks.append(ocr_text)
            ocr_pages += 1
        else:
            chunks.append(native_text)

    doc.close()
    full_text = "\n\n".join(chunk for chunk in chunks if chunk).strip()
    return PdfExtractionResult(
        text=full_text,
        page_count=page_count,
        native_text_pages=native_pages,
        ocr_pages=ocr_pages,
    )


def load_uploaded_document(
    filename: str,
    content: bytes,
    *,
    use_ocr: bool = True,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> tuple[str, PdfExtractionResult | None]:
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        result = extract_text_from_pdf(content, use_ocr=use_ocr, on_progress=on_progress)
        if not result.text:
            raise ValueError("No text extracted from PDF; file may be blank or low image quality.")
        return result.text, result

    if lower_name.endswith(".txt"):
        text = content.decode("utf-8", errors="replace").strip()
        if not text:
            raise ValueError("Text file is empty.")
        return text, None

    raise ValueError("Only .txt and .pdf files are supported.")
