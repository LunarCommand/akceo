import re
import shutil
from pathlib import Path

import pytest
from PIL import Image

from akceo.cli import main

ROOT = Path(__file__).parents[1]
DEMO = ROOT / "examples" / "demo"
EXTERNAL_REF = re.compile(r"""(src|href)=["']?(https?:|//|\.{0,2}/)|<link|@import|url\(""")
# The vendored Mermaid holds url(#marker) references inside its SVGs and CSS keywords such as
# @import as strings, so it gets a narrower check of its own: nothing that would load from outside.
MERMAID_SCRIPT = re.compile(r"<script>\n/\*! Mermaid .*?</script>\n", re.DOTALL)
OUTSIDE_LOAD = re.compile(r"""(src|href)=["']?(https?:|//)|(url\(|@import\s*(url\()?)["']?(https?:|//)""")


def test_builds_the_demo_deck_self_contained(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    out = tmp_path / "demo.html"
    assert main(["build", str(DEMO / "deck.md"), "-o", str(out)]) == 0
    assert re.fullmatch(rf"wrote {re.escape(str(out))} \(\d+ KB, 8 slides\)\n", capsys.readouterr().out)

    page = out.read_text()
    assert page.count('<section class="slide') == 8
    assert "__SLIDES__" not in page
    assert "data:image/svg+xml;base64," in page
    assert page.count('<div class="diagram bare"') == 1
    assert len(MERMAID_SCRIPT.findall(page)) == 1
    assert not EXTERNAL_REF.search(MERMAID_SCRIPT.sub("", page))
    assert not OUTSIDE_LOAD.search(page)
    assert "Author note" not in page


def test_default_output_sits_next_to_the_deck(tmp_path: Path):
    shutil.copytree(DEMO, tmp_path / "demo")
    assert main(["build", str(tmp_path / "demo" / "deck.md")]) == 0
    assert (tmp_path / "demo" / "deck.html").is_file()


def test_theme_flag_overrides_the_deck(tmp_path: Path):
    out = tmp_path / "out.html"
    assert main(["build", str(DEMO / "deck.md"), "-o", str(out), "--theme", "paper"]) == 0
    assert "--bg: #f7f5f0;" in out.read_text()


def test_deck_paths_resolve_against_the_deck_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "talk" / "img").mkdir(parents=True)
    Image.new("RGB", (20, 20)).save(tmp_path / "talk" / "img" / "fig.png")
    shutil.copy(ROOT / "src" / "akceo" / "themes" / "paper.css", tmp_path / "talk" / "brand.css")
    (tmp_path / "talk" / "deck.md").write_text(
        "theme: brand.css\nimages: img\n---\nlayout: split\nimage: fig.png\n\n## Figure\n"
    )
    monkeypatch.chdir(tmp_path)
    assert main(["build", "talk/deck.md"]) == 0
    page = (tmp_path / "talk" / "deck.html").read_text()
    assert "data:image/png;base64," in page
    assert "--bg: #f7f5f0;" in page


def test_image_frame_setting_reaches_the_page(tmp_path: Path):
    Image.new("RGB", (20, 20)).save(tmp_path / "fig.png")
    (tmp_path / "deck.md").write_text(
        "image-frame: no\n---\nlayout: image\nimage: fig.png\n"
        "---\nlayout: image\nimage-frame: yes\nimage: fig.png\n"
    )
    assert main(["build", str(tmp_path / "deck.md")]) == 0
    page = (tmp_path / "deck.html").read_text()
    assert page.count('<img class="bare" src="data:image/png') == 1
    assert page.count('<img src="data:image/png') == 1
    assert "/*! Mermaid" not in page and "mermaid-theme" not in page


def test_diagram_frames_pick_the_colors(tmp_path: Path):
    (tmp_path / "flow.mmd").write_text("flowchart LR\n  a --> b\n")
    (tmp_path / "deck.md").write_text(
        "---\nlayout: image\nimage: flow.mmd\n---\nlayout: image\nimage-frame: no\nimage: flow.mmd\n"
    )
    assert main(["build", str(tmp_path / "deck.md")]) == 0
    page = (tmp_path / "deck.html").read_text()
    assert page.count('<div class="diagram" role="img" aria-label="" data-mermaid="default">') == 1
    assert page.count('<div class="diagram bare" role="img" aria-label="" data-mermaid="theme">') == 1
    assert page.count('<pre class="diagram-src">flowchart LR\n  a --&gt; b\n</pre>') == 2
    assert page.count("/*! Mermaid") == 1
    assert '<script type="application/json" id="mermaid-theme">{"theme": "base", ' in page


