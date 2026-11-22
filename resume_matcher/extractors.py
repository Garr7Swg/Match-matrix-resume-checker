"""In-memory text extraction for common resume and office document formats."""

from __future__ import annotations

import csv
import html
import io
import json
import re
from pathlib import Path
from typing import Any


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_EXTRACTED_CHARS = 45_000


class DocumentProcessingError(Exception):
    """Raised when a file cannot be safely converted to usable text."""


def _text_from_docx(data: bytes) -> str:
    from docx import Document

    document = Document(io.BytesIO(data))
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _text_from_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data), strict=False)
    if reader.is_encrypted:
        try:
            if reader.decrypt("") == 0:
                raise DocumentProcessingError("Encrypted PDF")
        except Exception as exc:
            raise DocumentProcessingError("Encrypted PDF") from exc
    if len(reader.pages) > 100:
        raise DocumentProcessingError("PDF exceeds page limit")
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _text_from_xlsx(data: bytes) -> str:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    parts: list[str] = []
    try:
        for sheet in workbook.worksheets:
            parts.append(sheet.title)
            for row in sheet.iter_rows(values_only=True):
                values = [str(value) for value in row if value is not None]
                if values:
                    parts.append(" | ".join(values))
    finally:
        workbook.close()
    return "\n".join(parts)


def _text_from_pptx(data: bytes) -> str:
    from pptx import Presentation

    presentation = Presentation(io.BytesIO(data))
    parts: list[str] = []
    for slide in presentation.slides:
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False):
                parts.append(shape.text)
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _text_from_odt(data: bytes) -> str:
    from odf.opendocument import load
    from odf.teletype import extractText
    from odf.text import P

    document = load(io.BytesIO(data))
    return "\n".join(extractText(node) for node in document.getElementsByType(P))


def _text_from_image(data: bytes) -> str:
    from PIL import Image
    import pytesseract

    with Image.open(io.BytesIO(data)) as image:
        return pytesseract.image_to_string(image, timeout=30)


def _text_from_rtf(value: str) -> str:
    value = re.sub(r"\\'[0-9a-fA-F]{2}", " ", value)
    value = re.sub(r"\\u-?\d+\??", " ", value)
    value = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", value)
    value = value.replace("{", " ").replace("}", " ").replace("\\~", " ")
    return html.unescape(value)


def extract_document_text(filename: str, data: bytes) -> str:
    """Extract text from an uploaded file without writing it to disk."""

    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise DocumentProcessingError("Empty or oversized upload")

    extension = Path(filename).suffix.lower()
    try:
        if extension == ".pdf":
            text = _text_from_pdf(data)
        elif extension == ".docx":
            text = _text_from_docx(data)
        elif extension == ".xlsx":
            text = _text_from_xlsx(data)
        elif extension == ".pptx":
            text = _text_from_pptx(data)
        elif extension == ".odt":
            text = _text_from_odt(data)
        elif extension in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
            text = _text_from_image(data)
        elif extension in {".txt", ".md", ".csv", ".json", ".html", ".htm", ".xml", ".rtf"}:
            decoded = data.decode("utf-8-sig")
            if extension == ".rtf":
                text = _text_from_rtf(decoded)
            elif extension in {".html", ".htm", ".xml"}:
                from bs4 import BeautifulSoup

                text = BeautifulSoup(decoded, "html.parser").get_text("\n")
            elif extension == ".json":
                text = json.dumps(json.loads(decoded), ensure_ascii=False, indent=2)
            elif extension == ".csv":
                rows = csv.reader(io.StringIO(decoded))
                text = "\n".join(" | ".join(row) for row in rows)
            else:
                text = decoded
        else:
            raise DocumentProcessingError("Unsupported file type")
    except DocumentProcessingError:
        raise
    except Exception as exc:
        raise DocumentProcessingError("Could not extract document text") from exc

    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized or not normalized.strip():
        raise DocumentProcessingError("No readable text found")
    if len(normalized) > MAX_EXTRACTED_CHARS:
        raise DocumentProcessingError("Extracted text exceeds processing limit")
    return normalized

