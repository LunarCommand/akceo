from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

# Agents branch on these, so a code is never renamed or reused. docs/syntax.md lists them.
Code = Literal[
    "file-not-found",
    "file-unreadable",
    "file-not-utf8",
    "file-unwritable",
    "deck-control-character",
    "deck-no-slides",
    "config-not-key-value",
    "key-unknown",
    "layout-unknown",
    "key-wrong-layout",
    "value-not-yes-or-no",
    "value-not-pixels",
    "crop-invalid",
    "crop-empty",
    "crop-past-edge",
    "image-option-unsupported",
    "url-invalid",
    "style-url",
    "block-not-in-layout",
    "block-repeated",
    "block-missing",
    "link-split",
    "link-past-last-slide",
    "link-target-invalid",
    "image-format-unsupported",
    "image-damaged",
    "image-too-large",
    "diagram-syntax",
    "diagram-too-long",
    "diagram-loads-outside",
    "diagram-timeout",
    "img-unlocated",
    "img-no-path",
    "img-unquoted",
    "img-option-invalid",
    "theme-unknown",
    "theme-closes-style",
    "theme-missing-tokens",
    "init-not-folder",
    "init-link-outside",
    "init-broken-link",
]
CODES: tuple[Code, ...] = get_args(Code)

# The same, for warnings: what builds but probably isn't what the author meant.
WarningCode = Literal[
    "slide-dense",
    "image-placeholder",
    "markdown-code-fence",
    "markdown-nested-list",
    "markdown-bullet",
    "markdown-heading",
    "key-in-text",
]
WARNING_CODES: tuple[WarningCode, ...] = get_args(WarningCode)


@dataclass(frozen=True)
class Place:
    """Where a problem is: a file, and maybe a line in it and the slide that line is part of."""

    path: Path
    line: int | None = None
    slide: int | None = None

    def __str__(self) -> str:
        line = "" if self.line is None else f":{self.line}"
        slide = "" if self.slide is None else f" slide {self.slide}:"
        return f"{self.path}{line}:{slide} "


class DeckError(Exception):
    """A problem with the deck or its inputs, reported to the user without a traceback. places run
    from the outside in, such as a slide in the deck and then a line in that slide's diagram."""

    def __init__(
        self,
        code: Code,
        message: str,
        path: Path | None = None,
        line: int | None = None,
        slide: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code: Code = code
        self.message = message
        self.places: tuple[Place, ...] = () if path is None else (Place(path, line, slide),)

    def within(self, path: Path, line: int | None = None, slide: int | None = None) -> "DeckError":
        """This error, found inside a place, such as a slide."""
        outer = DeckError(self.code, self.message, path, line, slide)
        outer.places += self.places
        return outer

    def __str__(self) -> str:
        return "".join(map(str, self.places)) + self.message
