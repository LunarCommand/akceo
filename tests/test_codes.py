import io
import json
import re
from pathlib import Path

import pytest
from PIL import Image

from akceo import cli, report, themes
from akceo.cli import main
from akceo.errors import CODES, DeckError

ROOT = Path(__file__).parents[1]
FULL_THEME = ":root {\n" + "".join(f"  --{t}: #000;\n" for t in themes.TOKENS) + "}\n"
LONG = "flowchart LR\n" + "".join(f"  n{i} --> n{i + 1}\n" for i in range(3500))
IMAGE = "---\nlayout: image\nimage: a.png\n"
DIAGRAM = "---\nlayout: image\nimage: flow.mmd\n"
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"/>'
# Codes check can't raise, tested below, and the one test_mermaid.py tests with a stand-in worker.
NOT_FROM_CHECK = {"file-unwritable", "init-not-folder", "init-link-outside", "init-broken-link"}
TESTED_ELSEWHERE = {"diagram-timeout"}


def image(fmt: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 6), "red").save(buf, format=fmt)
    return buf.getvalue()


# (code, files with deck.md among them, the error's text)
CASES: list[tuple[str, dict[str, str | bytes], str]] = [
    ("file-not-found", {}, "deck.md: no such file"),
    ("file-not-found", {"deck.md": IMAGE}, "deck.md:2: slide 1: image not found: a.png"),
    ("file-not-found", {"deck.md": "icon: a.svg\n---\n## One\n"}, "deck.md:1: icon: image not found: a.svg"),
    ("file-not-found", {"deck.md": DIAGRAM}, "deck.md:2: slide 1: image not found: flow.mmd"),
    (
        "file-not-found",
        {"deck.md": "theme: gone.css\n---\n## One\n"},
        "deck.md:1: theme file not found: gone.css",
    ),
    (
        "file-not-utf8",
        {"deck.md": b"---\n## caf\xe9\n"},
        "deck.md:2: not valid UTF-8 text; save the deck as UTF-8",
    ),
    (
        "deck-control-character",
        {"deck.md": "---\n## a\x07b\n"},
        "deck.md:2: a control character (U+0007) can't be in a deck",
    ),
    (
        "deck-no-slides",
        {"deck.md": "title: Talk\n"},
        "deck.md: the deck has no slides; start each slide after a --- line",
    ),
    (
        "config-not-key-value",
        {"deck.md": "title: Talk\nhello\n---\n## One\n"},
        "deck.md:1: the config block may only hold key: value lines; start each slide after ---",
    ),
    (
        "key-unknown",
        {"deck.md": "colour: red\n---\n## One\n"},
        "deck.md:1: unknown config key 'colour' (expected one of: title, description, url, icon, theme, "
        "images, image-frame)",
    ),
    ("key-unknown", {"deck.md": "---\nfoo: bar\n\n## One\n"}, "deck.md:2: slide 1: unknown key 'foo'"),
    (
        "layout-unknown",
        {"deck.md": "---\nlayout: grid\n\n## One\n"},
        "deck.md:2: slide 1: unknown layout 'grid' (expected one of: title, bullets, split, steps, table, "
        "image)",
    ),
    (
        "key-wrong-layout",
        {"deck.md": "---\nmeta: x\n\n## One\n"},
        "deck.md:2: slide 1: 'meta' only applies to the title layout",
    ),
    (
        "value-not-yes-or-no",
        {"deck.md": "image-frame: maybe\n---\n## One\n"},
        "deck.md:1: 'image-frame' must be yes or no, not 'maybe'",
    ),
    (
        "value-not-yes-or-no",
        {"deck.md": IMAGE + "image-frame: maybe\n"},
        "deck.md:4: slide 1: 'image-frame' must be yes or no, not 'maybe'",
    ),
    (
        "value-not-pixels",
        {"deck.md": IMAGE + "image-max: big\n"},
        "deck.md:4: slide 1: 'image-max' must be a positive whole number of pixels, at most nine digits 0-9, "
        "not 'big'",
    ),
    (
        "crop-invalid",
        {"deck.md": IMAGE + "image-crop: 1, 2\n"},
        "deck.md:4: slide 1: 'image-crop' must be four whole numbers of pixels, left, top, right and bottom, "
        "each at most nine digits 0-9, such as 120, 80, 920, 580, not '1, 2'",
    ),
    (
        "crop-empty",
        {"deck.md": IMAGE + "image-crop: 10, 10, 5, 20\n"},
        "deck.md:4: slide 1: 'image-crop' 10, 10, 5, 20 is empty: right must be past left, and bottom "
        "below top",
    ),
    (
        "crop-past-edge",
        {"deck.md": IMAGE + "image-crop: 0, 0, 100, 100\n", "a.png": image("PNG")},
        "deck.md:2: slide 1: the crop 0, 0, 100, 100 goes past the edge of a.png, which is 8 by 6 pixels",
    ),
    (
        "image-option-unsupported",
        {"deck.md": "---\nlayout: image\nimage: a.svg\nimage-crop: 0, 0, 1, 1\n"},
        "deck.md:4: slide 1: 'image-crop' only works on PNG, JPEG and WebP images, not a.svg",
    ),
    (
        "image-option-unsupported",
        {"deck.md": DIAGRAM, "flow.mmd": 'flowchart LR\n  b@{ img: "a.svg#crop=0,0,1,1" }\n', "a.svg": SVG},
        "deck.md:2: slide 1: flow.mmd:2: can't crop an SVG image: a.svg",
    ),
    (
        "image-option-unsupported",
        {"deck.md": DIAGRAM, "flow.mmd": 'flowchart LR\n  b@{ img: "a.svg#max=10" }\n', "a.svg": SVG},
        "deck.md:2: slide 1: flow.mmd:2: max= can't shrink an SVG image, so set the node's w and h "
        "instead: a.svg",
    ),
    (
        "url-invalid",
        {"deck.md": "url: akceo.ai\n---\n## One\n"},
        "deck.md:1: 'url' must be the page's full address, starting https:// or http://, not 'akceo.ai'",
    ),
    (
        "style-url",
        {"deck.md": "---\nstyle-h2: background: url(x.png)\n\n## One\n"},
        "deck.md:2: slide 1: 'style-h2' can't reference files or URLs (url() or image-set())",
    ),
    (
        "block-not-in-layout",
        {"deck.md": "---\nlayout: title\n\n## One\n"},
        "deck.md:4: slide 1: a ## heading isn't used by the title layout, which takes a # heading",
    ),
    (
        "block-repeated",
        {"deck.md": "---\n## One\n## Two\n"},
        "deck.md:3: slide 1: the bullets layout takes only one ## heading",
    ),
    (
        "block-missing",
        {"deck.md": "---\nlayout: steps\n\n## One\n"},
        "deck.md:2: slide 1: the steps layout needs a 1. list",
    ),
    (
        "link-split",
        {"deck.md": "---\n## One\n\nSee [docs](https://x.example/\\\na) here\n"},
        "deck.md:4: slide 1: a link's URL can't continue onto the next line ('https://x.example/\\a')",
    ),
    (
        "link-past-last-slide",
        {"deck.md": "---\n## One\n\nGo to [two](#2)\n"},
        "deck.md:4: slide 1: the link to #2 goes past the last slide, 1",
    ),
    (
        "link-target-invalid",
        {"deck.md": "---\n## One\n\nGet [it](ftp://x.example)\n"},
        "deck.md:4: slide 1: can't link to 'ftp://x.example'; a link goes to an https:, http: or mailto: "
        "address, or to a slide as #N",
    ),
    (
        "image-format-unsupported",
        {"deck.md": "---\nlayout: image\nimage: a.gif\n", "a.gif": image("GIF")},
        "deck.md:2: slide 1: unsupported image format GIF: a.gif (use PNG, JPEG, WebP, SVG or .mmd)",
    ),
    (
        "image-damaged",
        {"deck.md": IMAGE, "a.png": b"not an image"},
        "deck.md:2: slide 1: not a readable image: a.png",
    ),
    (
        "diagram-syntax",
        {"deck.md": DIAGRAM, "flow.mmd": "flowchrt TD\n"},
        "deck.md:2: slide 1: flow.mmd:1: Mermaid doesn't recognise the diagram type; start with one such as "
        "flowchart",
    ),
    (
        "diagram-syntax",
        {"deck.md": DIAGRAM, "flow.mmd": "flowchart LR\n  a -->\n"},
        "deck.md:2: slide 1: flow.mmd:2: Parse error: Expecting 'AMP', 'COLON', 'PIPE', 'TESTSTR', 'DOWN', "
        "'DEFAULT', 'NUM', 'COMMA', 'NODE_STRING', 'BRKT', 'MINUS', 'MULT', 'UNICODE_TEXT', got 'EOF'",
    ),
    (
        "diagram-syntax",
        {"deck.md": DIAGRAM, "flow.mmd": "flowchart LR\n  a@{ img: shot.png, label: Shot,\n      w: 40 }\n"},
        "deck.md:2: slide 1: flow.mmd:2: bad indentation of a mapping entry",
    ),
    (
        "diagram-too-long",
        {"deck.md": DIAGRAM, "flow.mmd": LONG},
        f"deck.md:2: slide 1: flow.mmd: the diagram is {len(LONG):,} characters long, over Mermaid's "
        "limit of 50,000; split it into smaller diagrams",
    ),
    (
        "diagram-loads-outside",
        {"deck.md": DIAGRAM, "flow.mmd": 'flowchart LR\n  a@{ img: "https://x.example/a.png" }\n'},
        "deck.md:2: slide 1: flow.mmd:2: a diagram can't load or link to anything outside the deck "
        "(https://x.example/a.png); give an image as a file path in img: or a data: URI, and a link as a "
        "#anchor, such as #3 for slide 3",
    ),
    (
        "diagram-loads-outside",
        {"deck.md": DIAGRAM, "flow.mmd": "flowchart LR\n  b@{ img: &p https://x.example/a.png }\n"},
        "deck.md:2: slide 1: flow.mmd: node b: a diagram can't load or link to anything outside the deck "
        "(https://x.example/a.png); give an image as a file path in img: or a data: URI, and a link as a "
        "#anchor, such as #3 for slide 3",
    ),
    (
        "img-unlocated",
        {"deck.md": DIAGRAM, "flow.mmd": "flowchart LR\n  b@{ img: &p shot.png }\n"},
        "deck.md:2: slide 1: flow.mmd: akceo can't tell where node b's img: shot.png is written, to put the "
        'file in; write it on one line, such as img: "shot.png"',
    ),
    (
        "img-no-path",
        {"deck.md": DIAGRAM, "flow.mmd": 'flowchart LR\n  b@{ img: "#max=10" }\n'},
        "deck.md:2: slide 1: flow.mmd:2: an img: needs a file path before its #, such as "
        'img: "shot.png#max=10"',
    ),
    (
        "img-unquoted",
        {"deck.md": DIAGRAM, "flow.mmd": "flowchart LR\n  b@{ img: shot.png#max=10 }\n"},
        "deck.md:2: slide 1: flow.mmd:2: quote an img: path that has options, such as "
        'img: "shot.png#crop=120,80,920,580"',
    ),
    (
        "img-option-invalid",
        {"deck.md": DIAGRAM, "flow.mmd": 'flowchart LR\n  b@{ img: "shot.png#zoom=2" }\n'},
        "deck.md:2: slide 1: flow.mmd:2: an img: path takes crop= and max= after its #, joined with &, not "
        "'zoom=2' (a file name can't contain #)",
    ),
    (
        "img-option-invalid",
        {"deck.md": DIAGRAM, "flow.mmd": 'flowchart LR\n  b@{ img: "a.png#max=1&max=2" }\n'},
        "deck.md:2: slide 1: flow.mmd:2: an img: path takes max= only once",
    ),
    (
        "theme-unknown",
        {"deck.md": "theme: neon\n---\n## One\n"},
        "deck.md:1: unknown theme 'neon' (built-in themes: midnight, paper)",
    ),
    (
        "theme-closes-style",
        {"deck.md": "theme: evil.css\n---\n## One\n", "evil.css": FULL_THEME + "/* </style> */\n"},
        "deck.md:1: theme evil.css contains '</style', which would end the page's style block",
    ),
    (
        "theme-missing-tokens",
        {
            "deck.md": "theme: brand.css\n---\n## One\n",
            "brand.css": FULL_THEME.replace("  --bg: #000;\n", ""),
        },
        "deck.md:1: theme brand.css doesn't set: --bg",
    ),
    (
        "theme-missing-tokens",
        {
            "deck.md": "theme: brand.css\n---\n## One\n\nSee [docs](https://x.example)\n",
            "brand.css": FULL_THEME,
        },
        "deck.md:1: theme brand.css doesn't set --link, --link-hover, --link-underline, which the deck's "
        "links need",
    ),
]


