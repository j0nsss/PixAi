"""File parsing utilities for PDF, TXT, MD, JSON."""

from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pypdf

from config import (
    SUPPORTED_EXTENSIONS,
    MAX_FILE_SIZE_MB,
    MAX_PDF_PAGES,
    ATTACHMENT_MAX_CHARS,
)

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result of parsing a file."""

    text: str = ""
    ok: bool = False
    warnings: List[str] = field(default_factory=list)
    source: str = ""


def _decode_text(raw: bytes) -> str:
    """Decode bytes trying multiple encodings."""
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    # latin-1 never fails
    return raw.decode("latin-1")


def _normalize_newlines(text: str) -> str:
    """Normalize line endings and collapse excessive newlines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _parse_text(path: Path) -> ParseResult:
    """Parse text/markdown file."""
    result = ParseResult(source=str(path))
    try:
        raw = path.read_bytes()
        text = _decode_text(raw)
        text = _normalize_newlines(text)
        if not text.strip():
            result.warnings.append("file is empty")
            return result
        result.text = text
        result.ok = True
    except Exception:
        logger.exception("Failed to parse text file %s", path)
        result.warnings.append("parse error")
    return result


def _parse_json(path: Path) -> ParseResult:
    """Parse JSON file."""
    result = ParseResult(source=str(path))
    try:
        raw = path.read_bytes()
        text = _decode_text(raw)
        try:
            obj = json.loads(text)
            result.text = json.dumps(obj, indent=2, ensure_ascii=False)
            result.ok = True
        except json.JSONDecodeError:
            # Fall back to raw text
            result.text = _normalize_newlines(text)
            result.warnings.append("invalid JSON, used raw text")
            result.ok = True
    except Exception:
        logger.exception("Failed to parse JSON file %s", path)
        result.warnings.append("parse error")
    return result


def _parse_pdf(path: Path) -> ParseResult:
    """Parse PDF file with fallback extraction modes."""
    result = ParseResult(source=str(path))
    skipped_pages = 0

    try:
        reader = pypdf.PdfReader(str(path))
    except pypdf.errors.PdfReadError as e:
        logger.exception("PDF read error for %s", path)
        result.warnings.append("corrupted or unreadable PDF")
        return result
    except Exception:
        logger.exception("Failed to open PDF %s", path)
        result.warnings.append("corrupted or unreadable PDF")
        return result

    if reader.is_encrypted:
        try:
            if reader.decrypt("") == 0:
                result.warnings.append("PDF is password-protected")
                return result
        except Exception:
            result.warnings.append("PDF is password-protected")
            return result

    pages_to_read = reader.pages[:MAX_PDF_PAGES]
    if len(reader.pages) > MAX_PDF_PAGES:
        result.warnings.append(f"only first {MAX_PDF_PAGES} pages read")

    texts: List[str] = []
    for i, page in enumerate(pages_to_read):
        page_text = ""
        # Try default extraction
        try:
            page_text = page.extract_text() or ""
        except Exception:
            logger.debug("extract_text() failed for page %d of %s", i, path)

        # If empty or whitespace, try layout mode
        if not page_text.strip():
            try:
                page_text = page.extract_text(extraction_mode="layout") or ""
            except Exception:
                logger.debug("extract_text(layout) failed for page %d of %s", i, path)

        if not page_text.strip():
            skipped_pages += 1
            continue

        texts.append(page_text.strip())

    if not texts:
        result.warnings.append(
            "no extractable text (probably a scanned/image-only PDF; OCR is not supported)"
        )
        return result

    full_text = "\n\n".join(texts)
    full_text = _normalize_newlines(full_text)

    if not full_text.strip():
        result.warnings.append(
            "no extractable text (probably a scanned/image-only PDF; OCR is not supported)"
        )
        return result

    result.text = full_text
    result.ok = True

    if skipped_pages > 0:
        result.warnings.append(f"{skipped_pages} pages had no extractable text")

    return result


def parse_file(path: Path) -> ParseResult:
    """Parse a file based on its extension. Never raises."""
    result = ParseResult(source=str(path))

    try:
        # Pre-checks
        if not path.exists():
            result.warnings.append("file not found")
            return result

        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            result.warnings.append("unsupported type")
            return result

        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            result.warnings.append(f"file too large (> {MAX_FILE_SIZE_MB} MB)")
            return result

        if path.stat().st_size == 0:
            result.warnings.append("file is empty")
            return result

        # Dispatch by extension
        if ext in {".txt", ".md"}:
            return _parse_text(path)
        elif ext == ".json":
            return _parse_json(path)
        elif ext == ".pdf":
            return _parse_pdf(path)
        else:
            result.warnings.append("unsupported type")
            return result

    except Exception:
        logger.exception("Unexpected error parsing %s", path)
        result.warnings.append("parse error")
        return result


def parse_attachment(path: Path, max_chars: int = ATTACHMENT_MAX_CHARS) -> ParseResult:
    """Parse a file for attachment, truncating if necessary."""
    result = parse_file(path)
    if result.ok and len(result.text) > max_chars:
        result.text = result.text[:max_chars] + "\n[…truncated]"
        result.warnings.append(f"attachment truncated to {max_chars} characters")
    return result