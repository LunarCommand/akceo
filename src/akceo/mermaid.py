"""Mermaid diagrams: the build-time syntax check, the theme config, and the script the page embeds.

The check runs Mermaid's own parse() in V8 through mini-racer, so a broken diagram stops the build
with Mermaid's message and no browser or Node is needed. The page draws each diagram when it opens,
with the same vendored mermaid.min.js.

V8 runs in a child process (python -m akceo.mermaid). mini-racer can't interrupt JavaScript that
runs after an await, and parse() is async, so a diagram that sends Mermaid into a loop could hang the
build for good. A child process can be killed when a diagram takes too long, or on Ctrl-C."""

import json
import os
import queue
import re
import subprocess
import sys
import threading
from collections.abc import Callable
from importlib import resources
from pathlib import Path
from types import TracebackType
from typing import IO, Any

from akceo.errors import DeckError

ASSETS = resources.files("akceo") / "assets"
VENDOR = ASSETS / "vendor" / "mermaid"
WORKER = [sys.executable, "-m", "akceo.mermaid"]
START_TIMEOUT = 30  # seconds to load Mermaid into V8; about 0.2s warm, a second or so cold
PARSE_TIMEOUT = 10  # seconds per diagram; a diagram parses in milliseconds

# Mermaid removes these before it parses, so the line numbers in its errors count without them.
# The patterns are Mermaid's own (src/diagram-api/regexes.ts and src/preprocess.ts).
FRONT_MATTER = re.compile(r"([^\S\n\r]*)-{3}\s*[\n\r](.*?)[\n\r]\1-{3}\s*[\n\r]+", re.DOTALL)
DIRECTIVE = re.compile(r"%%\{\s*(?:(\w+)\s*:|(\w+))\s*(?:(\w+)|((?:(?!\}%%).|\r?\n)*))?\s*(?:\}%%)?", re.I)
COMMENT = re.compile(r"^\s*%%(?!\{)[^\n]+\n?", re.MULTILINE)

# Ways a diagram can link to or load something outside the deck. The page's Content-Security-Policy
# blocks every outside load, however it's spelled; this scan is here to stop the build with a clear
# message and a line for the usual spellings. Only #anchors may be linked and data: URIs loaded.
# A value may sit in a JSON string inside an %%{init}%% line, as \"https://…\", so each pattern
# allows a backslash before a quote and leaves backslashes out of the URL it captures.
LINKS = [
    re.compile(r"""(?:^|;)[ \t]*click\s+\S+\s+(?:href\s+)?\\?["']([^"'\\]*)\\?["']""", re.MULTILINE),
    re.compile(r"""(?:^|;)[ \t]*link\s+\S+\s+\\?["']([^"'\\]*)\\?["']""", re.MULTILINE),  # classDiagram
    re.compile(r"""(?:^|;)[ \t]*link\s+[^:\n]+:[^@\n]*@\s*(\S+)""", re.MULTILINE),  # sequenceDiagram
    re.compile(r"""\$link\s*=\s*\\?["']([^"'\\]*)\\?["']"""),  # C4
    re.compile(r"""<[a-z][^>]*?\b(?:xlink:)?href\s*=\s*\\?["']?\s*([^"'\\\s>]*)""", re.IGNORECASE),
]
# sequenceDiagram: links A: {"Docs": "https://…"}. Each value in the braces is a link.
SEQUENCE_LINKS = re.compile(r"""(?:^|;)[ \t]*links\s+[^:\n]+:\s*(\{[^\n]*\})""", re.MULTILINE)
SEQUENCE_LINK_VALUE = re.compile(r""":\s*\\?["']([^"'\\]*)\\?["']""")
LOADS = [
    re.compile(r"""<[a-z][^>]*?\b(?:src|poster|background|data)\s*=\s*\\?["']?\s*([^"'\\\s>]*)""", re.I),
    re.compile(r"""url\(\s*\\?["']?\s*([^"'\\)\s]*)""", re.IGNORECASE),
    re.compile(r"""@import\b\s*(?:url\()?\s*\\?["']?\s*([^"'\\)\s;]*)""", re.IGNORECASE),
]
# srcset holds a list of candidates, "url descriptor, url descriptor", and a data: URL has commas
# of its own, so its whole value is captured and split the way the HTML spec does.
SRCSET = [
    re.compile(r"""<[a-z][^>]*?\bsrcset\s*=\s*\\?(["'])(.*?)\\?\1""", re.IGNORECASE | re.DOTALL),
    re.compile(r"""<[a-z][^>]*?\bsrcset\s*=\s*()([^"'\\\s>]+)""", re.IGNORECASE),
]
SHAPE_DATA = re.compile(r"@\{.*?\}", re.DOTALL)
IMAGE_KEY = re.compile(r"""\\?["']?\bimg\\?["']?\s*:\s*\\?["']?\s*([^"'\\,}\s]*)""")

