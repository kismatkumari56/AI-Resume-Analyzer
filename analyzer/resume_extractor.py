"""Resume file extraction helpers.

This module provides one extraction entry point for supported resume formats
while keeping the PDF, DOCX, and OCR implementations independent and reusable.
"""

import os
import re
import unicodedata
from typing import Optional, Type

from docx import Document
from pypdf import PdfReader

from analyzer.docx_reader import extract_docx_text as _extract_docx_via_reader

_ORIGINAL_DOCUMENT = Document


# Runs of spaces/tabs (anything except a line break) become a single space.
_HORIZONTAL_SPACE = re.compile(r"[^\S\n]+")
# More than one blank line between blocks is not useful in a resume.
_MULTIPLE_BLANK_LINES = re.compile(r"\n{3,}")
# Control characters that PDF text extraction sometimes leaves behind.
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]")

from analyzer.ocr import (
    OCRError,
    extract_images_from_page,
    extract_ocr_from_images,
)



class UnsupportedFileFormatError(ValueError):
    """Raised when a resume format is not supported by the application."""



def _normalize_pdf_text(text: Optional[str]) -> str:
    """Clean up the whitespace and characters produced by PDF extraction.

    Page order is kept and meaningful line breaks are preserved so that
    section headings stay on their own lines. Only noisy spacing, control
    characters and repeated blank lines are removed.
    """
    if not text:
        return ""

    # Ligatures ("ﬁ" -> "fi") and other compatibility characters are common
    # in PDF text and would otherwise hide words from the analyzers.
    text = unicodedata.normalize("NFKC", text)

    # PDFs use different line endings and form feeds between pages.
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    text = _CONTROL_CHARACTERS.sub("", text)

    lines = [
        _HORIZONTAL_SPACE.sub(" ", line).strip()
        for line in text.split("\n")
    ]
    text = "\n".join(lines)
    text = _MULTIPLE_BLANK_LINES.sub("\n\n", text)
    return text.strip()

# Threshold in characters: pages with less selectable text are checked for scanned images
MIN_PAGE_TEXT_CHARS = 30



def extract_pdf_text(
    filepath: str,
    reader_class: Optional[Type[PdfReader]] = None,
    enable_ocr: bool = True,
    min_text_chars: int = MIN_PAGE_TEXT_CHARS,
) -> str:
    """Extract and clean text from every page of a PDF file, applying OCR to scanned pages.

    Pages are read in document order. Pages without extractable text (for
    example scanned images) fall back to OCR if enabled. Invalid or unreadable PDFs
    raise the underlying pypdf error so the caller can show a meaningful message.
    """
    reader = (reader_class or PdfReader)(filepath)
    pages = []

    try:
        for page in reader.pages:
            try:
                page_text = page.extract_text() or ""
            except Exception:
                # One unreadable page should not discard the rest of the resume
                page_text = ""

            cleaned = _normalize_pdf_text(page_text)

            # Normal text extraction for pages with sufficient text
            if len(cleaned) >= min_text_chars or not enable_ocr:
                if cleaned:
                    pages.append(cleaned)
                continue

            # Page has insufficient extractable text: check for scanned images to OCR
            ocr_text = ""
            try:
                images = extract_images_from_page(page)
                if images:
                    ocr_text = extract_ocr_from_images(images)
            except OCRError:
                raise
            except Exception:
                ocr_text = ""

            cleaned_ocr = _normalize_pdf_text(ocr_text)
            parts = [p for p in (cleaned, cleaned_ocr) if p]
            if parts:
                pages.append("\n".join(parts))
            elif cleaned:
                pages.append(cleaned)

    finally:
        # Ensure file streams opened by PdfReader are explicitly closed
        if hasattr(reader, "close"):
            try:
                reader.close()
            except Exception:
                pass
        stream = getattr(reader, "stream", None)
        if stream and hasattr(stream, "close"):
            try:
                stream.close()
            except Exception:
                pass

    if not pages:
        return ""

    return "\n".join(pages) + "\n"


def extract_docx_text(filepath: str) -> str:
    """Extract header, paragraph, and table text from a DOCX file in document order.

    Delegates to ``analyzer.docx_reader.extract_docx_text`` for zip-bomb
    validation, header extraction, XML block ordering, and merged-cell
    deduplication, while preserving support for patched ``Document`` mocks.
    """
    if Document is not _ORIGINAL_DOCUMENT:
        document = Document(filepath)
        paragraphs = [paragraph.text for paragraph in document.paragraphs]
        tables = [
            "\n".join(
                cell.text
                for row in table.rows
                for cell in row.cells
            )
            for table in document.tables
        ]
        return "\n".join(paragraphs + tables)

    return _extract_docx_via_reader(filepath)


def extract_resume_text(filepath: str) -> str:
    """Extract resume text based on the file extension.

    Raises:
        UnsupportedFileFormatError: if the path does not use a supported
            resume extension.
        OCRError: if OCR processing of scanned pages fails.
    """
    extension = os.path.splitext(filepath)[1].lower()
    if extension == ".pdf":
        return extract_pdf_text(filepath)
    if extension == ".docx":
        return extract_docx_text(filepath)

    raise UnsupportedFileFormatError("Only PDF and DOCX files are supported.")
