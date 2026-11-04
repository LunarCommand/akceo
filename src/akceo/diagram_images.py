"""Inline the image files a Mermaid diagram names in its shape data, so the page can show them
without loading anything. The syntax is in docs/syntax.md#images-in-diagrams."""

import math
import re
from dataclasses import dataclass
from pathlib import Path

from akceo import images, parse, shape_data
from akceo.errors import DeckError
from akceo.mermaid import COMMENT

NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?")
SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:", re.IGNORECASE)
OPTIONS = ("crop", "max")
# A node with w but no h, or h but no w, is shrunk along that side only.
UNBOUNDED = 1 << 30


@dataclass(frozen=True)
class Inlined:
    """An image file inlined into a diagram: its path as written, the diagram line it's on, and the
    length of its data: URI."""

    name: str
    line: int
    size: int


def inline(path: Path, source: str) -> tuple[str, list[Inlined]]:
    """source with each img: file path in its shape data replaced by the file's data: URI, and the
    images inlined. A path resolves against the diagram's folder. A data: URI or a URL is left for
    the check to pass or refuse, and %% comments are skipped.

    The URI has no line breaks, and a value that spanned lines is followed by as many, so every line
    stays where it was and Mermaid's errors still point at the right line of the diagram file."""
    text = COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), source)
    edits: list[tuple[int, int, str]] = []
    inlined: list[Inlined] = []
    for entries in shape_data.blocks(text):
        sizes = {
            e.key: float(e.value.strip())
            for e in entries
            if e.key in "wh" and NUMBER.fullmatch(e.value.strip())
        }
        for entry in entries:
            value = entry.value.strip()
            if entry.key != "img" or not value or SCHEME.match(value) or value.startswith(("#", "//")):
                continue
            line = source.count("\n", 0, entry.start) + 1
            if entry.plain and "#" in value:
                example = f'img: "{value.partition("#")[0]}#crop=120,80,920,580"'
                raise DeckError(f"{path}:{line}: quote an img: path that has options, such as {example}")
            name, uri = _encode(path, value, sizes, line)
            edits.append(
                (entry.start, entry.end, f'"{uri}"' + "\n" * source.count("\n", entry.start, entry.end))
            )
            inlined.append(Inlined(name, line, len(uri)))
    for start, end, new in reversed(edits):
        source = source[:start] + new + source[end:]
    return source, inlined


def _encode(path: Path, value: str, sizes: dict[str, float], line: int) -> tuple[str, str]:
    """The file name in value and its data: URI. max= sets the longest side; otherwise the image
    fits twice the node's w and h, or keeps its size when the node sets neither, since Mermaid then
    draws it at its own size."""
    name, mark, options = value.partition("#")
    try:
        crop, max_px = _options(options) if mark else (None, None)
        if max_px:
            box = (max_px, max_px)
        elif sizes:
            box = (_twice(sizes.get("w")), _twice(sizes.get("h")))
        else:
            box = None
        return name, images.data_uri(path.parent / name, box, crop)
    except DeckError as e:
        raise DeckError(f"{path}:{line}: {e}") from None


def _options(text: str) -> tuple[tuple[int, int, int, int] | None, int | None]:
    crop: tuple[int, int, int, int] | None = None
    max_px: int | None = None
    seen: set[str] = set()
    for option in text.split("&"):
        key, equals, value = option.partition("=")
        if key not in OPTIONS or not equals:
            raise DeckError(
                f"an img: path takes crop= and max= after its #, joined with &, not '{option}' "
                "(a file name can't contain #)"
            )
        if key in seen:
            raise DeckError(f"an img: path takes {key}= only once")
        seen.add(key)
        if key == "crop":
            crop = parse.crop_box(value, "crop")
        else:
            max_px = parse.pixel_count(value, "max")
    return crop, max_px


def _twice(size: float | None) -> int:
    return math.ceil(2 * size) if size else UNBOUNDED
