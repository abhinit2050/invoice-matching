from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass
class PDFTextResult:
    text: str | None
    error: str | None

    @property
    def ok(self) -> bool:
        return self.error is None


def extract_text(path: str | Path) -> PDFTextResult:
    """Extract text from a PDF. Never raises: unreadable/encrypted/empty/non-PDF
    files all come back as a PDFTextResult with `error` set instead of an
    exception, so callers (LangGraph nodes, Streamlit) can report the problem
    without crashing."""
    path = Path(path)

    if not path.exists():
        return PDFTextResult(text=None, error=f"File not found: {path}")

    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001 - any open failure means "unreadable"
        return PDFTextResult(text=None, error=f"Could not open '{path.name}' as a PDF: {exc}")

    with doc:
        if not doc.is_pdf:
            return PDFTextResult(text=None, error=f"'{path.name}' is not a valid PDF file.")

        if doc.is_encrypted:
            if not doc.authenticate(""):
                return PDFTextResult(text=None, error=f"'{path.name}' is password-protected and could not be opened.")

        try:
            pages_text = [page.get_text() for page in doc]
        except Exception as exc:  # noqa: BLE001
            return PDFTextResult(text=None, error=f"Failed to read text from '{path.name}': {exc}")

    text = "\n".join(pages_text).strip()
    if not text:
        return PDFTextResult(
            text=None,
            error=f"'{path.name}' contains no extractable text (it may be a blank or scanned/image-only PDF).",
        )

    return PDFTextResult(text=text, error=None)