@pytest.mark.parametrize(("code", "files", "text"), CASES, ids=[f"{c[0]}-{i}" for i, c in enumerate(CASES)])
def test_each_error_has_its_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: str, files: dict[str, str | bytes], text: str
):
    monkeypatch.chdir(tmp_path)
    for name, content in files.items():
        if isinstance(content, bytes):
            Path(name).write_bytes(content)
        else:
            Path(name).write_text(content, encoding="utf-8")
    [error] = report.check(Path("deck.md"))["errors"]
    assert (error["code"], error["text"]) == (code, text)


def test_a_deck_that_cant_be_read_is_unreadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    deck = tmp_path / "deck.md"
    deck.write_text("---\n## One\n")

    def denied(self: Path, *args: object, **kwargs: object) -> str:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "open", denied)
    [error] = report.check(deck)["errors"]
    assert (error["code"], error["text"]) == ("file-unreadable", f"{deck}: Permission denied")


@pytest.mark.parametrize(
    ("raised", "code", "text"),
    [
        (
            PermissionError(13, "Permission denied"),
            "file-unreadable",
            "can't read image a.png: Permission denied",
        ),
        (
            ValueError("image has wrong mode"),
            "image-damaged",
            "can't process image a.png: image has wrong mode",
        ),
    ],
    ids=["unreadable", "unprocessable"],
)
def test_an_image_pillow_cant_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raised: Exception, code: str, text: str
):
    monkeypatch.chdir(tmp_path)
    Path("deck.md").write_text(IMAGE)
    Path("a.png").write_bytes(image("PNG"))

    def fail(*args: object, **kwargs: object) -> None:
        raise raised

    monkeypatch.setattr(Image, "open", fail)
    [error] = report.check(Path("deck.md"))["errors"]
    assert (error["code"], error["text"]) == (code, f"deck.md:2: slide 1: {text}")


