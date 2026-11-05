"""The result of checking a deck, as data: what `akceo check --json` prints. Agents read these
fields, so a field may be added but never renamed or removed. docs/agent/tldr.md describes them."""

from pathlib import Path
from typing import Any

from akceo import render
from akceo.errors import DeckError


def check(deck: Path, theme: str | None = None) -> dict[str, Any]:
    try:
        _, count = render.build(deck, theme)
    except DeckError as e:
        return {"ok": False, "deck": str(deck), "slides": None, "errors": [error(e)]}
    return {"ok": True, "deck": str(deck), "slides": count, "errors": []}


def error(e: DeckError) -> dict[str, Any]:
    """file, line and slide are the outermost place, such as the slide in the deck; in is the
    innermost, such as the line in that slide's diagram."""
    outer = e.places[0] if e.places else None
    inner = e.places[-1] if len(e.places) > 1 else None
    return {
        "code": e.code,
        "message": e.message,
        "file": str(outer.path) if outer else None,
        "line": outer.line if outer else None,
        "slide": outer.slide if outer else None,
        "in": {"file": str(inner.path), "line": inner.line} if inner else None,
        "text": str(e),
    }
