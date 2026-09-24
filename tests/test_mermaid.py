import hashlib
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from akceo import mermaid
from akceo.errors import DeckError
from akceo.mermaid import Checker

FLOW = Path("flow.mmd")


@pytest.fixture(scope="module")
def checker() -> Iterator[Checker]:
    with Checker() as c:
        yield c


def error(checker: Checker, source: str) -> str:
    with pytest.raises(DeckError) as e:
        checker.check(FLOW, source)
    return str(e.value)


@pytest.mark.parametrize(
    "source",
    [
        "flowchart LR\n  a --> b\n",
        "sequenceDiagram\n  Alice->>Bob: hi\n",
        # The newer parser behind these needs the TextEncoder and structuredClone stand-ins.
        'pie\n  "a": 1\n',
        "gitGraph\n  commit\n  branch x\n  commit\n",
        # These call DOMPurify, which needs the no-op stand-in when there's no DOM.
        "classDiagram\n  A <|-- B\n",
        "stateDiagram-v2\n  [*] --> A\n",
        "%%{init: {'theme': 'base'}}%%\nflowchart LR\n  a --> b\n",
        # Links to a slide, data: images and URLs that are only text keep the deck self-contained.
        'flowchart LR\n  a --> b\n  click a "#5" "Go to slide 5"\n',
        'flowchart LR\n  b@{ img: "data:image/png;base64,AAAA", label: "L" }\n',
        'flowchart LR\n  a["see https://example.com"] --> b\n',
        'flowchart LR\n  a["Docs, img: https://example.com/guide"] --> b\n',
        'flowchart LR\n  %% click a href "https://example.com"\n  a --> b\n',
        # A srcset of data: URIs only, whose own commas don't split it.
        "flowchart LR\n  a[\"<img srcset='data:image/png;base64,AAAA 1x, "
        "data:image/png;base64,BB 2x'>\"] --> b\n",
        # url(#…) points inside the SVG itself.
        '%%{init: {"themeCSS": ".x { marker-end: url(#arrow) }"}}%%\nflowchart LR\n  a --> b\n',
    ],
)
def test_valid_diagrams_pass(checker: Checker, source: str):
    checker.check(FLOW, source)


def test_a_syntax_error_names_the_line_and_what_mermaid_expected(checker: Checker):
    source = "flowchart LR\n  a --> b\n  b --> c\n  c --> d{{x]\n  d --> e\n"
    assert error(checker, source) == (
        "flow.mmd:4: Parse error: Expecting 'DIAMOND_STOP', 'TAGEND', 'UNICODE_TEXT', 'TEXT', 'TAGSTART', "
        "got 'SQE'"
    )


@pytest.mark.parametrize(
    ("source", "line"),
    [
        ("%%{init: {'theme': 'base'}}%%\nflowchart LR\n  a --> b\n  b --> c(x]\n", 4),
        ("---\ntitle: T\n---\nflowchart LR\n  a --> b\n  b --> c(x]\n", 6),
        ("\n%% top\nflowchart LR\n  %% note\n  a --> b\n  %% more\n  b --> c(x]\n  c --> d\n", 7),
        ("flowchart LR\r\n  a --> b\r\n  b --> c(x]\r\n", 3),
        # An error at the end of the text points at the last line.
        ("flowchart LR\n  a -->\n", 2),
    ],
)
def test_error_lines_count_what_mermaid_drops_before_parsing(checker: Checker, source: str, line: int):
    assert error(checker, source).startswith(f"flow.mmd:{line}: Parse error: ")


def test_errors_from_the_newer_parser_name_the_line(checker: Checker):
    assert error(checker, "%% c\ngitGraph\n  commit\n  comit\n") == (
        "flow.mmd:4: Parse error on line 4, column 3: Expecting token of type 'EOF' but found `comit`."
    )


@pytest.mark.parametrize(
    ("source", "line"),
    [
        ("\n\nflowchrt LR\n  a --> b\n", 3),
        ("%% comment\nflowchrt LR\n", 2),
        ("---\ntitle: T\n---\nflowchrt LR\n", 4),
        ("%%{init: {'theme': 'base'}}%%\nflowchrt LR\n", 2),
    ],
)
def test_an_unknown_diagram_type_names_the_line_it_is_on(checker: Checker, source: str, line: int):
    assert error(checker, source) == (
        f"flow.mmd:{line}: Mermaid doesn't recognise the diagram type; start with one such as flowchart"
    )


