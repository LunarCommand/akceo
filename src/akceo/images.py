"""Turn image files into data URIs so the built deck has no external assets."""

import base64
import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from akceo import files
from akceo.errors import DeckError

MIME = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
SAVE_OPTIONS: dict[str, dict[str, Any]] = {"PNG": {}, "JPEG": {"quality": 90}, "WEBP": {"quality": 90}}


def data_uri(path: Path, max_px: int, crop: tuple[int, int, int, int] | None = None) -> str:
    """Embed an image. Raster formats are turned upright, cropped to crop (left, top, right, bottom)
    if given, then shrunk so the longest side is at most max_px. SVG is embedded as-is. Mermaid .mmd
    diagrams don't come here; the page draws them (see akceo.mermaid)."""
    if not files.is_file(path):
        raise DeckError(f"image not found: {path}")
    try:
        if path.suffix.lower() == ".svg":
            if crop:
                raise DeckError(f"can't crop an SVG image: {path}")
            return _uri("image/svg+xml", path.read_bytes())
        with Image.open(path) as opened:
            fmt = opened.format or ""
            if fmt not in MIME:
                raise DeckError(
                    f"unsupported image format {fmt or 'unknown'}: {path} (use PNG, JPEG, WebP, SVG or .mmd)"
                )
            image = ImageOps.exif_transpose(opened)
            if crop:
                image = _crop(image, crop, path, opened.size)
            image.thumbnail((max_px, max_px))
            buf = io.BytesIO()
            image.save(buf, format=fmt, **SAVE_OPTIONS[fmt])
    except UnidentifiedImageError:
        raise DeckError(f"not a readable image: {path}") from None
    except OSError as e:
        raise DeckError(f"can't read image {path}: {e.strerror or e}") from None
    # Pillow reports some damaged or unsupported images with these rather than OSError: EXIF that
    # isn't TIFF (SyntaxError), a mode thumbnail() can't reduce (ValueError), a huge declared size.
    except (ValueError, SyntaxError, Image.DecompressionBombError) as e:
        raise DeckError(f"can't process image {path}: {e}") from None
    return _uri(MIME[fmt], buf.getvalue())


def _crop(
    image: Image.Image, box: tuple[int, int, int, int], path: Path, stored: tuple[int, int]
) -> Image.Image:
    """Crop the upright image. stored is the size before EXIF turned it upright, which is what most
    tools report, so the edge error gives both when they differ."""
    width, height = image.size
    if box[2] > width or box[3] > height:
        size = f"{width} by {height} pixels"
        if (width, height) != stored:
            size += f" once turned upright (stored as {stored[0]} by {stored[1]})"
        raise DeckError(f"the crop {', '.join(map(str, box))} goes past the edge of {path}, which is {size}")
    return image.crop(box)


def _uri(mime: str, data: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"
