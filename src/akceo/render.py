"""Render a parsed deck into a single self-contained HTML page."""

import html
import json
import re
from importlib import resources
from pathlib import Path

from akceo import files, images, mermaid, parse, themes
from akceo.errors import DeckError
from akceo.parse import BREAK, Deck, Slide

ASSETS = resources.files("akceo") / "assets"
DEFAULT_IMAGE_MAX = 2400
PLACEHOLDER = re.compile(r"__(TITLE|STYLE|SLIDES|SCRIPT|DIAGRAMS)__")

ESCAPES = (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("≥", "&ge;"), ("≤", "&le;"), ("·", "&middot;"))
CODE = "\x00"  # brackets the index of a stashed `code` span, keeping it safe from the other inline rules


def build(deck_path: Path, theme: str | None = None) -> tuple[str, int]:
    """Build the page for the deck at deck_path. A theme passed here overrides the deck's own `theme:`
    and resolves against the working directory; the deck's resolves against the deck's folder.
    Returns the HTML and the slide count."""
    deck = parse.load(deck_path)
    if theme is not None:
        theme_css = themes.load(theme, Path.cwd())
    else:
        try:
            theme_css = themes.load(deck.config.get("theme", themes.DEFAULT), deck_path.parent)
        except DeckError as e:
            raise DeckError(f"{deck_path}: {e}") from None
    images_dir = deck_path.parent / Path(deck.config.get("images", ".")).expanduser()

    sections: list[str] = []
    with mermaid.Checker() as checker:
        for slide in deck.slides:
            diagram = _diagram(deck, slide, images_dir, checker)
            image_src = _image_src(deck, slide, images_dir)
            sections.append(render_slide(slide, image_src, deck.framed(slide), diagram))
    values = {
        "TITLE": escape(deck.title),
        "STYLE": _asset("base.css") + "\n" + theme_css,
        "SLIDES": "\n\n".join(sections),
        "SCRIPT": _asset("deck.js"),
        "DIAGRAMS": _diagram_scripts(theme_css) if any(map(_is_diagram, deck.slides)) else "",
    }
    page = PLACEHOLDER.sub(lambda m: values[m.group(1)], _asset("page.html"))
    return page, len(sections)


def _asset(name: str) -> str:
    return (ASSETS / name).read_text(encoding="utf-8")


def _is_diagram(slide: Slide) -> bool:
    return slide.meta.get("image", "").lower().endswith(".mmd")


def _image_src(deck: Deck, slide: Slide, images_dir: Path) -> str:
    """The slide's image as a data URI, or nothing for a diagram, which the page draws itself."""
    if "image" not in slide.meta or _is_diagram(slide):
        return ""
    max_px = int(slide.meta.get("image-max", DEFAULT_IMAGE_MAX))
    try:
        return images.data_uri(images_dir / slide.meta["image"], max_px)
    except DeckError as e:
        raise deck.error(slide, str(e)) from None


def _diagram(deck: Deck, slide: Slide, images_dir: Path, checker: mermaid.Checker) -> str:
    """The Mermaid source of the slide's diagram, checked with Mermaid's parser, or nothing."""
    if not _is_diagram(slide):
        return ""
    path = images_dir / slide.meta["image"]
    try:
        if not path.is_file():
            raise DeckError(f"image not found: {path}")
        source = files.read_text(path, "diagram")
        checker.check(path, source)
    except DeckError as e:
        raise deck.error(slide, str(e)) from None
    return source


def _diagram_scripts(theme_css: str) -> str:
    """Mermaid, the theme's Mermaid config and the script that draws the diagrams. The config is JSON
    with < escaped, so no value in it can close the script element."""
    config = json.dumps(mermaid.config(themes.values(theme_css))).replace("<", "\\u003c")
    return (
        f"<script>\n{mermaid.page_script()}\n</script>\n"
        f'<script type="application/json" id="mermaid-theme">{config}</script>\n'
        f"<script>\n{_asset('diagrams.js')}</script>\n"
    )


# ---------------------------------------------------------------- inline text


def escape(text: str) -> str:
    for raw, entity in ESCAPES:
        text = text.replace(raw, entity)
    return text


def inline(text: str) -> str:
    """Render the inline markup: `code`, **bold**, ***strong***, ==accent==, ((dimmed)) and hard breaks."""
    spans: list[str] = []

    def stash(match: re.Match[str]) -> str:
        spans.append(match.group(1))
        return CODE + str(len(spans) - 1) + CODE

    text = re.sub(r"`([^`]+)`", stash, text)
    text = escape(text)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r'<b class="strong">\1</b>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"==(.+?)==", r'<span class="hl">\1</span>', text)
    text = re.sub(r"\(\((.+?)\)\)", r'<span class="dim">(\1)</span>', text)
    text = re.sub(
        CODE + r"(\d+)" + CODE, lambda m: "<code>" + escape(spans[int(m.group(1))]) + "</code>", text
    )
    return text.replace(BREAK, "<br>")


# ------------------------------------------------------------------ slides


