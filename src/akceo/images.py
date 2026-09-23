"""Turn image files into data URIs so the built deck has no external assets."""

import base64
import io
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from akceo.errors import DeckError

MIME = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
SAVE_OPTIONS: dict[str, dict[str, Any]] = {"PNG": {}, "JPEG": {"quality": 90}, "WEBP": {"quality": 90}}
MERMAID_INSTALL = "npm install -g @mermaid-js/mermaid-cli"
MERMAID_TIMEOUT = 60  # seconds; mmdc starts a headless browser for each diagram
SVG_ROOT = re.compile(rb"<svg\b[^>]*>")


def data_uri(path: Path, max_px: int, mermaid: dict[str, Any] | None = None) -> str:
    """Embed an image, shrinking raster formats so the longest side is at most max_px. SVG is embedded
    as-is, and a Mermaid .mmd file is rendered to SVG first, with the mermaid config if one is given."""
    if not path.is_file():
        raise DeckError(f"image not found: {path}")
    try:
        if path.suffix.lower() == ".svg":
            return _uri("image/svg+xml", path.read_bytes())
        if path.suffix.lower() == ".mmd":
            return _uri("image/svg+xml", _mermaid_svg(path, mermaid))
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


def mermaid_config(tokens: dict[str, str]) -> dict[str, Any]:
    """A Mermaid config that draws diagrams in a theme's colors, for diagrams that sit straight on the
    slide. Mermaid's base theme derives its other colors from these."""
    variables: dict[str, Any] = {
        "background": tokens["bg"],
        "primaryColor": tokens["line"],
        "secondaryColor": tokens["line"],
        "tertiaryColor": tokens["bg"],
        "primaryTextColor": tokens["text"],
        "textColor": tokens["text"],
        "primaryBorderColor": tokens["accent"],
        "lineColor": tokens["muted"],
        "edgeLabelBackground": tokens["bg"],
        "fontFamily": tokens["font"],
    }
    dark = _is_dark(tokens["bg"])
    if dark is not None:
        variables["darkMode"] = dark
    return {"theme": "base", "themeVariables": variables}


def _is_dark(color: str) -> bool | None:
    """Whether a #rgb or #rrggbb color is dark, or None for any other color syntax."""
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", color.strip())
    if not m:
        return None
    digits = m.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    r, g, b = (int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.5


def _mermaid_svg(path: Path, config: dict[str, Any] | None) -> bytes:
    """Render a Mermaid diagram to SVG with the Mermaid CLI (mmdc), an optional outside tool."""
    mmdc = shutil.which("mmdc")
    if mmdc is None:
        raise DeckError(f"rendering {path} needs the Mermaid CLI (mmdc): {MERMAID_INSTALL}")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "diagram.svg"
        command = [mmdc, "-i", str(path), "-o", str(out), "-b", "transparent", "-q"]
        if config is not None:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps(config), encoding="utf-8")
            command += ["-c", str(config_file)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=MERMAID_TIMEOUT)
        except subprocess.TimeoutExpired:
            raise DeckError(f"Mermaid took over {MERMAID_TIMEOUT}s to render {path}") from None
        if result.returncode != 0 or not out.is_file():
            raise DeckError(f"Mermaid couldn't render {path}: {_mermaid_reason(result.stderr)}")
        return _fixed_size(out.read_bytes())


def _mermaid_reason(stderr: str) -> str:
    """mmdc prints a stack trace after the message; keep the message."""
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    message = [line for line in lines if not line.startswith("at ")]
    return " ".join(message[:4]) or "mmdc failed with no message"


def _fixed_size(svg: bytes) -> bytes:
    """Mermaid sizes its SVG as width="100%". Inside an <img> that leaves no natural size, so give the
    root element a pixel width and height from its viewBox."""
    root = SVG_ROOT.search(svg)
    view_box = root and re.search(rb'viewBox="[\d.-]+ [\d.-]+ ([\d.]+) ([\d.]+)"', root.group())
    if not root or not view_box:
        return svg
    width, height = (round(float(v)) for v in view_box.groups())
    tag = re.sub(rb'\s(width|height)="[^"]*"', b"", root.group())
    tag = tag.replace(b"<svg", f'<svg width="{width}" height="{height}"'.encode(), 1)
    return svg[: root.start()] + tag + svg[root.end() :]


def _uri(mime: str, data: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"
