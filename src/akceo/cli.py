"""The akceo command line."""

import argparse
import sys
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

from akceo import files, render, themes
from akceo.errors import DeckError

VIEWER = "md-viewer.html"
GUIDE = Path(__file__).with_name("AGENTS.md")
INIT_MARKER = "<!-- akceo-init -->"
INIT_FILES = ("AGENTS.md", "CLAUDE.md")


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

    check = commands.add_parser("check", help="check a deck, diagrams included, without writing a file")
    check.add_argument("deck", type=Path, help="the deck's Markdown file")
    check.add_argument("-t", "--theme", help="built-in theme name or path to a .css file (overrides theme:)")

    commands.add_parser("themes", help="list the built-in themes")

    viewer = commands.add_parser(
        "viewer", help="write md-viewer.html, a live Markdown viewer for speaker notes"
    )
    viewer.add_argument(
        "-o", "--out", type=Path, default=Path(VIEWER), help=f"output file or folder (default: ./{VIEWER})"
    )

    docs = commands.add_parser("docs", help="print where the guide to writing decks is, for AI agents")
    docs.add_argument("--print", action="store_true", dest="text", help="print the guide itself")

    init = commands.add_parser(
        "init", help="add a section that points AI agents to the guide to AGENTS.md and CLAUDE.md"
    )
    init.add_argument(
        "folder", type=Path, nargs="?", default=Path("."), help="the folder the decks are in (default: .)"
    )
    init.add_argument("--dry-run", action="store_true", help="say what would change, and change nothing")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            _build(args.deck, args.out, args.theme)
        elif args.command == "check":
            _check(args.deck, args.theme)
        elif args.command == "viewer":
            _write_viewer(args.out)
        elif args.command == "docs":
            _docs(args.text)
        elif args.command == "init":
            _init(args.folder, args.dry_run)
        else:
            _list_themes()
    except DeckError as e:
        print(f"akceo: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("akceo: interrupted", file=sys.stderr)
        return 130
    return 0


def _build(deck: Path, out: Path | None, theme: str | None) -> None:
    page, count = render.build(deck, theme)
    out = out or deck.with_suffix(".html")
    _write(out, page)
    noun = "slide" if count == 1 else "slides"
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB, {count} {noun})")


def _check(deck: Path, theme: str | None) -> None:
    _, count = render.build(deck, theme)
    noun = "slide" if count == 1 else "slides"
    print(f"ok: {deck} ({count} {noun})")


def _write_viewer(out: Path) -> None:
    if out.is_dir():
        out = out / VIEWER
    _write(out, (render.ASSETS / VIEWER).read_text(encoding="utf-8"))
    print(f"wrote {out}")


def _docs(text: bool) -> None:
    if text:
        print(GUIDE.read_text(encoding="utf-8"), end="")
    else:
        print(GUIDE)


def _init(folder: Path, dry_run: bool) -> None:
    """Add the section that points agents to the guide to each of INIT_FILES in folder, creating the
    file if it's missing. A file that already has the section is left as it is."""
    if not folder.is_dir():
        raise DeckError(f"{folder}: not a folder")
    section = (render.ASSETS / "init-block.md").read_text(encoding="utf-8")
    for name in INIT_FILES:
        path = folder / name
        if not path.exists():
            text, done, would = section, "wrote", "would write"
        else:
            existing = files.read_text(path, "file").rstrip()
            if INIT_MARKER in existing:
                print(f"{path} already has the akceo section")
                continue
            text = (existing + "\n\n" if existing else "") + section
            done, would = "added the akceo section to", "would add the akceo section to"
        if not dry_run:
            _write(path, text)
        print(f"{would if dry_run else done} {path}")
    print("next: run akceo docs --print and read the guide before writing a deck")


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
