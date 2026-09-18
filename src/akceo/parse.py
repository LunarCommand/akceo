"""Parse akceo's Markdown dialect into a validated deck. The format is described in docs/syntax.md."""

import re
from dataclasses import dataclass
from pathlib import Path

from akceo import files
from akceo.errors import DeckError

LAYOUTS = ("title", "bullets", "split", "steps", "table")
DEFAULT_LAYOUT = "bullets"
CONFIG_KEYS = ("title", "theme", "images")
STYLE_KEYS = ("style-h1", "style-h2", "style-lead", "style-ul", "style-ol", "style-sub")
COMMON_KEYS = ("layout", "kicker", *STYLE_KEYS)
LAYOUT_KEYS: dict[str, tuple[str, ...]] = {
    "title": ("meta",),
    "bullets": (),
    "split": ("image", "image-alt", "image-max", "image-wide"),
    "steps": (),
    "table": ("dim-last-column",),
}
REQUIRED_KEYS: dict[str, tuple[str, ...]] = {"split": ("image",)}
FLAG_KEYS = ("image-wide", "dim-last-column")

# Block kinds each layout renders, mapped to whether that kind may appear more than once.
LAYOUT_BLOCKS: dict[str, dict[str, bool]] = {
    "title": {"h1": False},
    "bullets": {"h2": False, "lead": False, "ul": False, "para": False},
    "split": {"h2": False, "phase": True, "ul": True, "note": False},
    "steps": {"h2": False, "para": False, "ol": False},
    "table": {"h2": False, "table": False},
}
REQUIRED_BLOCKS: dict[str, tuple[str, ...]] = {
    "title": ("h1",),
    "bullets": ("h2",),
    "split": ("h2",),
    "steps": ("h2", "ol"),
    "table": ("h2", "table"),
}
BLOCK_NAMES = {
    "h1": "a # heading",
    "h2": "a ## heading",
    "phase": "a ### phase",
    "ul": "a - list",
    "ol": "a 1. list",
    "lead": "a > lead",
    "table": "a | table",
    "note": "an *italic note*",
    "para": "a paragraph",
}

BREAK = "\x01"  # stands in for a hard line break until the inline renderer turns it into <br>

HEADER = re.compile(r"^([a-z][a-z0-9-]*):(.*)$")
UL_ITEM = re.compile(r"^- (.*)$")
OL_ITEM = re.compile(r"^\d+\. (.*)$")
LEAD_LINE = re.compile(r"^> (.*)$")
TABLE_ROW = re.compile(r"^(\|.*)$")
BLOCK_START = re.compile(r"^(#{1,3} |- |> |\||\d+\. )")
DELIMITER_CELL = re.compile(r"^:?-+:?$")
STYLE_URL = re.compile(r"(url|image-set)\s*\(", re.IGNORECASE)


@dataclass(frozen=True)
class Block:
    kind: str
    text: str = ""
    body: str = ""
    items: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class Slide:
    number: int
    line: int
    meta: dict[str, str]
    blocks: tuple[Block, ...]

    @property
    def layout(self) -> str:
        return self.meta.get("layout", DEFAULT_LAYOUT)

    def first(self, kind: str) -> Block | None:
        return next((b for b in self.blocks if b.kind == kind), None)

    def flag(self, key: str) -> bool:
        return self.meta.get(key) == "yes"


@dataclass(frozen=True)
class Deck:
    path: Path
    config: dict[str, str]
    slides: tuple[Slide, ...]

    @property
    def title(self) -> str:
        return self.config.get("title", self.path.stem)

    def error(self, slide: Slide, message: str) -> DeckError:
        return _error(self.path, slide.line, f"slide {slide.number}: {message}")


Entry = tuple[int, str, str]  # (line number, key, value)


def load(path: Path) -> Deck:
    return parse(files.read_text(path, "deck"), path)


def parse(text: str, path: Path) -> Deck:
    chunks = _chunks(text)
    config_start, config_lines = chunks[0]
    entries, rest, _ = _split_header(config_start, config_lines)
    config: dict[str, str] = {}
    for line, key, value in entries:
        if key not in CONFIG_KEYS:
            raise _error(
                path, line, f"unknown config key '{key}' (expected one of: {', '.join(CONFIG_KEYS)})"
            )
        config[key] = value
    if any(line.strip() for line in rest):
        raise _error(
            path, config_start, "the config block may only hold key: value lines; start each slide after ---"
        )

    slides: list[Slide] = []
    for start, lines in chunks[1:]:
        if any(line.strip() for line in lines):
            slides.append(_slide(path, len(slides) + 1, start, lines))
    if not slides:
        raise DeckError(f"{path}: the deck has no slides; start each slide after a --- line")
    return Deck(path, config, tuple(slides))


def _error(path: Path, line: int, message: str) -> DeckError:
    return DeckError(f"{path}:{line}: {message}")


def _chunks(text: str) -> list[tuple[int, list[str]]]:
    """Split the source on `---` lines into (first line number, lines) chunks."""
    chunks: list[tuple[int, list[str]]] = [(1, [])]
    for number, line in enumerate(text.splitlines(), 1):
        if line.rstrip() == "---":
            chunks.append((number + 1, []))
        else:
            chunks[-1][1].append(line)
    return chunks


def _split_header(start: int, lines: list[str]) -> tuple[list[Entry], list[str], int]:
    """Peel the leading `key: value` lines off a chunk. Returns the entries, the body lines, and the
    line number of the chunk's first non-blank line."""
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    first = start + i
    entries: list[Entry] = []
    while i < len(lines) and (m := HEADER.match(lines[i])):
        entries.append((start + i, m.group(1), m.group(2).strip()))
        i += 1
    return entries, lines[i:], first


