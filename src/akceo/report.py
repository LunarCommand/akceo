"""The result of checking a deck, as data: what `akceo check --json` prints. Agents read these
fields, so a field may be added but never renamed or removed. docs/agent/tldr.md describes them."""

from pathlib import Path
from typing import Any

from akceo import lint, render
from akceo.errors import DeckError, Place


def check(deck: Path, theme: str | None = None) -> dict[str, Any]:
    """A deck with an error gets no warnings: the error is what to fix first."""
    try:
        _, parsed = render.build(deck, theme)
    except DeckError as e:
        return {"ok": False, "deck": str(deck), "slides": None, "errors": [error(e)], "warnings": []}
    warnings = [_entry(w.code, w.message, (w.place,), str(w)) for w in lint.find(parsed)]
    return {"ok": True, "deck": str(deck), "slides": len(parsed.slides), "errors": [], "warnings": warnings}


def error(e: DeckError) -> dict[str, Any]:
    return _entry(e.code, e.message, e.places, str(e))


def _entry(code: str, message: str, places: tuple[Place, ...], text: str) -> dict[str, Any]:
    """file, line and slide are the outermost place, such as the slide in the deck; in is the
    innermost, such as the line in that slide's diagram."""
    outer = places[0] if places else None
    inner = places[-1] if len(places) > 1 else None
    return {
        "code": code,
        "message": message,
        "file": str(outer.path) if outer else None,
        "line": outer.line if outer else None,
        "slide": outer.slide if outer else None,
        "in": {"file": str(inner.path), "line": inner.line} if inner else None,
        "text": text,
    }