def test_an_image_over_pillows_size_limit_is_too_large(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    Path("deck.md").write_text(IMAGE)
    Path("a.png").write_bytes(image("PNG"))
    # Pillow refuses an image over twice this many pixels; the test image has 48.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 20)
    [error] = report.check(Path("deck.md"))["errors"]
    assert error["code"] == "image-too-large"
    assert error["text"].startswith(
        "deck.md:2: slide 1: can't process image a.png: Image size (48 pixels) exceeds"
    )


def test_a_theme_given_on_the_command_line_has_no_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    Path("deck.md").write_text("theme: midnight\n---\n## One\n\nSee [docs](https://x.example)\n")
    Path("brand.css").write_text(FULL_THEME)
    [error] = report.check(Path("deck.md"), "brand.css")["errors"]
    assert error["text"] == (
        "deck.md: theme brand.css doesn't set --link, --link-hover, --link-underline, which the deck's "
        "links need"
    )


def test_init_and_write_errors_have_their_codes(tmp_path: Path):
    outside = tmp_path / "outside.md"
    outside.write_text("")
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "AGENTS.md").symlink_to(outside)
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "AGENTS.md").symlink_to(broken / "gone.md")
    raised: dict[str, str] = {}
    for run in (
        lambda: cli._write(tmp_path / "no" / "deck.html", ""),  # pyright: ignore[reportPrivateUsage]
        lambda: cli._init(tmp_path / "nope", dry_run=False),  # pyright: ignore[reportPrivateUsage]
        lambda: cli._init(linked, dry_run=False),  # pyright: ignore[reportPrivateUsage]
        lambda: cli._init(broken, dry_run=False),  # pyright: ignore[reportPrivateUsage]
    ):
        with pytest.raises(DeckError) as e:
            run()
        raised[e.value.code] = str(e.value)
    assert set(raised) == NOT_FROM_CHECK
    assert raised["file-unwritable"] == f"{tmp_path / 'no' / 'deck.html'}: No such file or directory"
    assert raised["init-not-folder"] == f"{tmp_path / 'nope'}: not a folder"


