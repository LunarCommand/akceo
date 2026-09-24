"""Mermaid diagrams: the build-time syntax check, the theme config, and the script the page embeds.

The check runs Mermaid's own parse() in V8 through mini-racer, so a broken diagram stops the build
with Mermaid's message and no browser or Node is needed. The page draws each diagram when it opens,
with the same vendored mermaid.min.js."""

import json
import re
from collections.abc import Callable
from importlib import resources
from pathlib import Path
from types import TracebackType
from typing import Any

from py_mini_racer import JSPromise, JSTimeoutException, MiniRacer

from akceo.errors import DeckError

ASSETS = resources.files("akceo") / "assets"
VENDOR = ASSETS / "vendor" / "mermaid"
PARSE_TIMEOUT = 10  # seconds; a diagram parses in milliseconds

# Mermaid removes these before it parses, so the line numbers in its errors count without them.
# The patterns are Mermaid's own (src/diagram-api/regexes.ts and src/preprocess.ts).
FRONT_MATTER = re.compile(r"([^\S\n\r]*)-{3}\s*[\n\r](.*?)[\n\r]\1-{3}\s*[\n\r]+", re.DOTALL)
DIRECTIVE = re.compile(r"%%\{\s*(?:(\w+)\s*:|(\w+))\s*(?:(\w+)|((?:(?!\}%%).|\r?\n)*))?\s*(?:\}%%)?", re.I)
COMMENT = re.compile(r"^\s*%%(?!\{)[^\n]+\n?", re.MULTILINE)

LINE_REF = re.compile(r"\bline (\d+)")
JISON_ERROR = re.compile(r"(Parse|Lexical) error on line (\d+)[:.]?\s*(.*)", re.DOTALL)
UNKNOWN_TYPE = "No diagram type detected"


class Checker:
    """Checks diagrams with one V8 context, started on the first check. Use it as a context manager:
    mini-racer's context has to be closed, or the Python process hangs when it exits."""

    def __init__(self) -> None:
        self._ctx: MiniRacer | None = None

    def __enter__(self) -> "Checker":
        return self

    def __exit__(
        self, kind: type[BaseException] | None, error: BaseException | None, trace: TracebackType | None
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._ctx is not None:
            self._ctx.close()
            self._ctx = None

    def check(self, path: Path, source: str) -> None:
        """Raise a DeckError naming the line in path when Mermaid can't parse source."""
        if self._ctx is None:
            self._ctx = MiniRacer()
            self._ctx.eval((ASSETS / "mermaid-shims.js").read_text(encoding="utf-8"))
            self._ctx.eval((VENDOR / "mermaid.min.js").read_text(encoding="utf-8"))
        promise = self._ctx.eval(f"akceoCheck({json.dumps(source)})")
        assert isinstance(promise, JSPromise)
        try:
            message = promise.get(timeout=PARSE_TIMEOUT)
        except JSTimeoutException:
            raise DeckError(f"{path}: Mermaid took over {PARSE_TIMEOUT}s to check the diagram") from None
        if isinstance(message, str):
            raise DeckError(explain(path, source, message))


def explain(path: Path, source: str, message: str) -> str:
    """Turn a Mermaid parse error into one line that points at the line in the diagram file."""
    origin = _origin_lines(source)
    if message.startswith(UNKNOWN_TYPE):
        first = next((n for n, text in enumerate(source.splitlines(), 1) if text.strip()), 1)
        return f"{path}:{first}: Mermaid doesn't recognise the diagram type; start with one such as flowchart"
    jison = JISON_ERROR.match(message)
    if jison:
        kind, line, rest = jison.groups()
        # Mermaid shows the failing text and a caret under it; on one line the caret points nowhere.
        detail = [part for part in rest.splitlines() if part and not part.startswith(("...", "-"))]
        return f"{path}:{origin(int(line))}: {kind} error: {' '.join(detail) or 'the diagram is incomplete'}"
    message = " ".join(message.removeprefix("Parsing failed:").split())
    lines = LINE_REF.findall(message)
    message = LINE_REF.sub(lambda m: f"line {origin(int(m.group(1)))}", message)
    return f"{path}:{origin(int(lines[0]))}: {message}" if lines else f"{path}: {message}"


def _origin_lines(source: str) -> Callable[[int], int]:
    """A function from a line number in the text Mermaid parses to the same line in source. Mermaid
    drops front matter, %%{init}%% directives, %% comments and leading blank lines before parsing, so
    repeat those steps here while keeping each character's original line."""
    text = source.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[int] = []
    line = 1
    for c in text:
        lines.append(line)
        line += c == "\n"

    def remove(pattern: re.Pattern[str], first_only: bool = False) -> None:
        nonlocal text, lines
        matches = [pattern.match(text)] if first_only else list(pattern.finditer(text))
        keep = [True] * len(text)
        for m in matches:
            if m:
                keep[m.start() : m.end()] = [False] * (m.end() - m.start())
        text = "".join(c for c, k in zip(text, keep, strict=True) if k)
        lines = [n for n, k in zip(lines, keep, strict=True) if k]

    remove(FRONT_MATTER, first_only=True)
    remove(DIRECTIVE)
    remove(COMMENT)
    start = len(text) - len(text.lstrip())
    text, lines = text[start:], lines[start:]
    starts = [0, *(i + 1 for i, c in enumerate(text) if c == "\n" and i + 1 < len(text))]
    last = max(lines, default=1)

    def origin(line: int) -> int:
        # An error at the end of the text can name a line past it; the last line is the useful one.
        if line < 1 or line > len(starts) or not lines:
            return last
        return lines[starts[line - 1]]

    return origin


def config(tokens: dict[str, str]) -> dict[str, Any]:
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


def page_script() -> str:
    """mermaid.min.js ready to sit in the page's <script>, under a comment that carries Mermaid's
    license and the notices of every package it bundles, as their licenses ask of each copy.

    Any <script or </script text is escaped as \\x3C, which JavaScript strings and regular
    expressions read as <, so it can't end or restart the page's script element."""
    manifest = json.loads((VENDOR / "manifest.json").read_text(encoding="utf-8"))
    notices = "\n\n".join(
        (VENDOR / name).read_text(encoding="utf-8").strip() for name in ("LICENSE", "THIRD_PARTY_NOTICES")
    )
    comment = f"/*! Mermaid {manifest['version']}\n\n{notices.replace('*/', '* /')}\n*/\n"
    script = (VENDOR / "mermaid.min.js").read_text(encoding="utf-8")
    return re.sub(r"<(/?script)", r"\\x3C\1", comment + script, flags=re.IGNORECASE)
