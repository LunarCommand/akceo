import re
import shutil
from pathlib import Path

import pytest
from PIL import Image

from akceo.cli import main

ROOT = Path(__file__).parents[1]
DEMO = ROOT / "examples" / "demo"
EXTERNAL_REF = re.compile(r"""(src|href)=["']?(https?:|//|\.{0,2}/)|<link|@import|url\(""")


def test_builds_the_demo_deck_self_contained(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    out = tmp_path / "demo.html"
    assert main(["build", str(DEMO / "deck.md"), "-o", str(out)]) == 0
    assert re.fullmatch(rf"wrote {re.escape(str(out))} \(\d+ KB, 8 slides\)\n", capsys.readouterr().out)

    page = out.read_text()
    assert page.count('<section class="slide') == 8
    assert "__SLIDES__" not in page
    assert "data:image/svg+xml;base64," in page
    assert not EXTERNAL_REF.search(page)
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


def test_errors_exit_1_with_a_message(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["build", str(tmp_path / "missing.md")]) == 1
    assert capsys.readouterr().err == f"akceo: {tmp_path / 'missing.md'}: no such file\n"


def test_image_errors_name_the_slide(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    deck = tmp_path / "deck.md"
    deck.write_text("---\n## One\n---\nlayout: split\nimage: gone.png\n\n## Two\n")
    assert main(["build", str(deck)]) == 1
    assert f"{deck}:4: slide 2: image not found: {tmp_path / 'gone.png'}" in capsys.readouterr().err


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
    paths = [*package.glob("assets/*"), *package.glob("themes/*.css")]
    assert len(paths) >= 6
    for path in paths:
        text = path.read_text(encoding="utf-8")
        bad = {hex(ord(c)) for c in text if (ord(c) < 32 and c not in "\n\t") or 0xE000 <= ord(c) <= 0xF8FF}
        assert not bad, f"{path.name}: {sorted(bad)}"
