import json
import re
from pathlib import Path

import pytest

from akceo import lint, parse, report
from akceo.cli import main
from akceo.errors import WARNING_CODES

ROOT = Path(__file__).parents[1]
WORDS = " ".join(["word"] * 100)
PLACE = "at the top of the slide, in lowercase, before the blank line"

# (code, deck, the warning's text)
CASES: list[tuple[str, str, str]] = [
    (
        "slide-dense",
        f"---\n## One\n\n{WORDS}\n",
        "deck.md:2: slide 1: warning: 101 words, which may not fit; look at the built page, or split the "
        "slide",
    ),
    (
        # A hard line break separates two words: without it, these 101 words would count as 100.
        "slide-dense",
        f"---\n## One\n\n{' '.join(['word'] * 98)} a\\\nb\n",
        "deck.md:2: slide 1: warning: 101 words, which may not fit; look at the built page, or split the "
        "slide",
    ),
    (
        "image-placeholder",
        "---\nlayout: split\n\n## One\n",
        "deck.md:2: slide 1: warning: no image: yet, so the slide shows a dashed box where it goes",
    ),
    (
        "image-placeholder",
        "---\nlayout: image\n",
        "deck.md:2: slide 1: warning: no image: yet, so the slide shows a dashed box where it goes",
    ),
    (
        "markdown-code-fence",
        "---\n## One\n\n```python\nprint(1)\n```\n",
        "deck.md:4: slide 1: warning: ``` shows as text; akceo has no code blocks yet",
    ),
    (
        "markdown-code-fence",
        "---\n## One\n\n~~~\nx\n~~~\n",
        "deck.md:4: slide 1: warning: ~~~ shows as text; akceo has no code blocks yet",
    ),
    (
        "markdown-nested-list",
        "---\n## One\n\n- item\n  - sub\n",
        "deck.md:5: slide 1: warning: an indented list item joins the item above it as text; lists are one "
        "level deep",
    ),
    (
        "markdown-nested-list",
        "---\nlayout: steps\n\n## One\n\n1. step\n   1. sub\n",
        "deck.md:7: slide 1: warning: an indented list item joins the item above it as text; lists are one "
        "level deep",
    ),
    (
        "markdown-bullet",
        "---\n## One\n\n* a\n* b\n",
        "deck.md:4: slide 1: warning: a list item that starts with * shows as text; use - instead",
    ),
    (
        "markdown-bullet",
        "---\n## One\n\n+ a\n",
        "deck.md:4: slide 1: warning: a list item that starts with + shows as text; use - instead",
    ),
    (
        "markdown-heading",
        "---\n## One\n\n#### Deep\n",
        "deck.md:4: slide 1: warning: a #### heading shows as text; use ## for the slide's heading",
    ),
    (
        "key-in-text",
        "---\n## One\n\nimage: arch.mmd\n",
        f"deck.md:4: slide 1: warning: 'image:' shows as text; a key goes {PLACE}",
    ),
    (
        # Still at the top: every line above it looks like a key, and an author note doesn't count.
        "key-in-text",
        "---\nNote: x\n// todo\nKicker: y\n\n## One\n",
        f"deck.md:4: slide 1: warning: 'Kicker:' shows as text; a key goes {PLACE}",
    ),
    (
        "key-in-text",
        "---\nKicker: Intro\n\n## One\n",
        f"deck.md:2: slide 1: warning: 'Kicker:' shows as text; a key goes {PLACE}",
    ),
]


def warnings(text: str) -> list[str]:
    return [str(w) for w in lint.find(parse.parse(text, Path("deck.md")))]


@pytest.mark.parametrize(("code", "deck", "text"), CASES, ids=[f"{c[0]}-{i}" for i, c in enumerate(CASES)])
def test_each_warning_has_its_code(code: str, deck: str, text: str):
    [warning] = lint.find(parse.parse(deck, Path("deck.md")))
    assert (warning.code, str(warning)) == (code, text)


@pytest.mark.parametrize(
    "deck",
    [
        # Exactly the limit: 1 heading word and 99 more.
        f"---\n## One\n\n{' '.join(['word'] * 99)}\n",
        "---\nlayout: split\nimage: a.png\n\n## One\n",
        "---\nlayout: split\nimage: a.png\n\n## One\n\n*A note in italics*\n",
        "---\n## One\n\n**Bold** to start a line\n",
        "---\n## One\n\n// * an author note, never shown\n",
        "---\n## One\n\nNote: not a key\n",
        "---\n## One\n\nKicker: below the top, so ordinary text\n",
        "---\nlayout: image\nimage: a.png\n\n## One\n\nImage: a cat on a keyboard\n",
        "---\nlayout: split\nimage: a.png\n\n## One\n\n### Phase\n",
        "---\n## One\n\n- item\n  continued, not nested\n",
    ],
    ids=[
        "100-words",
        "has-image",
        "italic-note",
        "bold",
        "author-note",
        "not-a-key",
        "capital-below-top",
        "caption",
        "three-hashes",
        "continuation",
    ],
)
def test_what_isnt_a_warning(deck: str):
    assert warnings(deck) == []


def test_a_fenced_blocks_lines_are_code():
    assert warnings("---\n## One\n\n```\n  - sub\n* a\n#### x\nimage: y\n```\n") == [
        "deck.md:4: slide 1: warning: ``` shows as text; akceo has no code blocks yet"
    ]


