"""The akceo command line."""

import argparse
import sys
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

from akceo import render, themes
from akceo.errors import DeckError

VIEWER = "md-viewer.html"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="akceo", description="Build self-contained HTML slide decks from Markdown."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {version('akceo')}")
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="render a deck into a single HTML file")
    build.add_argument("deck", type=Path, help="the deck's Markdown file")
    build.add_argument("-o", "--out", type=Path, help="output file (default: the deck's name with .html)")
    build.add_argument("-t", "--theme", help="built-in theme name or path to a .css file (overrides theme:)")

    commands.add_parser("themes", help="list the built-in themes")

    viewer = commands.add_parser(
        "viewer", help="write md-viewer.html, a live Markdown viewer for speaker notes"
    )
    viewer.add_argument(
        "-o", "--out", type=Path, default=Path(VIEWER), help=f"output file or folder (default: ./{VIEWER})"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            _build(args.deck, args.out, args.theme)
        elif args.command == "viewer":
            _write_viewer(args.out)
        else:
            _list_themes()
    except DeckError as e:
        print(f"akceo: {e}", file=sys.stderr)
        return 1
    return 0


def _build(deck: Path, out: Path | None, theme: str | None) -> None:
    page, count = render.build(deck, theme)
    out = out or deck.with_suffix(".html")
    _write(out, page)
    noun = "slide" if count == 1 else "slides"
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB, {count} {noun})")


def _write_viewer(out: Path) -> None:
    if out.is_dir():
        out = out / VIEWER
    _write(out, (render.ASSETS / VIEWER).read_text(encoding="utf-8"))
    print(f"wrote {out}")


def _write(out: Path, text: str) -> None:
    try:
        out.write_text(text, encoding="utf-8")
    except OSError as e:
        raise DeckError(f"{out}: {e.strerror}") from None


def _list_themes() -> None:
    names = themes.builtin()
    width = max(map(len, names))
    for name, description in names.items():
        default = " (default)" if name == themes.DEFAULT else ""
        print(f"{name.ljust(width)}  {description}{default}")
