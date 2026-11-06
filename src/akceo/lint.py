"""Warnings: what builds but probably isn't what the author meant, such as Markdown akceo doesn't
read, which shows on the slide as plain text. A warning never stops the build. The parser finds
the stray lines, so that an error a stray line causes can say so too; this adds the warnings about
whole slides."""

from dataclasses import dataclass

from akceo.errors import Place, WarningCode
from akceo.parse import BREAK, Deck, Slide, slide_texts

DENSE_WORDS = 100

Found = tuple[WarningCode, int, str]  # (code, line, message)


@dataclass(frozen=True)
class DeckWarning:
    code: WarningCode
    message: str
    place: Place

    def __str__(self) -> str:
        return f"{self.place}warning: {self.message}"


def find(deck: Deck) -> list[DeckWarning]:
    """The deck's warnings, slide by slide and line by line. Each code is given once a slide, at its
    first line."""
    warnings: list[DeckWarning] = []
    for slide in deck.slides:
        first: dict[WarningCode, Found] = {}
        for found in _slide_warnings(slide):
            first.setdefault(found[0], found)
        for code, line, message in first.values():
            warnings.append(DeckWarning(code, message, Place(deck.path, line, slide.number)))
    return warnings


def _slide_warnings(slide: Slide) -> list[Found]:
    """The slide's warnings in line order: those about the whole slide are on its first line."""
    out: list[Found] = []
    words = sum(len(text.replace(BREAK, " ").split()) for _, text in slide_texts(slide))
    if words > DENSE_WORDS:
        message = f"{words} words, which may not fit; look at the built page, or split the slide"
        out.append(("slide-dense", slide.line, message))
    if slide.layout in ("split", "image") and "image" not in slide.meta:
        message = "no image: yet, so the slide shows a dashed box where it goes"
        out.append(("image-placeholder", slide.line, message))
    out.extend((code, number, reason) for number, (code, reason) in slide.stray.items())
    return out