def test_every_code_is_tested():
    tested = (
        {code for code, _, _ in CASES}
        | {"file-unreadable", "image-too-large"}
        | NOT_FROM_CHECK
        | TESTED_ELSEWHERE
    )
    assert sorted(tested) == sorted(CODES)


def test_the_docs_list_every_code():
    syntax = (ROOT / "docs" / "syntax.md").read_text(encoding="utf-8")
    section = syntax.partition("\n## Error codes\n")[2].partition("\n## ")[0]
    assert re.findall(r"^\| `([a-z0-9-]+)` \|", section, re.MULTILINE) == list(CODES)


def test_the_report_places_a_diagram_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    Path("deck.md").write_text("---\n## One\n---\nlayout: image\nimage: flow.mmd\n")
    Path("flow.mmd").write_text("flowchrt TD\n")
    message = "Mermaid doesn't recognise the diagram type; start with one such as flowchart"
    assert report.check(Path("deck.md")) == {
        "ok": False,
        "deck": "deck.md",
        "slides": None,
        "errors": [
            {
                "code": "diagram-syntax",
                "message": message,
                "file": "deck.md",
                "line": 4,
                "slide": 2,
                "in": {"file": "flow.mmd", "line": 1},
                "text": f"deck.md:4: slide 2: flow.mmd:1: {message}",
            }
        ],
    }


def test_the_report_leaves_out_what_an_error_doesnt_have(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    Path("deck.md").write_text("title: Talk\n")
    [error] = report.check(Path("deck.md"))["errors"]
    assert (error["file"], error["line"], error["slide"], error["in"]) == ("deck.md", None, None, None)
    Path("deck.md").write_text("---\n## One\n")
    [error] = report.check(Path("deck.md"), "neon")["errors"]
    assert (error["file"], error["line"], error["slide"], error["in"]) == (None, None, None, None)


def test_check_json_prints_the_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    Path("deck.md").write_text("---\n## One\n---\n## Two\n")
    assert main(["check", "--json", "deck.md"]) == 0
    out, err = capsys.readouterr()
    assert (json.loads(out), err) == ({"ok": True, "deck": "deck.md", "slides": 2, "errors": []}, "")

    Path("deck.md").write_text("---\nfoo: bar\n")
    assert main(["check", "--json", "deck.md"]) == 1
    out, err = capsys.readouterr()
    assert json.loads(out)["errors"][0]["text"] == "deck.md:2: slide 1: unknown key 'foo'"
    assert err == ""
