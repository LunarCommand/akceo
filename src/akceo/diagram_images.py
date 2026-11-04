"""Inline the image files a Mermaid diagram names in its shape data, so the page can show them
without loading anything. The syntax is in docs/syntax.md#images-in-diagrams."""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from akceo import images, parse, shape_data
from akceo.errors import DeckError
from akceo.mermaid import NodeImage, blank_removed

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


def inline(path: Path, source: str, nodes: Sequence[NodeImage]) -> tuple[str, list[Inlined]]:
    """source with each img: file path in it replaced by the file's data: URI, and the images
    inlined. nodes are the node images Mermaid reads in source, and only those values are replaced,
    so @{…} in a label is left alone. A path resolves against the diagram's folder. A data: URI or a
    URL is left for the check to pass or refuse.

    The URI has no line breaks, and a value that spanned lines is followed by as many, so every line
    stays where it was and Mermaid's errors still point at the right line of the diagram file."""
    by_value: dict[str, list[NodeImage]] = {}
    for node in nodes:
        value = node.img.strip()
        if not SCHEME.match(value) and not value.startswith("//"):
            by_value.setdefault(node.img, []).append(node)
    found = [
        entry
        for entries in shape_data.blocks(blank_removed(source))
        for entry in entries
        if entry.key == "img" and entry.value in by_value
    ]
    for value, using in by_value.items():
        if not any(entry.value == value for entry in found):
            raise DeckError(
                f"{path}: akceo can't tell where node {using[0].node}'s img: {value.strip()} is written, "
                f'to put the file in; write it on one line, such as img: "{value.strip()}"'
            )
    edits: list[tuple[int, int, str]] = []
    inlined: list[Inlined] = []
    for entry in found:
        value = entry.value.strip()
        line = source.count("\n", 0, entry.start) + 1
        if value.startswith("#"):
            example = f'img: "shot.png{value}"'
            raise DeckError(f"{path}:{line}: an img: needs a file path before its #, such as {example}")
        if entry.plain and "#" in value:
            example = f'img: "{value.partition("#")[0]}#crop=120,80,920,580"'
            raise DeckError(f"{path}:{line}: quote an img: path that has options, such as {example}")
        name, uri = _encode(path, value, _box(by_value[entry.value]), line)
        edits.append((entry.start, entry.end, f'"{uri}"' + "\n" * source.count("\n", entry.start, entry.end)))
        inlined.append(Inlined(name, line, len(uri)))
    for start, end, new in reversed(edits):
        source = source[:start] + new + source[end:]
    return source, inlined


def _box(using: Sequence[NodeImage]) -> tuple[int, int] | None:
    """The size to fit an image into: twice the node's w and h, or None to keep its size when the
    node sets neither, since Mermaid then draws it at its own size. An image several nodes use is
    sized for the largest."""
    box = (max(_twice(node.w) for node in using), max(_twice(node.h) for node in using))
    return None if box == (UNBOUNDED, UNBOUNDED) else box


def _twice(size: float | None) -> int:
    return math.ceil(2 * size) if size and 0 < 2 * size < UNBOUNDED else UNBOUNDED


def _encode(path: Path, value: str, box: tuple[int, int] | None, line: int) -> tuple[str, str]:
    """The file name in value and its data: URI. max= after the name sets the longest side instead
    of box."""
    name, mark, options = value.partition("#")
    try:
        crop, max_px = _options(options) if mark else (None, None)
        if max_px:
            if name.lower().endswith(".svg"):
                raise DeckError(
                    f"max= can't shrink an SVG image, so set the node's w and h instead: {path.parent / name}"
                )
            box = (max_px, max_px)
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
