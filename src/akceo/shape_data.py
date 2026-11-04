"""Read the @{…} shape data in a Mermaid diagram the way Mermaid reads it, keeping where each value
sits in the source, so a value can be checked and replaced in place."""

import re
from collections.abc import Iterator
from dataclasses import dataclass

# Mermaid's flowchart lexer ends shape data at the first } outside a double-quoted string; a single
# quote doesn't protect one. It turns a line break inside such a string into <br/>
# (src/diagrams/flowchart/parser/flow.jison). Its YAML then reads the data as a flow mapping when no
# line break is left, and as a block mapping when one is (addVertex in flowchart/flowDb.ts).
BLOCK = re.compile(r'@\{((?:[^"}]|"[^"]*")*)\}')
DATA = re.compile(r'(?:[^"}]|"[^"]*")*+\}')
# Where the lexer reads @{ as text: a string, accessibility text, and the text of an edge written
# as -- text --> or == text ==>. A link with no text is tried first, as the lexer does, so --> isn't
# taken for the start of edge text.
TOKEN = re.compile(
    r'(?P<string>")|\bacc(?:Title|Descr)\s*:[^\n]*|\baccDescr\s*\{[^}]*\}?'
    r"|[xo<]?(?:--+[-xo>]|==+[=xo>]|-?\.+-[xo>]?)|(?P<edge>[xo<]?(?:--|==|-\.))|(?P<data>@\{)"
)
EDGE_END = {
    "-": re.compile(r'(")|[xo<]?--+[-xo>]'),
    "=": re.compile(r'(")|[xo<]?==+[=xo>]'),
    ".": re.compile(r'(")|[xo<]?-?\.+-[xo>]?'),
}
# A plain key needs a space after its colon; a quoted one doesn't.
KEY = re.compile(
    r"""(?:"((?:[^"\\\n]|\\.)*)"|'((?:[^'\n]|'')*)')[ \t]*:"""
    r"""|([^\s"'#:,][^:,\n]*+)[ \t]*:(?=\s|$)"""
)
# Quoted values as YAML reads them. The lexer's own strings, which BLOCK pairs, ignore escapes.
DOUBLE = re.compile(r'"((?:[^"\\]|\\.)*)"', re.DOTALL)
SINGLE = re.compile(r"'((?:[^']|'')*)'")
LEXER_STRING = re.compile(r'"[^"]*"')
BLOCK_SCALAR = re.compile(r"([|>])([1-9]?)([+-]?)[1-9]?[ \t]*(?:#.*)?$")
COMMENT = re.compile(r"(?:^|[ \t])#.*")
ESCAPE = re.compile(r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|.)", re.DOTALL)
ESCAPES = {
    "0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r",
    "e": "\x1b", " ": " ", '"': '"', "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0", "L": "\u2028",
    "P": "\u2029",
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
    """The entries of each @{…} block in text, in order. text is a flowchart with what Mermaid
    removes before parsing, such as front matter, blanked."""
    for offset, end in _spans(text):
        body = text[offset:end]
        lexed = LEXER_STRING.sub(lambda m: m.group().replace("\n", " "), body)
        block = "\n" in lexed
        masked = _blank_quoted(lexed)
        if not block:
            # Mermaid puts one-line data between braces on lines of their own, so a comment runs to
            # the end of the data.
            masked = COMMENT.sub(lambda m: " " * len(m.group()), masked)
        regions = _block_regions(masked) if block else _flow_regions(masked)
        yield [
            Entry(e.key, e.value, e.start + offset, e.end + offset, e.plain)
            for start, end in regions
            if (e := _entry(body, start, end, block))
        ]


def _spans(text: str) -> Iterator[tuple[int, int]]:
    """Where the inside of each @{…} that the lexer reads as shape data starts and ends. The scan
    stops at anything left open: past it, Mermaid couldn't parse the diagram either."""
    pos = 0
    while token := TOKEN.search(text, pos):
        pos = token.end()
        if token.group("string"):
            pos = text.find('"', pos) + 1
            if not pos:
                return
        elif token.group("edge"):
            pos = _edge_end(text, pos, EDGE_END[token.group("edge")[-1]])
            if pos < 0:
                return
        elif token.group("data"):
            data = DATA.match(text, pos)
            if not data:
                return
            yield pos, data.end() - 1
            pos = data.end()


def _edge_end(text: str, pos: int, end: re.Pattern[str]) -> int:
    """Where edge text from pos ends, past the link that ends it, or -1. A string in it is skipped."""
    while found := end.search(text, pos):
        if found.group(1) is None:
            return found.end()
        pos = text.find('"', found.end()) + 1
        if not pos:
            break
    return -1


def _blank_quoted(body: str) -> str:
    """body with the inside of each quoted value or key blanked, line breaks included."""
    out = list(body)
    i = 0
    while i < len(body):
        quoted = (DOUBLE if body[i] == '"' else SINGLE).match(body, i) if _opens(body, i) else None
        if quoted:
            out[i + 1 : quoted.end() - 1] = " " * (quoted.end() - i - 2)
            i = quoted.end()
        else:
            i += 1
    return "".join(out)


def _opens(body: str, i: int) -> bool:
    """Whether the character at i opens a quoted key or value: a quote where one can start, or after
    a colon that a space or a quoted key's closing quote sets apart. Inside a plain value, as in
    It's or Era:'90s, a quote is just a character."""
    if body[i] not in "\"'":
        return False
    j = i
    while j and body[j - 1] in " \t":
        j -= 1
    before = body[j - 1] if j else ""
    if before == ":":
        return j < i or (j >= 2 and body[j - 2] in "\"'")
    return before in ("", "{", ",", "[", "\n")


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
    if key.group(1) is not None:
        name = ESCAPE.sub(lambda e: _unescape(e.group(1)), key.group(1))
    elif key.group(2) is not None:
        name = key.group(2).replace("''", "'")
    else:
        name = key.group(3).rstrip(" \t")
    value = _value(body, key.end(), end, block)
    return Entry(name, *value) if value else None


def _value(body: str, start: int, end: int, block: bool) -> tuple[str, int, int, bool] | None:
    """A value as YAML reads it, with its span and whether it's plain. None if it's empty. In a block
    mapping, a value can start on a later, more-indented line, after blank and comment lines."""
    while block and start < end and not COMMENT.sub("", body[start : _line_end(body, start, end)]).strip():
        start = _line_end(body, start, end) + 1
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
        return (_fold(m.group(1)).replace("''", "'"), start, m.end(), False) if m else None
    header = BLOCK_SCALAR.match(first) if block else None
    if header:
        return _block_scalar(body, start, line_end, end, header)
    return _plain(body, start, end)


def _fold(text: str) -> str:
    """A single-quoted value's lines as YAML joins them: a line break becomes a space, and each
    blank line in between a line break, with the spaces around each break dropped."""
    first, *rest = text.split("\n")
    if not rest:
        return text
    out = first.rstrip(" \t")
    breaks = 0
    for n, line in enumerate(rest, 1):
        line = line.lstrip(" \t") if n == len(rest) else line.strip(" \t")
        if not line and n < len(rest):
            breaks += 1
            continue
        out += "\n" * breaks if breaks else " "
        out += line
        breaks = 0
    return out


def _line_end(body: str, start: int, end: int) -> int:
    newline = body.find("\n", start, end)
    return end if newline < 0 else newline


def _plain(body: str, start: int, end: int) -> tuple[str, int, int, bool] | None:
    """A plain value: its lines without comments, folded as YAML folds them. A line break becomes a
    space, and each blank line in between a line break."""
    value = ""
    breaks = 0
    value_end = start
    position = start
    for line in body[start:end].split("\n"):
        text = COMMENT.sub("", line)
        if text.strip():
            if value:
                value += "\n" * breaks or " "
            value += text.strip()
            breaks = 0
            value_end = position + len(text.rstrip())
        elif value and line.lstrip().startswith("#"):
            break
        elif value:
            breaks += 1
        position += len(line) + 1
    return (value, start, value_end, True) if value else None


def _block_scalar(
    body: str, start: int, line_end: int, end: int, header: re.Match[str]
) -> tuple[str, int, int, bool] | None:
    """A | or > block scalar: the lines under its header, with their common indent removed, joined
    by line breaks for | or spaces for >, and the final line break kept, dropped (-) or all kept (+).
    Its lines are those indented more than its key; the first that isn't, even a comment, ends it."""
    key_line = body.rfind("\n", 0, start) + 1
    key_indent = _indent(body, key_line, start)
    lines: list[str] = []
    for line in body[line_end + 1 : end].split("\n") if line_end < end else []:
        if line.strip() and len(line) - len(line.lstrip(" \t")) <= key_indent:
            break
        lines.append(line)
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
    """The character an escape stands for. One that isn't a valid character, such as \\U00110000 or
    a lone surrogate, is left as written for Mermaid to judge."""
    if code[0] in "xuU" and len(code) > 1:
        point = int(code[1:], 16)
        return chr(point) if point < 0x110000 and not 0xD800 <= point <= 0xDFFF else "\\" + code
    return ESCAPES.get(code, "\\" + code)