LINE_REF = re.compile(r"\bline (\d+)")
JISON_ERROR = re.compile(r"(Parse|Lexical) error on line (\d+)[:.]?\s*(.*)", re.DOTALL)
UNKNOWN_TYPE = "No diagram type detected"
UNKNOWN_SHAPE = re.compile(r"No such shape: (.+?)\.?$")
YAML_POSITION = re.compile(r"\s*\(\d+:\d+\)$")


class Checker:
    """Checks diagrams in one child process, started on the first check. Use it as a context
    manager, so the child is stopped when the build ends or fails."""

    def __init__(self) -> None:
        self._worker: subprocess.Popen[str] | None = None
        self._answers: queue.Queue[str | None] = queue.Queue()
        self._max_text_size = 0

    def __enter__(self) -> "Checker":
        return self

    def __exit__(
        self, kind: type[BaseException] | None, error: BaseException | None, trace: TracebackType | None
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._worker is not None:
            self._worker.kill()
            self._worker.wait()
            self._worker = None

    def check(self, path: Path, source: str) -> None:
        """Raise a DeckError naming the line in path when Mermaid can't parse source, when it's too
        long for Mermaid to draw, or when it links to or loads anything outside the deck."""
        self._start(path)
        # Mermaid counts JavaScript string length, in UTF-16 units, of the text the page hands it,
        # where the HTML parser has already turned \r\n into \n.
        size = len(source.replace("\r\n", "\n").encode("utf-16-le")) // 2
        if size > self._max_text_size:
            raise DeckError(
                f"{path}: the diagram is {size:,} characters long, over Mermaid's limit of "
                f"{self._max_text_size:,}; split it into smaller diagrams"
            )
        error = self._parse(path, source)
        if error is not None:
            raise DeckError(explain(path, source, error["message"], self._locate(path, source, error)))
        outside = outside_reference(source)
        if outside:
            line, url = outside
            raise DeckError(
                f"{path}:{line}: a diagram can't load or link to anything outside the deck ({url}); "
                "use a data: URI for an image and a #anchor, such as #3 for slide 3, for a link"
            )

    def _start(self, path: Path) -> None:
        if self._worker is not None:
            return
        self._answers = queue.Queue()
        self._worker = subprocess.Popen(
            WORKER, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8"
        )
        assert self._worker.stdout is not None
        threading.Thread(target=_read_lines, args=(self._worker.stdout, self._answers), daemon=True).start()
        ready = self._answer(path, START_TIMEOUT, "load Mermaid")
        self._max_text_size = int(ready["max_text_size"])

    def _parse(self, path: Path, source: str) -> dict[str, Any] | None:
        """Mermaid's error for source as a dict (name, message, yamlLine), or None if it parses."""
        self._start(path)
        assert self._worker is not None and self._worker.stdin is not None
        try:
            self._worker.stdin.write(json.dumps({"source": source}) + "\n")
            self._worker.stdin.flush()
        except BrokenPipeError:
            pass  # the worker has stopped; _answer reports it
        return self._answer(path, PARSE_TIMEOUT, "check the diagram")["error"]

    def _answer(self, path: Path, timeout: float, task: str) -> dict[str, Any]:
        try:
            line = self._answers.get(timeout=timeout)
        except queue.Empty:
            self.close()
            raise DeckError(f"{path}: Mermaid took over {timeout}s to {task}") from None
        if line is None:
            self.close()
            raise RuntimeError("the Mermaid checker process stopped unexpectedly")
        return json.loads(line)

    def _locate(self, path: Path, source: str, error: dict[str, Any]) -> int | None:
        """The file line of an error Mermaid gives no usable line for: YAML in front matter or in
        @{...} shape data, or an unknown shape. Found by parsing each suspect part on its own."""
        shape = UNKNOWN_SHAPE.search(error["message"])
        if shape:
            m = re.search(rf"""\bshape\s*:\s*["']?{re.escape(shape.group(1))}\b""", source)
            return _line_at(source, m.start()) if m else None
        if error["name"] != "YAMLException":
            return None
        front = FRONT_MATTER.match(source)
        if front:
            found = self._parse(path, front.group(0) + "info\n")
            if found is not None and found["name"] == "YAMLException":
                body_lines = front.group(2).count("\n") + 1
                return 2 + min(max(found["yamlLine"] or 0, 0), body_lines - 1)
        for block in SHAPE_DATA.finditer(source):
            found = self._parse(path, "flowchart LR\n  x" + block.group(0) + "\n")
            if found is not None and found["name"] == "YAMLException":
                # Mermaid wraps the block's inside in { and }, so its line 1 is the block's first.
                block_lines = block.group(0).count("\n") + 1
                offset = min(max((found["yamlLine"] or 0) - 1, 0), block_lines - 1)
                return _line_at(source, block.start()) + offset
        return None


def _read_lines(stream: IO[str], answers: "queue.Queue[str | None]") -> None:
    """Hand each line the worker writes to the waiting check; None when the worker stops."""
    for line in stream:
        answers.put(line)
    answers.put(None)


def _serve() -> None:
    """The worker behind Checker: load Mermaid into V8, then answer one JSON request per line."""
    from py_mini_racer import JSPromise, MiniRacer

    try:
        ctx = MiniRacer()
        ctx.eval((ASSETS / "mermaid-shims.js").read_text(encoding="utf-8"))
        ctx.eval((VENDOR / "mermaid.min.js").read_text(encoding="utf-8"))
        _send({"max_text_size": ctx.eval("akceoMaxTextSize()")})
        for line in sys.stdin:
            promise = ctx.eval(f"akceoCheck({json.dumps(json.loads(line)['source'])})")
            assert isinstance(promise, JSPromise)
            result = promise.get()
            _send({"error": json.loads(result) if isinstance(result, str) else None})
    except KeyboardInterrupt:
        pass  # Ctrl-C reaches the worker too; the build reports it
    # Skip interpreter shutdown: an open mini-racer context can hang it, and there's nothing to save.
    os._exit(0)


def _send(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def _line_at(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def outside_reference(source: str) -> tuple[int, str] | None:
    """The line and URL of the first place the diagram links to, or loads, something outside the
    page. Links may only be #anchors and loads only data: URIs: a relative path would point next to
    deck.html and break once the deck is copied. A URL that is only text in a label is fine.

    The whole source is scanned, so a tag split over lines is still seen. %% comments are blanked
    first, keeping their line breaks, but directives and front matter are scanned: themeCSS there
    can load images and fonts."""
    text = COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), source)
    links = [(m.start(1), m.group(1)) for pattern in LINKS for m in pattern.finditer(text)]
    links += [
        (block.start(1) + m.start(1), m.group(1))
        for block in SEQUENCE_LINKS.finditer(text)
        for m in SEQUENCE_LINK_VALUE.finditer(block.group(1))
    ]
    found = [(index, url) for index, url in links if not url.startswith("#")]
    loads = [(m.start(1), m.group(1)) for pattern in LOADS for m in pattern.finditer(text)]
    loads += [
        (m.start(2) + index, url)
        for pattern in SRCSET
        for m in pattern.finditer(text)
        for index, url in _srcset_urls(m.group(2))
    ]
    loads += [
        (block.start() + m.start(1), m.group(1))
        for block in SHAPE_DATA.finditer(text)
        for m in IMAGE_KEY.finditer(block.group(0))
    ]
    found += [
        (index, url)
        for index, url in loads
        # url(#marker) points inside the SVG itself.
        if not url.lower().startswith("data:") and not url.startswith("#")
    ]
    found = [(index, url) for index, url in found if url]
    if not found:
        return None
    index, url = min(found)
    return _line_at(source, index), url


def _srcset_urls(value: str) -> list[tuple[int, str]]:
    """Each candidate URL in a srcset value, with its offset. As the HTML spec reads it, a URL runs
    to the next whitespace, less any trailing commas, and its descriptors run to the next comma."""
    urls: list[tuple[int, str]] = []
    i = 0
    while i < len(value):
        while i < len(value) and (value[i].isspace() or value[i] == ","):
            i += 1
        start = i
        while i < len(value) and not value[i].isspace():
            i += 1
        url = value[start:i].rstrip(",")
        if url:
            urls.append((start, url))
        if not value[start:i].endswith(","):
            while i < len(value) and value[i] != ",":
                i += 1
    return urls


def explain(path: Path, source: str, message: str, line: int | None = None) -> str:
    """Turn a Mermaid parse error into one line that points at the line in the diagram file. A line
    found some other way is used as is, with any YAML (line:column), which counts within a snippet,
    dropped from the message."""
    if line is not None:
        first = YAML_POSITION.sub("", message.strip().splitlines()[0])
        return f"{path}:{line}: {first}"
    origin = _origin_lines(source)
    if message.startswith(UNKNOWN_TYPE):
        # Mermaid reads the type from the first line it parses.
        hint = "start with one such as flowchart"
        return f"{path}:{origin(1)}: Mermaid doesn't recognise the diagram type; {hint}"
    jison = JISON_ERROR.match(message)
    if jison:
        kind, number, rest = jison.groups()
        # Mermaid shows the failing text and a caret under it; on one line the caret points nowhere.
        detail = [part for part in rest.splitlines() if part and not part.startswith(("...", "-"))]
        detail_text = " ".join(detail) or "the diagram is incomplete"
        return f"{path}:{origin(int(number))}: {kind} error: {detail_text}"
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


if __name__ == "__main__":
    _serve()
