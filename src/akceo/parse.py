"""Parse akceo's Markdown dialect into a validated deck. The format is described in docs/syntax.md."""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from akceo import files
from akceo.errors import Code, DeckError, WarningCode

LAYOUTS = ("title", "bullets", "split", "steps", "table", "image")
DEFAULT_LAYOUT = "bullets"
CONFIG_KEYS = ("title", "description", "url", "icon", "theme", "images", "image-frame")
STYLE_KEYS = ("style-h1", "style-h2", "style-lead", "style-ul", "style-ol", "style-sub")
COMMON_KEYS = ("layout", "kicker", *STYLE_KEYS)
LAYOUT_KEYS: dict[str, tuple[str, ...]] = {
    "title": ("meta",),
    "bullets": (),
    "split": ("image", "image-alt", "image-max", "image-crop", "image-wide", "image-frame"),
    "steps": (),
    "table": ("dim-last-column",),
    "image": ("image", "image-alt", "image-max", "image-crop", "image-frame"),
}
FLAG_KEYS = ("image-wide", "dim-last-column", "image-frame")
SLIDE_KEYS = {*COMMON_KEYS, *(key for keys in LAYOUT_KEYS.values() for key in keys)}

# Block kinds each layout renders, mapped to whether that kind may appear more than once.
LAYOUT_BLOCKS: dict[str, dict[str, bool]] = {
    "title": {"h1": False},
    "bullets": {"h2": False, "lead": False, "ul": False, "para": False},
    "split": {"h2": False, "phase": True, "ul": True, "note": False},
    "steps": {"h2": False, "para": False, "ol": False},
    "table": {"h2": False, "table": False},
    "image": {"h2": False, "para": False},
}
REQUIRED_BLOCKS: dict[str, tuple[str, ...]] = {
    "title": ("h1",),
    "bullets": ("h2",),
    "split": ("h2",),
    "steps": ("h2", "ol"),
    "table": ("h2", "table"),
    "image": (),
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
CODE_SPAN = re.compile(r"`[^`]+`")
LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\n]*)\)")
OUTSIDE_LINK = re.compile(r"(https?://|mailto:)[^\s\"'<>`\x01]+", re.IGNORECASE)  # \x01 is BREAK
SLIDE_LINK = re.compile(r"#([0-9]+)")  # ASCII digits only, as deck.js reads the hash
# Pixel counts take at most nine ASCII digits. str.isdigit() also passes digits such as "²", which
# int() rejects, and int() refuses a string past its digit limit.
PIXELS = re.compile(r"[0-9]{1,9}")
CROP = re.compile(r"([0-9]{1,9})" + r"(?:\s*,\s*|\s+)([0-9]{1,9})" * 3)
# C0 control characters, apart from tab, line feed, form feed and carriage return. The renderer
# uses some as placeholders, and none of them belongs on a slide.
CONTROL = re.compile(r"[\x00-\x08\x0b\x0e-\x1f]")
# Markdown akceo doesn't read, and keys written as text, which stray_markdown() finds
FENCE = re.compile(r"\s*(`{3,}|~{3,})")
CLOSING_FENCE = re.compile(r"\s*(`{3,}|~{3,})\s*")
NESTED_ITEM = re.compile(r"\s+(-|\d+\.) ")
BULLET = re.compile(r"\s*([*+]) ")
DEEP_HEADING = re.compile(r"(#{4,})(\s|$)")
KEY_LIKE = re.compile(r"([A-Za-z][A-Za-z0-9-]*):")

Stray = tuple[WarningCode, str]  # the warning for a line of slide text, and why it shows as text


@dataclass(frozen=True)
class Block:
    kind: str
    text: str = ""
    body: str = ""
    items: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()
    line: int = field(default=0, compare=False)  # where the block starts in the deck file


