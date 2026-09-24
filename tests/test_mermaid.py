import hashlib
import json
import re
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
        'flowchart LR\n  %% click a href "https://example.com"\n  a --> b\n',
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


@pytest.mark.parametrize(
    ("source", "line", "url"),
    [
        # The http(s) URL also needs the URL stand-in; without it the check crashed.
        (
            'flowchart LR\n  a --> b\n  click a href "https://example.com/docs"\n',
            3,
            "https://example.com/docs",
        ),
        ('flowchart LR\n  a --> b\n  click a "https://example.com" "tip" _blank\n', 3, "https://example.com"),
        (
            'flowchart LR\n  a --> b\n  b@{ img: "https://example.com/x.png", label: "L" }\n',
            3,
            "https://example.com/x.png",
        ),
        ('flowchart LR\n  b@{\n    label: "L"\n    img: "pic.png"\n  }\n', 4, "pic.png"),
        (
            "flowchart LR\n  a --> c[\"<img src='https://example.com/l.png'/> L\"]\n",
            2,
            "https://example.com/l.png",
        ),
        ("flowchart LR\n  a --> c[\"<a href='https://x.com'>x</a>\"]\n", 2, "https://x.com"),
    ],
)
def test_diagrams_cant_load_or_link_outside_the_deck(checker: Checker, source: str, line: int, url: str):
    assert error(checker, source) == (
        f"flow.mmd:{line}: a diagram can't load or link to anything outside the deck ({url}); "
        "use a data: URI for an image and a #anchor, such as #3 for slide 3, for a link"
    )


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
