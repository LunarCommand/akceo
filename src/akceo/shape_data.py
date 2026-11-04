"""Read the @{…} shape data in a Mermaid diagram the way Mermaid reads it, keeping where each value
sits in the source, so a value can be checked and replaced in place."""

import re
from collections.abc import Iterator
from dataclasses import dataclass

# Mermaid's flowchart lexer ends shape data at the first } outside a double-quoted string; a single
# quote doesn't protect one (src/diagrams/flowchart/parser/flow.jison). Its YAML then reads the data
# as a flow mapping when there's no line break outside the quotes, and as a block mapping when there
# is (addVertex in src/diagrams/flowchart/flowDb.ts).
BLOCK = re.compile(r'@\{((?:[^"}]|"[^"]*")*)\}')
QUOTED = re.compile(r""""[^"]*"|'(?:[^'\n]|'')*'""")
# A plain key needs a space after its colon; a quoted one doesn't.
KEY = re.compile(r"""(?:"([^"]*)"|'((?:[^'\n]|'')*)')[ \t]*:|([^\s"'#:,][^:,\n]*?)[ \t]*:(?=\s|$)""")
DOUBLE = re.compile(r'"([^"]*)"')
SINGLE = re.compile(r"'((?:[^'\n]|'')*)'")
BLOCK_SCALAR = re.compile(r"([|>])([1-9]?)([+-]?)[1-9]?[ \t]*(?:#.*)?$")
COMMENT = re.compile(r"(?:^|[ \t])#.*")
ESCAPE = re.compile(r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|.)", re.DOTALL)
ESCAPES = {
    "0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r",
    "e": "\x1b", " ": " ", '"': '"', "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0", "L": " ",
    "P": " ",
}  # fmt: skip


@dataclass(frozen=True)
class Entry:
    """A key in shape data and its value as Mermaid reads it. start and end span the value's text in
    the source, quotes or block scalar included; plain is True when the value isn't quoted."""

    key: str
    value: str
    start: int
    end: int
    plain: bool


def blocks(text: str) -> Iterator[list[Entry]]:
    """The entries of each @{…} block in text, in order."""
    for block in BLOCK.finditer(text):
        body, offset = block.group(1), block.start(1)
        masked = QUOTED.sub(lambda m: m.group()[0] + " " * (len(m.group()) - 2) + m.group()[-1], body)
        regions = _block_regions(masked) if "\n" in masked else _flow_regions(masked)
        yield [
            Entry(e.key, e.value, e.start + offset, e.end + offset, e.plain)
            for start, end in regions
            if (e := _entry(body, start, end, "\n" in masked))
        ]


def _flow_regions(masked: str) -> list[tuple[int, int]]:
    """Each comma-separated entry of a flow mapping. Commas inside quotes are blanked in masked."""
    regions: list[tuple[int, int]] = []
    start = 0
    for comma in [*(i for i, c in enumerate(masked) if c == ","), len(masked)]:
        regions.append((start, comma))
        start = comma + 1
    return regions


def _block_regions(masked: str) -> list[tuple[int, int]]:
    """Each entry of a block mapping: a line at the mapping's indent, with the more-indented lines
    under it, which hold the rest of its value. Line breaks inside quotes are blanked in masked."""
    lines: list[tuple[int, int]] = []
    start = 0
    for line in masked.split("\n"):
        lines.append((start, start + len(line)))
        start += len(line) + 1
    content = [(s, e) for s, e in lines if masked[s:e].strip() and not masked[s:e].lstrip().startswith("#")]
    if not content:
        return []
    indent = min(_indent(masked, s, e) for s, e in content)
    starts = [s for s, e in content if _indent(masked, s, e) == indent]
    return [(s, end) for s, end in zip(starts, [*starts[1:], len(masked)], strict=True)]


def _indent(text: str, start: int, end: int) -> int:
    return len(text[start:end]) - len(text[start:end].lstrip(" \t"))


def _entry(body: str, start: int, end: int, block: bool) -> Entry | None:
    while start < end and body[start].isspace():
        start += 1
    key = KEY.match(body, start, end)
    if not key:
        return None
    name = key.group(1) if key.group(1) is not None else key.group(3)
    if name is None:
        name = key.group(2).replace("''", "'")
    value = _value(body, key.end(), end, block)
    return Entry(name.strip(), *value) if value else None


def _value(body: str, start: int, end: int, block: bool) -> tuple[str, int, int, bool] | None:
    """A value as YAML reads it, with its span and whether it's plain. None if it's empty. In a block
    mapping, a value can start on a later, more-indented line."""
    if block and not COMMENT.sub("", body[start : _line_end(body, start, end)]).strip():
        start = _line_end(body, start, end)
    while start < end and body[start].isspace():
        start += 1
    if start >= end:
        return None
    line_end = _line_end(body, start, end)
    first = body[start:line_end]
    if first.startswith('"'):
        m = DOUBLE.match(body, start, end)
        if not m:
            return None
        # The lexer turns a line break inside a string into <br/> before YAML reads it.
        text = re.sub(r"\n\s*", "<br/>", m.group(1))
        return ESCAPE.sub(lambda e: _unescape(e.group(1)), text), start, m.end(), False
    if first.startswith("'"):
        m = SINGLE.match(body, start, end)
        return (m.group(1).replace("''", "'"), start, m.end(), False) if m else None
    header = BLOCK_SCALAR.match(first) if block else None
    if header:
        return _block_scalar(body, start, line_end, end, header)
    return _plain(body, start, end)


def _line_end(body: str, start: int, end: int) -> int:
    newline = body.find("\n", start, end)
    return end if newline < 0 else newline


def _plain(body: str, start: int, end: int) -> tuple[str, int, int, bool] | None:
    """A plain value: its lines without comments, folded with single spaces."""
    parts: list[str] = []
    value_end = start
    position = start
    for line in body[start:end].split("\n"):
        text = COMMENT.sub("", line)
        if text.strip():
            parts.append(text.strip())
            value_end = position + len(text.rstrip())
        elif parts and line.lstrip().startswith("#"):
            break
        position += len(line) + 1
    return (" ".join(parts), start, value_end, True) if parts else None


def _block_scalar(
    body: str, start: int, line_end: int, end: int, header: re.Match[str]
) -> tuple[str, int, int, bool] | None:
    """A | or > block scalar: the lines under its header, with their common indent removed, joined
    by line breaks for | or spaces for >, and the final line break kept, dropped (-) or all kept (+)."""
    lines = body[line_end + 1 : end].split("\n") if line_end < end else []
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return None
    indent = min(len(line) - len(line.lstrip(" ")) for line in lines if line.strip())
    content = [line[indent:] for line in lines]
    style, _, chomp = header.groups()
    text = "\n".join(content) if style == "|" else " ".join(line for line in content if line)
    text += "" if chomp == "-" else "\n"
    value_end = line_end + 1 + len("\n".join(lines))
    return text, start, value_end, False


def _unescape(code: str) -> str:
    if code[0] in "xuU" and len(code) > 1:
        return chr(int(code[1:], 16))
    return ESCAPES.get(code, "\\" + code)