@dataclass(frozen=True)
class Slide:
    number: int
    line: int
    meta: dict[str, str]
    blocks: tuple[Block, ...]
    # The lines of slide text that show as text but were likely meant as something else, by line
    stray: dict[int, Stray] = field(default_factory=dict[int, Stray], compare=False)

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
    config_lines: dict[str, int] = field(default_factory=dict[str, int], compare=False)  # key: its line

    @property
    def title(self) -> str:
        return self.config.get("title", self.path.stem)

    def framed(self, slide: Slide) -> bool:
        """Whether the slide's image sits in a panel. The slide's image-frame wins over the deck's."""
        return slide.meta.get("image-frame", self.config.get("image-frame", "yes")) == "yes"

    def has_links(self) -> bool:
        texts = (text for slide in self.slides for _, text in slide_texts(slide))
        return any(LINK.search(_without_code(text)) for text in texts)


Entry = tuple[int, str, str]  # (line number, key, value)


def load(path: Path) -> Deck:
    return parse(files.read_text(path, "deck"), path)


def parse(text: str, path: Path) -> Deck:
    control = CONTROL.search(text)
    if control:
        line = text.count("\n", 0, control.start()) + 1
        raise DeckError(
            "deck-control-character",
            f"a control character (U+{ord(control.group()):04X}) can't be in a deck",
            path,
            line,
        )
    chunks = _chunks(text)
    config_start, config_lines = chunks[0]
    entries, rest, _ = _split_header(config_start, config_lines)
    config: dict[str, str] = {}
    key_lines: dict[str, int] = {}
    for line, key, value in entries:
        if key not in CONFIG_KEYS:
            raise DeckError(
                "key-unknown",
                f"unknown config key '{key}' (expected one of: {', '.join(CONFIG_KEYS)})",
                path,
                line,
            )
        if key in FLAG_KEYS and value not in ("yes", "no"):
            raise DeckError("value-not-yes-or-no", f"'{key}' must be yes or no, not '{value}'", path, line)
        if key == "url" and not _is_page_url(value):
            raise DeckError(
                "url-invalid",
                f"'url' must be the page's full address, starting https:// or http://, not '{value}'",
                path,
                line,
            )
        config[key] = value
        key_lines[key] = line
    if any(_has_content(line) for line in rest):
        raise DeckError(
            "config-not-key-value",
            "the config block may only hold key: value lines; start each slide after ---",
            path,
            config_start,
        )

    slides: list[Slide] = []
    for start, lines in chunks[1:]:
        if any(_has_content(line) for line in lines):
            slides.append(_slide(path, len(slides) + 1, start, lines))
    if not slides:
        raise DeckError("deck-no-slides", "the deck has no slides; start each slide after a --- line", path)
    for slide in slides:
        _check_links(path, slide, len(slides))
    return Deck(path, config, tuple(slides), key_lines)


def slide_texts(slide: Slide) -> list[tuple[int, str]]:
    """Each text the slide shows, with the line it's on: a block's first line, or the slide's for
    the kicker and meta keys."""
    texts = [(slide.line, slide.meta.get("kicker", "")), (slide.line, slide.meta.get("meta", ""))]
    for block in slide.blocks:
        cells = (cell for row in block.rows for cell in row)
        texts += [(block.line, text) for text in (block.text, block.body, *block.items, *cells)]
    return texts


def _without_code(text: str) -> str:
    """The text with each code span blanked to spaces of the same length. A label that is only code
    still reads as a link, as it does to the renderer, a URL with code in it fails the check, and
    positions still match the original text, for quoting it in errors."""
    return CODE_SPAN.sub(lambda m: " " * len(m.group()), text)