def _style(slide: Slide, target: str) -> str:
    value = slide.meta.get("style-" + target)
    return f' style="{html.escape(value)}"' if value else ""


def _text(slide: Slide, kind: str) -> str:
    block = slide.first(kind)
    return block.text if block else ""


def _list(tag: str, items: tuple[str, ...], indent: str, attrs: str = "") -> list[str]:
    return [
        f"{indent}<{tag}{attrs}>",
        *(f"{indent}  <li>{inline(x)}</li>" for x in items),
        f"{indent}</{tag}>",
    ]


def _figure(slide: Slide, image_src: str, framed: bool, diagram: str) -> str:
    """The slide's image, or a dashed box holding its place while there's no image: line yet. An
    image without a frame gets the bare class, which drops the panel behind it.

    A diagram carries its Mermaid source for the page to draw. One without a frame is drawn in the
    theme's colors; one in a frame keeps Mermaid's defaults, since theme colors may not read on the
    frame's white."""
    if "image" not in slide.meta:
        return '<div class="placeholder"></div>'
    alt = html.escape(slide.meta.get("image-alt", ""))
    if diagram:
        cls, colors = ("diagram", "default") if framed else ("diagram bare", "theme")
        source = html.escape(diagram, quote=False)
        return (
            f'<div class="{cls}" role="img" aria-label="{alt}" data-mermaid="{colors}">'
            f'<pre class="diagram-src">{source}</pre></div>'
        )
    bare = "" if framed else ' class="bare"'
    return f'<img{bare} src="{image_src}" alt="{alt}">'


def render_slide(slide: Slide, image_src: str = "", framed: bool = True, diagram: str = "") -> str:
    kicker = slide.meta.get("kicker")
    kicker_html = [f'    <div class="kicker">{inline(kicker)}</div>'] if kicker else []

    if slide.layout == "title":
        out = ['  <section class="slide title-wrap">', *kicker_html]
        out.append(f"    <h1{_style(slide, 'h1')}>{inline(_text(slide, 'h1'))}</h1>")
        out.append('    <div class="rule"></div>')
        if "meta" in slide.meta:
            out.append(f'    <div class="meta">{inline(slide.meta["meta"])}</div>')
        out.append("  </section>")
        return "\n".join(out)

    # A split slide puts its kicker in the text column, so it stays with the heading.
    out = ['  <section class="slide">', *(kicker_html if slide.layout != "split" else [])]
    h2 = f"<h2{_style(slide, 'h2')}>{inline(_text(slide, 'h2'))}</h2>"

    if slide.layout == "image":
        out.append(f'    <div class="figure-full">{_figure(slide, image_src, framed, diagram)}</div>')

    elif slide.layout == "split":
        wide = " img-wide" if slide.flag("image-wide") else ""
        out.append(f'    <div class="split{wide}">')
        out.append(f'      <div class="figwrap">{_figure(slide, image_src, framed, diagram)}</div>')
        out.append("      <div>")
        out.extend("    " + line for line in kicker_html)
        out.append(f"        {h2}")
        for block in slide.blocks:
            if block.kind == "phase":
                body = f"<p>{inline(block.body)}</p>" if block.body else ""
                phase = f"<h3>{inline(block.text)}</h3>{body}"
                out.append(f'        <div class="phase">{phase}</div>')
            elif block.kind == "ul":
                out.extend(_list("ul", block.items, "        ", _style(slide, "ul")))
        note = slide.first("note")
        if note:
            out.append(f'        <p class="note-inline">{inline(note.text)}</p>')
        out.append("      </div>")
        out.append("    </div>")

    elif slide.layout == "steps":
        out.append(f"    {h2}")
        para = slide.first("para")
        if para:
            out.append(f'    <p class="sub"{_style(slide, "sub")}>{inline(para.text)}</p>')
        ol = slide.first("ol")
        out.extend(_list("ol", ol.items if ol else (), "    ", ' class="steps"' + _style(slide, "ol")))

    elif slide.layout == "table":
        out.append(f"    {h2}")
        table = slide.first("table")
        rows = table.rows if table else ()
        dim_last = slide.flag("dim-last-column")
        out.append("    <table>")
        if rows:
            headers = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
            out.append(f"      <thead><tr>{headers}</tr></thead>")
        out.append("      <tbody>")
        for row in rows[1:]:
            cells = [f"<td>{inline(c)}</td>" for c in row]
            if dim_last and cells:
                cells[-1] = f'<td class="dim">{inline(row[-1])}</td>'
            out.append(f"        <tr>{''.join(cells)}</tr>")
        out.append("      </tbody>")
        out.append("    </table>")

    else:  # bullets
        out.append(f"    {h2}")
        lead = slide.first("lead")
        if lead:
            out.append(f'    <p class="lead"{_style(slide, "lead")}>{inline(lead.text)}</p>')
        ul = slide.first("ul")
        if ul:
            out.extend(_list("ul", ul.items, "    ", _style(slide, "ul")))
        para = slide.first("para")
        if para:
            out.append(f'    <p class="sub"{_style(slide, "sub")}>{inline(para.text)}</p>')

    out.append("  </section>")
    return "\n".join(out)