def _slide(path: Path, number: int, start: int, lines: list[str]) -> Slide:
    entries, body, first = _split_header(start, lines)

    def fail(message: str, line: int = first) -> DeckError:
        return _error(path, line, f"slide {number}: {message}")

    meta = {key: value for _, key, value in entries}
    layout = meta.get("layout", DEFAULT_LAYOUT)
    if layout not in LAYOUTS:
        raise fail(f"unknown layout '{layout}' (expected one of: {', '.join(LAYOUTS)})")

    for line, key, value in entries:
        owner = next((name for name, keys in LAYOUT_KEYS.items() if key in keys), None)
        if key not in COMMON_KEYS and owner is None:
            raise fail(f"unknown key '{key}'", line)
        if owner is not None and owner != layout:
            raise fail(f"'{key}' only applies to the {owner} layout", line)
        if key in FLAG_KEYS and value not in ("yes", "no"):
            raise fail(f"'{key}' must be yes or no, not '{value}'", line)
        if key == "image-max" and not (value.isdigit() and int(value) > 0):
            raise fail(f"'image-max' must be a positive whole number of pixels, not '{value}'", line)
        if key in STYLE_KEYS and STYLE_URL.search(value):
            raise fail(f"'{key}' can't reference files or URLs (url() or image-set())", line)
    for key in REQUIRED_KEYS.get(layout, ()):
        if key not in meta:
            raise fail(f"the {layout} layout needs an '{key}:' line")

    blocks = _blocks(_logical_lines(body))
    allowed = LAYOUT_BLOCKS[layout]
    seen: set[str] = set()
    for block in blocks:
        name = BLOCK_NAMES[block.kind]
        if block.kind not in allowed:
            raise fail(f"{name} isn't used by the {layout} layout")
        if block.kind in seen and not allowed[block.kind]:
            raise fail(f"the {layout} layout takes only one {name.split(' ', 1)[1]}")
        seen.add(block.kind)
    for kind in REQUIRED_BLOCKS[layout]:
        if kind not in seen:
            raise fail(f"the {layout} layout needs {BLOCK_NAMES[kind]}")

    return Slide(number, first, meta, tuple(blocks))


def _logical_lines(lines: list[str]) -> list[str]:
    """Fold continuations into one line each: a trailing backslash joins the next line as a hard break,
    a two-space indent joins it as flowing text."""
    out: list[str] = []
    for line in lines:
        stripped = line.rstrip()
        if not stripped.strip():
            out.append("")
        elif out and out[-1].endswith("\\"):
            out[-1] = out[-1][:-1] + BREAK + stripped.strip()
        elif stripped.startswith("  ") and out and out[-1]:
            out[-1] = out[-1] + " " + stripped.strip()
        else:
            out.append(stripped)
    return out


def _take(lines: list[str], i: int, pattern: re.Pattern[str]) -> tuple[list[str], int]:
    taken: list[str] = []
    while i < len(lines) and (m := pattern.match(lines[i])):
        taken.append(m.group(1))
        i += 1
    return taken, i


def _cells(line: str, protect_code: bool = True) -> tuple[str, ...]:
    """Split a table row on its pipes. A pipe inside a `code` span doesn't split, and `\\|` is a
    literal pipe anywhere. A row with an unclosed backtick is split as if it had none."""
    row = line.removeprefix("|")
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    cells: list[str] = []
    cell = ""
    in_code = False
    i = 0
    while i < len(row):
        if row.startswith("\\|", i):
            cell += "|"
            i += 2
            continue
        char = row[i]
        if char == "`" and protect_code:
            in_code = not in_code
        if char == "|" and not in_code:
            cells.append(cell.strip())
            cell = ""
        else:
            cell += char
        i += 1
    if in_code:
        return _cells(line, protect_code=False)
    cells.append(cell.strip())
    return tuple(cells)


def _table_rows(lines: list[str]) -> tuple[tuple[str, ...], ...]:
    rows = [_cells(line) for line in lines]
    if len(rows) > 1 and all(DELIMITER_CELL.match(cell) for cell in rows[1]):
        del rows[1]
    return tuple(rows)


def _is_note(line: str) -> bool:
    return line.startswith("*") and line.endswith("*") and not line.startswith("**")


def _blocks(lines: list[str]) -> list[Block]:
    out: list[Block] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("### "):
            i += 1
            body = ""
            if (
                i < len(lines)
                and lines[i].strip()
                and not BLOCK_START.match(lines[i])
                and not _is_note(lines[i])
            ):
                body = lines[i]
                i += 1
            out.append(Block("phase", text=line[4:], body=body))
        elif line.startswith("## "):
            out.append(Block("h2", text=line[3:]))
            i += 1
        elif line.startswith("# "):
            out.append(Block("h1", text=line[2:]))
            i += 1
        elif UL_ITEM.match(line):
            items, i = _take(lines, i, UL_ITEM)
            out.append(Block("ul", items=tuple(items)))
        elif OL_ITEM.match(line):
            items, i = _take(lines, i, OL_ITEM)
            out.append(Block("ol", items=tuple(items)))
        elif LEAD_LINE.match(line):
            parts, i = _take(lines, i, LEAD_LINE)
            out.append(Block("lead", text=" ".join(parts)))
        elif TABLE_ROW.match(line):
            rows, i = _take(lines, i, TABLE_ROW)
            out.append(Block("table", rows=_table_rows(rows)))
        elif _is_note(line):
            out.append(Block("note", text=line.strip("*")))
            i += 1
        else:
            parts = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not BLOCK_START.match(lines[i]):
                parts.append(lines[i])
                i += 1
            out.append(Block("para", text=" ".join(parts)))
    return out