def _check_links(path: Path, slide: Slide, count: int) -> None:
    """Every [text](url) must go to the web, to an email address, or to a slide in this deck. A
    link inside a code span is code, not a link."""
    for line, text in slide_texts(slide):
        for m in LINK.finditer(_without_code(text)):
            url = m.group(2)
            written = text[m.start(2) : m.end(2)]
            if BREAK in url:
                message = f"a link's URL can't continue onto the next line ('{written.replace(BREAK, '\\')}')"
                raise DeckError("link-split", message, path, line, slide.number)
            slide_link = SLIDE_LINK.fullmatch(url)
            if slide_link and not _names_a_slide(slide_link.group(1), count):
                message = f"the link to {url} goes past the last slide, {count}"
                raise DeckError("link-past-last-slide", message, path, line, slide.number)
            if not slide_link and not OUTSIDE_LINK.fullmatch(url):
                raise DeckError(
                    "link-target-invalid",
                    f"can't link to '{written}'; a link goes to an https:, http: or mailto: address, or to a "
                    "slide as #N",
                    path,
                    line,
                    slide.number,
                )


def _is_page_url(value: str) -> bool:
    """Whether value is a full http:// or https:// address with a host. urlsplit, and reading the
    port, raise ValueError on a malformed authority, such as an unclosed IPv6 bracket or a port
    that isn't a number."""
    if any(c.isspace() for c in value):
        return False
    try:
        parts = urlsplit(value)
        _ = parts.port
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def _names_a_slide(digits: str, count: int) -> bool:
    """Whether #digits opens one of count slides. deck.js reads the hash with parseInt, so leading
    zeros don't change the slide. The length check keeps int() inside its digit limit; no deck has
    a billion slides."""
    significant = digits.lstrip("0") or "0"
    return len(significant) <= 9 and 1 <= int(significant) <= count


def _chunks(text: str) -> list[tuple[int, list[str]]]:
    """Split the source on `---` lines into (first line number, lines) chunks."""
    chunks: list[tuple[int, list[str]]] = [(1, [])]
    for number, line in enumerate(text.splitlines(), 1):
        if line.rstrip() == "---":
            chunks.append((number + 1, []))
        else:
            chunks[-1][1].append(line)
    return chunks


def _is_author_note(line: str) -> bool:
    """A `//` line is for the deck's author. The parser drops it wherever it appears."""
    return line.lstrip().startswith("//")


def _has_content(line: str) -> bool:
    return bool(line.strip()) and not _is_author_note(line)


def _split_header(start: int, lines: list[str]) -> tuple[list[Entry], list[str], int]:
    """Peel the leading `key: value` lines off a chunk, skipping author notes among them. Returns the
    entries, the body lines, and the line number of the chunk's first line with content."""
    i = 0
    while i < len(lines) and not _has_content(lines[i]):
        i += 1
    first = start + i
    entries: list[Entry] = []
    while i < len(lines) and ((m := HEADER.match(lines[i])) or _is_author_note(lines[i])):
        if m:
            entries.append((start + i, m.group(1), m.group(2).strip()))
        i += 1
    return entries, lines[i:], first


