import logging
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image
from pillow_heif import register_heif_opener
from starlette.concurrency import run_in_threadpool

register_heif_opener()

logger = logging.getLogger(__name__)

IMAGES_DIR = Path("images")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF"}

_SAVE_PARAMS: dict[str, dict] = {
    "JPEG": {"quality": 95, "optimize": True},
    "PNG": {"optimize": True},
    "WEBP": {"quality": 95, "method": 6},
}

_EXT: dict[str, str] = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}


def _process_image(contents: bytes) -> tuple[Image.Image, str, str]:
    """Open, validate, and determine output format. Returns (image, save_format, extension)."""
    try:
        img = Image.open(BytesIO(contents))
        img.load()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")

    if img.format not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported format '{img.format}'. Allowed: JPEG, PNG, WebP, HEIC/HEIF",
        )

    # HEIF → JPEG (browsers don't universally support HEIC rendering)
    save_format = "JPEG" if img.format == "HEIF" else img.format

    # JPEG requires RGB; drop alpha channel if present when converting to JPEG
    if save_format == "JPEG" and img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    return img, save_format, _EXT[save_format]


def _write_image(img: Image.Image, save_format: str, ext: str) -> str:
    """Save image to disk, return URL path."""
    filename = f"{uuid.uuid4()}.{ext}"
    dest = IMAGES_DIR / filename
    img.save(dest, format=save_format, **_SAVE_PARAMS[save_format])
    logger.info("Saved image %s (format=%s)", filename, save_format)
    return f"/images/{filename}"


async def save_image(file: UploadFile) -> str:
    contents = await file.read()

    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large, max 10 MB")

    return await run_in_threadpool(
        lambda: _write_image(*_process_image(contents))
    )


def delete_image_file(url: str) -> None:
    filename = url.lstrip("/").removeprefix("images/")
    path = IMAGES_DIR / filename
    try:
        path.unlink()
        logger.info("Deleted image %s", filename)
    except FileNotFoundError:
        logger.warning("Image not found for deletion: %s", filename)
    except OSError as exc:
        logger.error("Failed to delete image %s: %s", filename, exc)
