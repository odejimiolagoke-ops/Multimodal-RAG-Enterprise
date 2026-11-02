"""Document extraction and retrieval-augmented generation helpers.

This module keeps file extraction separate from the storage and retrieval code in
pipeline.py. It supports PDF and common text-based files, then indexes chunks so
retrieval can return focused context instead of an entire document.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict, List

from pipeline import insert_document, rag_query

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv", ".json", ".docx"}
DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract text from supported file bytes."""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported file type. Supported types: {supported}")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            pages = PdfReader(io.BytesIO(file_bytes)).pages
            text = "\n".join(page.extract_text() or "" for page in pages)
        except Exception as exc:
            raise ValueError("Could not extract text from the PDF") from exc
    elif suffix == ".docx":
        try:
            from docx import Document

            document = Document(io.BytesIO(file_bytes))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        except ImportError as exc:
            raise ValueError("DOCX extraction requires the python-docx package") from exc
        except Exception as exc:
            raise ValueError("Could not extract text from the DOCX file") from exc
    else:
        try:
            decoded = file_bytes.decode("utf-8-sig")
            text = json.dumps(json.loads(decoded), indent=2) if suffix == ".json" else decoded
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("The file must contain valid UTF-8 text") from exc

    text = text.strip()
    if not text:
        raise ValueError("The file contains no extractable text")
    return text


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks suitable for embedding."""
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    normalized = " ".join(text.split())
    return [
        normalized[start : start + chunk_size]
        for start in range(0, len(normalized), chunk_size - overlap)
        if normalized[start : start + chunk_size]
    ]


def index_file(
    file_bytes: bytes,
    filename: str,
    metadata: Dict[str, Any] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> Dict[str, Any]:
    """Extract and index a file, returning indexing statistics."""
    text = extract_text(file_bytes, filename)
    chunks = chunk_text(text, chunk_size, overlap)
    base_metadata = {"filename": filename, **(metadata or {})}

    for index, chunk in enumerate(chunks):
        insert_document(chunk, {**base_metadata, "chunk": index, "total_chunks": len(chunks)})

    return {"filename": filename, "chunks": len(chunks), "characters": len(text)}


__all__ = ["SUPPORTED_EXTENSIONS", "extract_text", "chunk_text", "index_file", "rag_query"]