def _slide(path: Path, number: int, start: int, lines: list[str]) -> Slide:
    entries, body, first = _split_header(start, lines)

    def fail(code: Code, message: str, line: int = first) -> DeckError:
        return DeckError(code, message, path, line, number)

    meta = {key: value for _, key, value in entries}
    layout = meta.get("layout", DEFAULT_LAYOUT)
    if layout not in LAYOUTS:
        raise fail("layout-unknown", f"unknown layout '{layout}' (expected one of: {', '.join(LAYOUTS)})")

    for line, key, value in entries:
        owners = [name for name, keys in LAYOUT_KEYS.items() if key in keys]
        if key not in COMMON_KEYS and not owners:
            raise fail("key-unknown", f"unknown key '{key}'", line)
        if owners and layout not in owners:
            noun = "layout" if len(owners) == 1 else "layouts"
            raise fail("key-wrong-layout", f"'{key}' only applies to the {_join(owners)} {noun}", line)
        if key in FLAG_KEYS and value not in ("yes", "no"):
            raise fail("value-not-yes-or-no", f"'{key}' must be yes or no, not '{value}'", line)
        if key == "image-max":
            try:
                pixel_count(value, key)
            except DeckError as e:
                raise e.within(path, line, number) from None
        if key == "image-crop":
            try:
                crop_box(value, key)
            except DeckError as e:
                raise e.within(path, line, number) from None
            image = meta.get("image", "")
            if image.lower().endswith((".svg", ".mmd")):
                message = f"'image-crop' only works on PNG, JPEG and WebP images, not {image}"
                raise fail("image-option-unsupported", message, line)
        if key in STYLE_KEYS and STYLE_URL.search(value):
            raise fail("style-url", f"'{key}' can't reference files or URLs (url() or image-set())", line)

    body_start = start + len(lines) - len(body)
    blocks = _blocks(*_logical_lines(body, body_start))
    stray = stray_markdown(enumerate(body, body_start))

    def fail_block(code: Code, message: str, block: Block) -> DeckError:
        """An error about a block, with the reason when the block starts with a stray line."""
        if block.line in stray:
            reason = stray[block.line][1]
            message += ". " + reason[0].upper() + reason[1:]
        return fail(code, message, block.line)

    allowed = LAYOUT_BLOCKS[layout]
    seen: set[str] = set()
    for block in blocks:
        name = BLOCK_NAMES[block.kind]
        if block.kind not in allowed:
            takes = _join([BLOCK_NAMES[kind] for kind in allowed]) if allowed else "no content"
            raise fail_block(
                "block-not-in-layout", f"{name} isn't used by the {layout} layout, which takes {takes}", block
            )
        if block.kind in seen and not allowed[block.kind]:
            raise fail_block(
                "block-repeated", f"the {layout} layout takes only one {name.split(' ', 1)[1]}", block
            )
        seen.add(block.kind)
    for kind in REQUIRED_BLOCKS[layout]:
        if kind not in seen:
            raise fail("block-missing", f"the {layout} layout needs {BLOCK_NAMES[kind]}")

    return Slide(number, first, meta, tuple(blocks), stray)


def stray_markdown(lines: Iterable[tuple[int, str]]) -> dict[int, Stray]:
    """Each of lines, the numbered lines of a slide's text, that shows as text but was likely meant as
    something else, with its warning. Every line of a fenced block gets the fence's warning, since
    all of it shows as text. A capitalized key counts only at the top, where keys go: further down,
    "Image: a cat" is ordinary text."""
    found: dict[int, Stray] = {}
    fence: Stray | None = None
    opened = ""
    at_top = True
    for number, line in lines:
        if _is_author_note(line):
            continue
        mark = FENCE.match(line)
        if fence is None and mark:
            opened = mark[1]
            fence = ("markdown-code-fence", f"{mark[1]} shows as text; akceo has no code blocks yet")
            found[number] = fence
        elif fence is not None:
            found[number] = fence
            if _closes(line, opened):
                fence = None
        else:
            key = KEY_LIKE.match(line)
            at_top = at_top and key is not None
            if stray := _stray_line(line, key, at_top):
                found[number] = stray
    return found


def _closes(line: str, opened: str) -> bool:
    """CommonMark's rule: a fence closes on a run of its opening's character, at least as long,
    with nothing after it but whitespace."""
    closing = CLOSING_FENCE.fullmatch(line)
    return bool(closing) and closing[1][0] == opened[0] and len(closing[1]) >= len(opened)


def _stray_line(line: str, key: re.Match[str] | None, at_top: bool) -> Stray | None:
    if NESTED_ITEM.match(line):
        reason = "an indented list item joins the item above it as text; lists are one level deep"
        return "markdown-nested-list", reason
    if bullet := BULLET.match(line):
        return "markdown-bullet", f"a list item that starts with {bullet[1]} shows as text; use - instead"
    if heading := DEEP_HEADING.match(line):
        return "markdown-heading", f"a {heading[1]} heading shows as text; use ## for the slide's heading"
    if key and key[1].lower() in SLIDE_KEYS and (key[1].islower() or at_top):
        where = "at the top of the slide, in lowercase, before the blank line"
        return "key-in-text", f"'{key[0]}' shows as text; a key goes {where}"
    return None