OUTSIDE = [
    # The http(s) link also needs the URL stand-in; without it the check crashed.
    ('flowchart LR\n  a --> b\n  click a href "https://x.example/docs"\n', 3, "https://x.example/docs"),
    ('flowchart LR\n  a --> b\n  click a "https://x.example" "tip" _blank\n', 3, "https://x.example"),
    ('flowchart LR\n  a --> b; click a href "https://x.example"\n', 2, "https://x.example"),
    ('classDiagram\n  class Foo\n  link Foo "https://x.example"\n', 3, "https://x.example"),
    ("sequenceDiagram\n  participant A\n  link A: Home @ https://x.example\n", 3, "https://x.example"),
    ('sequenceDiagram\n  participant A\n  links A: {"Home": "https://x.example"}\n', 3, "https://x.example"),
    ('C4Context\n  Person(a, "A", $link="https://x.example")\n', 2, "https://x.example"),
    ("flowchart LR\n  a --> c[\"<a href='https://x.example'>x</a>\"]\n", 2, "https://x.example"),
    # Image shapes, quoted key or not, on one line or several.
    (
        'flowchart LR\n  a --> b\n  b@{ img: "https://x.example/i.png", label: "L" }\n',
        3,
        "https://x.example/i.png",
    ),
    ('flowchart LR\n  b@{ "img": "https://x.example/i.png", label: "L" }\n', 2, "https://x.example/i.png"),
    ('flowchart LR\n  b@{\n    label: "L"\n    img: "pic.png"\n  }\n', 4, "pic.png"),
    # HTML in a label: src with a padded value, srcset, and a tag split over two lines.
    ("flowchart LR\n  a --> c[\"<img src=' https://x.example/l.png'/> L\"]\n", 2, "https://x.example/l.png"),
    ("flowchart LR\n  a --> c[\"<img srcset='https://x.example/s.png'> L\"]\n", 2, "https://x.example/s.png"),
    ("flowchart LR\n  a --> c[\"<img\nsrc='https://x.example/t.png'> L\"]\n", 3, "https://x.example/t.png"),
    # srcset: every candidate is checked, data: first or not, quoted or not.
    (
        "flowchart LR\n  a[\"<img srcset='data:image/png;base64,AAAA 1x, "
        "https://x.example/i.png 2x'>\"] --> b\n",
        2,
        "https://x.example/i.png",
    ),
    ('flowchart LR\n  a["<img srcset=https://x.example/u.png>"] --> b\n', 2, "https://x.example/u.png"),
    # Each url( is checked on its own, so one after a data: URL is still caught.
    (
        "flowchart LR\n  a[\"<span style='background: url(data:image/png;base64,AAAA), "
        "url(https://x.example/b.png)'>x</span>\"] --> b\n",
        2,
        "https://x.example/b.png",
    ),
    # A JSON-escaped quote in a directive: the message shows the URL, not the backslash.
    (
        '%%{init: {"themeCSS": "@import \\"https://x.example/c.css\\";"}}%%\nflowchart LR\n  a --> b\n',
        1,
        "https://x.example/c.css",
    ),
    # CSS: themeCSS in a directive or front matter, and style= in a label.
    (
        '%%{init: {"themeCSS": ".node rect { fill: url(https://x.example/f.png) }"}}%%\n'
        "flowchart LR\n  a --> b\n",
        1,
        "https://x.example/f.png",
    ),
    (
        '---\nconfig:\n  themeCSS: "@import url(https://x.example/c.css);"\n---\nflowchart LR\n  a --> b\n',
        3,
        "https://x.example/c.css",
    ),
    (
        "flowchart LR\n  a[\"<span style='background:url(https://x.example/b.png)'>x</span>\"] --> b\n",
        2,
        "https://x.example/b.png",
    ),
]


@pytest.mark.parametrize(("source", "line", "url"), OUTSIDE)
def test_diagrams_cant_load_or_link_outside_the_deck(checker: Checker, source: str, line: int, url: str):
    assert error(checker, source) == (
        f"flow.mmd:{line}: a diagram can't load or link to anything outside the deck ({url}); "
        "use a data: URI for an image and a #anchor, such as #3 for slide 3, for a link"
    )


def test_a_diagram_too_long_for_mermaid_to_draw(checker: Checker):
    source = "flowchart LR\n" + "".join(f"  n{i} --> n{i + 1}\n" for i in range(3500))
    size = len(source)
    assert size > 50_000
    assert error(checker, source) == (
        f"flow.mmd: the diagram is {size:,} characters long, over Mermaid's limit of 50,000; "
        "split it into smaller diagrams"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # YAML errors count lines within the snippet Mermaid parsed, so the check finds the snippet.
        (
            "flowchart LR\n  a --> b\n  c@{ shape: [rect }\n",
            "3: missed comma between flow collection entries",
        ),
        (
            "flowchart LR\n  a --> b\n  c@{\n    shape: rect\n    label: [x\n  }\n",
            "6: unexpected end of the stream within a flow collection",
        ),
        (
            "---\ntitle: [x\n---\nflowchart LR\n  a --> b\n",
            "2: unexpected end of the stream within a flow collection",
        ),
        ("flowchart LR\n  a --> b\n  c@{ shape: nosuch }\n", "3: No such shape: nosuch."),
    ],
)
def test_yaml_and_shape_errors_name_the_line(checker: Checker, source: str, expected: str):
    assert error(checker, source) == f"flow.mmd:{expected}"


def fake_worker(monkeypatch: pytest.MonkeyPatch, code: str) -> None:
    """Stand in for the V8 worker with a small Python program, to test how Checker handles it."""
    monkeypatch.setattr(mermaid, "WORKER", [sys.executable, "-c", code])