def test_the_closing_fence_ends_the_code():
    assert warnings("---\n## One\n\n```\nx\n```\n* a\n") == [
        "deck.md:4: slide 1: warning: ``` shows as text; akceo has no code blocks yet",
        "deck.md:7: slide 1: warning: a list item that starts with * shows as text; use - instead",
    ]


@pytest.mark.parametrize(
    "inner",
    ["```", "~~~", "```python"],
    ids=["shorter-run", "other-character", "text-after"],
)
def test_only_a_matching_fence_closes_the_code(inner: str):
    opening = "````" if inner == "```" else "```"
    deck = f"---\n## One\n\n{opening}\n{inner}\n* a\n{opening}\n* b\n"
    assert warnings(deck)[1] == (
        "deck.md:8: slide 1: warning: a list item that starts with * shows as text; use - instead"
    )


def test_each_code_is_given_once_a_slide_at_its_first_line_and_in_line_order():
    deck = "---\n## One\n\n#### a\n* b\n* c\n#### d\n---\n## Two\n\n* e\n"
    assert warnings(deck) == [
        "deck.md:4: slide 1: warning: a #### heading shows as text; use ## for the slide's heading",
        "deck.md:5: slide 1: warning: a list item that starts with * shows as text; use - instead",
        "deck.md:11: slide 2: warning: a list item that starts with * shows as text; use - instead",
    ]


def test_every_warning_code_is_tested():
    assert sorted({code for code, _, _ in CASES}) == sorted(WARNING_CODES)


def test_the_docs_list_every_warning_code():
    syntax = (ROOT / "docs" / "syntax.md").read_text(encoding="utf-8")
    section = syntax.partition("\n## Warning codes\n")[2].partition("\n## ")[0]
    assert re.findall(r"^\| `([a-z0-9-]+)` \|", section, re.MULTILINE) == list(WARNING_CODES)


def test_the_demo_has_no_warnings():
    deck = ROOT / "examples" / "demo" / "deck.md"
    assert lint.find(parse.load(deck)) == []


def test_check_and_build_print_warnings_and_still_succeed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    Path("deck.md").write_text("---\n## One\n\n* a\n---\nlayout: split\n\n## Two\n")
    expected = (
        "akceo: deck.md:4: slide 1: warning: a list item that starts with * shows as text; use - instead\n"
        "akceo: deck.md:6: slide 2: warning: no image: yet, so the slide shows a dashed box where it goes\n"
    )
    assert main(["check", "deck.md"]) == 0
    assert capsys.readouterr() == ("ok: deck.md (2 slides, 2 warnings)\n", expected)
    assert main(["build", "deck.md"]) == 0
    out, err = capsys.readouterr()
    assert re.fullmatch(r"wrote deck\.html \(\d+ KB, 2 slides, 2 warnings\)\n", out)
    assert err == expected


def test_one_warning_is_counted_as_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    Path("deck.md").write_text("---\nlayout: image\n")
    assert main(["check", "deck.md"]) == 0
    assert capsys.readouterr().out == "ok: deck.md (1 slide, 1 warning)\n"


def test_the_report_lists_warnings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    Path("deck.md").write_text("---\n## One\n\n#### Deep\n")
    assert report.check(Path("deck.md"))["warnings"] == [
        {
            "code": "markdown-heading",
            "message": "a #### heading shows as text; use ## for the slide's heading",
            "file": "deck.md",
            "line": 4,
            "slide": 1,
            "in": None,
            "text": "deck.md:4: slide 1: warning: a #### heading shows as text; use ## for the slide's "
            "heading",
        }
    ]


def test_a_deck_with_an_error_gets_no_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    Path("deck.md").write_text("---\n## One\n\n* a\n---\nlayout: image\nimage: gone.png\n")
    result = report.check(Path("deck.md"))
    assert (result["ok"], result["warnings"]) == (False, [])
    assert main(["check", "--json", "deck.md"]) == 1
    assert json.loads(capsys.readouterr().out)["warnings"] == []
    assert main(["check", "deck.md"]) == 1
    assert "warning" not in capsys.readouterr().err


@pytest.mark.parametrize(
    ("deck", "code", "text"),
    [
        (
            "---\n## One\n\nText\n\n* a\n* b\n",
            "block-repeated",
            "deck.md:6: slide 1: the bullets layout takes only one paragraph. A list item that starts with * "
            "shows as text; use - instead",
        ),
        (
            "---\nlayout: title\nKicker: Intro\n\n# Talk\n",
            "block-not-in-layout",
            "deck.md:3: slide 1: a paragraph isn't used by the title layout, which takes a # heading. "
            f"'Kicker:' shows as text; a key goes {PLACE}",
        ),
        # The list is inside the fence, so the fence is the reason.
        (
            "---\nlayout: steps\n\n## One\n\n1. step\n\n```\n- a\n```\n",
            "block-not-in-layout",
            "deck.md:9: slide 1: a - list isn't used by the steps layout, which takes a ## heading, a "
            "paragraph and a 1. list. ``` shows as text; akceo has no code blocks yet",
        ),
    ],
    ids=["bullet", "capital-key", "fence"],
)
def test_an_error_a_stray_line_causes_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, deck: str, code: str, text: str
):
    monkeypatch.chdir(tmp_path)
    Path("deck.md").write_text(deck)
    [error] = report.check(Path("deck.md"))["errors"]
    assert (error["code"], error["text"]) == (code, text)