def pixel_count(value: str, key: str) -> int:
    """A positive whole number of pixels. Anything else raises a DeckError naming key, the setting it
    came from."""
    if not (PIXELS.fullmatch(value) and int(value) > 0):
        raise DeckError(
            "value-not-pixels",
            f"'{key}' must be a positive whole number of pixels, at most nine digits 0-9, not '{value}'",
        )
    return int(value)


def crop_box(value: str, key: str) -> tuple[int, int, int, int]:
    """A crop value as (left, top, right, bottom). A value that isn't four whole numbers, or that
    keeps nothing, raises a DeckError naming key, the setting it came from."""
    m = CROP.fullmatch(value.strip())
    if not m:
        raise DeckError(
            "crop-invalid",
            f"'{key}' must be four whole numbers of pixels, left, top, right and bottom, each at most nine "
            f"digits 0-9, such as 120, 80, 920, 580, not '{value}'",
        )
    left, top, right, bottom = map(int, m.groups())
    if right <= left or bottom <= top:
        raise DeckError(
            "crop-empty", f"'{key}' {value} is empty: right must be past left, and bottom below top"
        )
    return left, top, right, bottom


def _join(names: list[str]) -> str:
    """Join names as prose: "a", "a and b", "a, b and c"."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _logical_lines(lines: list[str], start: int) -> tuple[list[str], list[int]]:
    """Fold continuations into one line each: a trailing backslash joins the next line as a hard break,
    a two-space indent joins it as flowing text. Author notes are dropped first, so they never join
    or split anything. Returns the folded lines and, for each, the file line it starts on; start is
    the file line of lines[0]."""
    out: list[str] = []
    numbers: list[int] = []
    for number, line in enumerate(lines, start):
        stripped = line.rstrip()
        if _is_author_note(line):
            continue
        if not stripped.strip():
            out.append("")
            numbers.append(number)
        elif out and out[-1].endswith("\\"):
            out[-1] = out[-1][:-1] + BREAK + stripped.strip()
        elif stripped.startswith("  ") and out and out[-1]:
            out[-1] = out[-1] + " " + stripped.strip()
        else:
            out.append(stripped)
            numbers.append(number)
    return out, numbers


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


def _blocks(lines: list[str], numbers: list[int]) -> list[Block]:
    """The blocks in lines, each with the file line it starts on, from numbers."""
    out: list[Block] = []
    i = 0
    while i < len(lines):
        line, number = lines[i], numbers[i]
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
            out.append(Block("phase", text=line[4:], body=body, line=number))
        elif line.startswith("## "):
            out.append(Block("h2", text=line[3:], line=number))
            i += 1
        elif line.startswith("# "):
            out.append(Block("h1", text=line[2:], line=number))
            i += 1
        elif UL_ITEM.match(line):
            items, i = _take(lines, i, UL_ITEM)
            out.append(Block("ul", items=tuple(items), line=number))
        elif OL_ITEM.match(line):
            items, i = _take(lines, i, OL_ITEM)
            out.append(Block("ol", items=tuple(items), line=number))
        elif LEAD_LINE.match(line):
            parts, i = _take(lines, i, LEAD_LINE)
            out.append(Block("lead", text=" ".join(parts), line=number))
        elif TABLE_ROW.match(line):
            rows, i = _take(lines, i, TABLE_ROW)
            out.append(Block("table", rows=_table_rows(rows), line=number))
        elif _is_note(line):
            out.append(Block("note", text=line.strip("*"), line=number))
            i += 1
        else:
            parts = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not BLOCK_START.match(lines[i]):
                parts.append(lines[i])
                i += 1
            out.append(Block("para", text=" ".join(parts), line=number))
    return out