READY = "import sys, time; print('{\"max_text_size\": 50000}', flush=True); "


def test_a_diagram_that_hangs_mermaid_stops_the_build(monkeypatch: pytest.MonkeyPatch):
    fake_worker(monkeypatch, READY + "sys.stdin.readline(); time.sleep(60)")
    monkeypatch.setattr(mermaid, "PARSE_TIMEOUT", 0.5)
    checker = Checker()
    with pytest.raises(DeckError, match=r"^flow\.mmd: Mermaid took over 0\.5s to check the diagram$"):
        checker.check(FLOW, "flowchart LR\n")
    assert checker._worker is None  # pyright: ignore[reportPrivateUsage]


def test_a_worker_that_never_starts(monkeypatch: pytest.MonkeyPatch):
    fake_worker(monkeypatch, "import time; time.sleep(60)")
    monkeypatch.setattr(mermaid, "START_TIMEOUT", 0.5)
    with Checker() as checker, pytest.raises(DeckError, match=r"took over 0\.5s to load Mermaid$"):
        checker.check(FLOW, "flowchart LR\n")


def test_a_worker_that_dies_is_a_bug_not_a_deck_error(monkeypatch: pytest.MonkeyPatch):
    fake_worker(monkeypatch, READY + "sys.stdin.readline()")
    with Checker() as checker, pytest.raises(RuntimeError, match="stopped unexpectedly"):
        checker.check(FLOW, "flowchart LR\n")


def test_closing_stops_the_worker(checker: Checker):
    fresh = Checker()
    fresh.check(FLOW, "flowchart LR\n  a --> b\n")
    worker = fresh._worker  # pyright: ignore[reportPrivateUsage]
    assert worker is not None and worker.poll() is None
    fresh.close()
    assert worker.poll() is not None


MIDNIGHT = {"bg": "#0b0f16", "line": "#23324a", "text": "#e8eef6", "muted": "#93a4bd", "accent": "#5eead4"}


def test_config_uses_the_theme_colors():
    config = mermaid.config({**MIDNIGHT, "font": "Inter, sans-serif"})
    assert config["theme"] == "base"
    variables = config["themeVariables"]
    assert variables["background"] == "#0b0f16"
    assert variables["primaryColor"] == "#23324a"
    assert variables["primaryBorderColor"] == "#5eead4"
    assert variables["primaryTextColor"] == variables["textColor"] == "#e8eef6"
    assert variables["lineColor"] == "#93a4bd"
    assert variables["fontFamily"] == "Inter, sans-serif"
    assert variables["darkMode"] is True


@pytest.mark.parametrize(
    ("bg", "dark"), [("#f7f5f0", False), ("#fff", False), ("#123", True), ("black", None)]
)
def test_dark_mode_follows_the_background(bg: str, dark: bool | None):
    variables = mermaid.config({**MIDNIGHT, "bg": bg, "font": "x"})["themeVariables"]
    assert variables.get("darkMode") is dark


def test_vendored_mermaid_matches_its_manifest():
    manifest = json.loads((mermaid.VENDOR / "manifest.json").read_text(encoding="utf-8"))
    script = (mermaid.VENDOR / "mermaid.min.js").read_bytes()
    assert hashlib.sha256(script).hexdigest() == manifest["sha256"]


def test_notices_list_the_bundled_packages():
    notices = (mermaid.VENDOR / "THIRD_PARTY_NOTICES").read_text(encoding="utf-8")
    headings = re.findall(r"^-{72}\n(\S+) (\S+)\nLicense: ", notices, re.MULTILINE)
    names = {name for name, _ in headings}
    assert len(headings) >= 100
    assert {"d3", "dompurify", "elkjs", "cytoscape", "langium", "chevrotain"} <= names
    assert ("dompurify", "3.4.12") in headings  # the version the bundle was built with


def test_page_script_carries_the_license_notices():
    script = mermaid.page_script()
    comment_end = script.index("*/")
    comment = script[:comment_end]
    assert comment.startswith("/*! Mermaid 12.0.0\n")
    assert "MIT License" in comment
    assert "Eclipse Public License" in comment
    assert "https://github.com/kieler/elkjs" in comment
    assert script[comment_end:].startswith("*/\n")
    assert not re.search(r"<script|</script", script, re.IGNORECASE)


def test_page_script_escapes_script_tags_and_keeps_its_comment_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "manifest.json").write_text('{"version": "1.0.0"}')
    (tmp_path / "LICENSE").write_text("MIT")
    (tmp_path / "THIRD_PARTY_NOTICES").write_text("a */ in a notice")
    (tmp_path / "mermaid.min.js").write_text('var a = "</script>", b = /<SCRIPT/;')
    monkeypatch.setattr(mermaid, "VENDOR", tmp_path)
    assert mermaid.page_script() == (
        '/*! Mermaid 1.0.0\n\nMIT\n\na * / in a notice\n*/\nvar a = "\\x3C/script>", b = /\\x3CSCRIPT/;'
    )
