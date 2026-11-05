"""The akceo command line."""

import argparse
import json
import os
import sys
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

from akceo import files, render, report, themes
from akceo.errors import DeckError

VIEWER = "md-viewer.html"
GUIDE = Path(__file__).with_name("guide.md")
INIT_MARKER = "<!-- akceo-init -->"
INIT_FILES = ("AGENTS.md", "CLAUDE.md")
INIT_VERBS = {
    "x": ("wrote", "would write"),
    "a": ("added the akceo section to", "would add the akceo section to"),
}


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
    check.add_argument("--json", action="store_true", help="print the result as JSON, for agents and scripts")

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
            return _check(args.deck, args.theme, args.json)
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


def _check(deck: Path, theme: str | None, as_json: bool) -> int:
    if as_json:
        result = report.check(deck, theme)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    _, count = render.build(deck, theme)
    noun = "slide" if count == 1 else "slides"
    print(f"ok: {deck} ({count} {noun})")
    return 0


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
    """Append the section that points agents to the guide to each of INIT_FILES in folder, creating a
    file that's missing. A file that has the section already is left as it is. Every file is read
    before any is written, so a problem with one leaves both unchanged."""
    if not os.path.isdir(folder):
        raise DeckError("init-not-folder", "not a folder", folder)
    section = (render.ASSETS / "init-block.md").read_text(encoding="utf-8")
    plan: list[tuple[Path, str, str]] = []  # (path, mode, text); with no mode, text is only reported
    targets: dict[Path, Path] = {}
    for name in INIT_FILES:
        path = folder / name
        target = Path(os.path.realpath(path))
        if not target.is_relative_to(os.path.realpath(folder)):
            message = f"{path} links to {target}, outside {folder}; akceo init writes only inside it"
            raise DeckError("init-link-outside", message)
        if target in targets:
            plan.append((path, "", f"{path} is the same file as {targets[target]}"))
            continue
        targets[target] = path
        if os.path.islink(path) and not os.path.exists(path):
            raise DeckError("init-broken-link", f"{path} links to {target}, which doesn't exist")
        if not os.path.lexists(path):
            plan.append((path, "x", section))
            continue
        existing = files.read_text(path, "file", newline="")
        if INIT_MARKER in existing:
            plan.append((path, "", f"{path} already has the akceo section"))
            continue
        newline = "\r\n" if "\r\n" in existing else "\n"
        plan.append((path, "a", _gap(existing, newline) + section.replace("\n", newline)))
    for path, mode, text in plan:
        if not mode:
            print(text)
            continue
        if not dry_run:
            _write_section(path, mode, text)
        done, would = INIT_VERBS[mode]
        print(f"{would if dry_run else done} {path}")
    print("next: run akceo docs --print and read the guide before writing a deck")


def _gap(existing: str, newline: str) -> str:
    """What goes between a file's text and the section appended to it, to leave one blank line."""
    if not existing.strip() or existing.endswith(newline * 2):
        return ""
    return newline if existing.endswith(newline) else newline * 2


def _write_section(path: Path, mode: str, text: str) -> None:
    """Create path ("x") or append to it ("a"), leaving whatever it already holds as it was."""
    try:
        with path.open(mode, encoding="utf-8", newline="") as f:
            f.write(text)
    except OSError as e:
        raise DeckError("file-unwritable", str(e.strerror), path) from None


def _write(out: Path, text: str) -> None:
    try:
        out.write_text(text, encoding="utf-8")
    except OSError as e:
        raise DeckError("file-unwritable", str(e.strerror), out) from None


def _list_themes() -> None:
    names = themes.builtin()
    width = max(map(len, names))
    for name, description in names.items():
        default = " (default)" if name == themes.DEFAULT else ""
        print(f"{name.ljust(width)}  {description}{default}")
