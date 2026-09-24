"""Turn image files into data URIs so the built deck has no external assets."""

import base64
import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from akceo.errors import DeckError

MIME = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
SAVE_OPTIONS: dict[str, dict[str, Any]] = {"PNG": {}, "JPEG": {"quality": 90}, "WEBP": {"quality": 90}}


def data_uri(path: Path, max_px: int) -> str:
    """Embed an image, shrinking raster formats so the longest side is at most max_px. SVG is embedded
    as-is. Mermaid .mmd diagrams don't come here; the page draws them (see akceo.mermaid)."""
    if not path.is_file():
        raise DeckError(f"image not found: {path}")
    try:
        if path.suffix.lower() == ".svg":
            return _uri("image/svg+xml", path.read_bytes())
        with Image.open(path) as opened:
            fmt = opened.format or ""
            if fmt not in MIME:
                raise DeckError(
                    f"unsupported image format {fmt or 'unknown'}: {path} (use PNG, JPEG, WebP, SVG or .mmd)"
                )
            image = ImageOps.exif_transpose(opened)
            image.thumbnail((max_px, max_px))
            buf = io.BytesIO()
            image.save(buf, format=fmt, **SAVE_OPTIONS[fmt])
    except UnidentifiedImageError:
        raise DeckError(f"not a readable image: {path}") from None
    except OSError as e:
        raise DeckError(f"can't read image {path}: {e.strerror or e}") from None
    return _uri(MIME[fmt], buf.getvalue())


def _uri(mime: str, data: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"
