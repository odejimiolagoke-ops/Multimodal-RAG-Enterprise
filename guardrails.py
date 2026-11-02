from __future__ import annotations

from io import BytesIO
import unicodedata

from fastapi import HTTPException, UploadFile

MAX_INPUT_CHARS = 4_000
MAX_OUTPUT_CHARS = 8_000
MAX_CONTEXT_CHARS = 12_000
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000


def validate_text_input(value: str, field_name: str = "text") -> str:
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail=f"{field_name} must be text")

    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail=f"{field_name} must not be empty")
    if len(normalized) > MAX_INPUT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"{field_name} exceeds the {MAX_INPUT_CHARS}-character limit",
        )
    if any(unicodedata.category(char) == "Cc" and char not in "\n\r\t" for char in normalized):
        raise HTTPException(status_code=422, detail=f"{field_name} contains unsupported control characters")
    return normalized


def validate_text_output(value: object) -> str:
    if not isinstance(value, str):
        raise HTTPException(status_code=502, detail="Generated response was not valid text")

    normalized = "".join(
        char
        for char in value.strip()
        if char in "\n\r\t" or unicodedata.category(char) != "Cc"
    )
    if not normalized:
        raise HTTPException(status_code=502, detail="Generated response was empty")
    if len(normalized) > MAX_OUTPUT_CHARS:
        raise HTTPException(
            status_code=502,
            detail=f"Generated response exceeds the {MAX_OUTPUT_CHARS}-character limit",
        )
    return normalized


async def read_guarded_upload(file: UploadFile, max_bytes: int, label: str) -> bytes:
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"{label} exceeds the upload size limit")
    if not content:
        raise HTTPException(status_code=422, detail=f"{label} must not be empty")
    return content


def validate_image_bytes(content: bytes) -> None:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Pillow is required to validate image uploads") from exc

    try:
        with Image.open(BytesIO(content)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(status_code=422, detail="Image must be a JPEG, PNG, or WebP file")
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=413, detail="Image dimensions exceed the allowed limit")
            image.verify()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=422, detail="Image upload is invalid or corrupted") from exc