def test_errors_exit_1_with_a_message(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["build", str(tmp_path / "missing.md")]) == 1
    assert capsys.readouterr().err == f"akceo: {tmp_path / 'missing.md'}: no such file\n"


def test_image_errors_name_the_slide(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    deck = tmp_path / "deck.md"
    deck.write_text("---\n## One\n---\nlayout: split\nimage: gone.png\n\n## Two\n")
    assert main(["build", str(deck)]) == 1
    assert f"{deck}:4: slide 2: image not found: {tmp_path / 'gone.png'}" in capsys.readouterr().err


def test_diagram_errors_name_the_slide_and_the_diagram_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    (tmp_path / "flow.mmd").write_text("flowchart LR\n  a --> b\n  b --> c(x]\n")
    deck = tmp_path / "deck.md"
    deck.write_text("---\n## One\n---\nlayout: image\nimage: flow.mmd\n")
    assert main(["build", str(deck)]) == 1
    assert capsys.readouterr().err == (
        f"akceo: {deck}:4: slide 2: {tmp_path / 'flow.mmd'}:3: Parse error: "
        "Expecting 'PE', 'TAGEND', 'UNICODE_TEXT', 'TEXT', 'TAGSTART', got 'SQE'\n"
    )
    assert not (tmp_path / "deck.html").exists()


def test_missing_diagram(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    deck = tmp_path / "deck.md"
    deck.write_text("---\nlayout: image\nimage: gone.mmd\n")
    assert main(["build", str(deck)]) == 1
    assert f"{deck}:2: slide 1: image not found: {tmp_path / 'gone.mmd'}" in capsys.readouterr().err


def test_check_reports_without_writing(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    shutil.copytree(DEMO, tmp_path / "demo", ignore=shutil.ignore_patterns("*.html"))
    deck = tmp_path / "demo" / "deck.md"
    assert main(["check", str(deck)]) == 0
    assert capsys.readouterr().out == f"ok: {deck} (8 slides)\n"
    assert not (tmp_path / "demo" / "deck.html").exists()

    (tmp_path / "demo" / "flow.mmd").write_text("flowchrt TD\n")
    assert main(["check", str(deck)]) == 1
    assert "flow.mmd:1: Mermaid doesn't recognise the diagram type" in capsys.readouterr().err
    assert not (tmp_path / "demo" / "deck.html").exists()


def test_bad_theme_in_deck_names_the_deck(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    deck = tmp_path / "deck.md"
    deck.write_text("theme: neon\n---\n## One\n")
    assert main(["build", str(deck)]) == 1
    assert capsys.readouterr().err.startswith(f"akceo: {deck}: unknown theme 'neon'")


def test_themes_command(capsys: pytest.CaptureFixture[str]):
    assert main(["themes"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("midnight  ") and lines[0].endswith("(default)")
    assert lines[1].startswith("paper     ")


def test_viewer_is_written_to_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    assert main(["viewer"]) == 0
    assert capsys.readouterr().out == "wrote md-viewer.html\n"
    page = (tmp_path / "md-viewer.html").read_text()
    assert page == (ROOT / "src" / "akceo" / "assets" / "md-viewer.html").read_text()
    assert "showOpenFilePicker" in page
    assert not EXTERNAL_REF.search(page)


def test_viewer_out_may_be_a_folder_or_a_file(tmp_path: Path):
    assert main(["viewer", "-o", str(tmp_path)]) == 0
    assert (tmp_path / "md-viewer.html").is_file()
    assert main(["viewer", "-o", str(tmp_path / "notes.html")]) == 0
    assert (tmp_path / "notes.html").is_file()


def test_packaged_assets_contain_no_raw_control_characters():
    # A raw NUL in a JavaScript regex is turned into U+FFFD by the HTML parser, which makes the whole
    # viewer script a syntax error while every Python test still passes. Escapes must stay as text.
    package = ROOT / "src" / "akceo"
    paths = [p for p in (*package.rglob("assets/**/*"), *package.glob("themes/*.css")) if p.is_file()]
    assert package / "assets" / "vendor" / "mermaid" / "mermaid.min.js" in paths
    assert len(paths) >= 12
    for path in paths:
        text = path.read_text(encoding="utf-8")
        bad = {hex(ord(c)) for c in text if (ord(c) < 32 and c not in "\n\t") or 0xE000 <= ord(c) <= 0xF8FF}
        assert not bad, f"{path.name}: {sorted(bad)}"
