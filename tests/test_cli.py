import re
import shutil
from pathlib import Path

import pytest
from PIL import Image

from akceo.cli import main

DEMO = Path(__file__).parents[1] / "examples" / "demo"


def test_builds_the_demo_deck_self_contained(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    out = tmp_path / "demo.html"
    assert main(["build", str(DEMO / "deck.md"), "-o", str(out)]) == 0
    assert re.fullmatch(rf"wrote {re.escape(str(out))} \(\d+ KB, 7 slides\)\n", capsys.readouterr().out)

    page = out.read_text()
    assert page.count('<section class="slide') == 7
    assert "__SLIDES__" not in page
    assert "data:image/svg+xml;base64," in page
    assert not re.search(r"""(src|href)=["']?(https?:|//|\.{0,2}/)|<link|@import|url\(""", page)


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
    shutil.copy(
        Path(__file__).parents[1] / "src" / "akceo" / "themes" / "paper.css", tmp_path / "talk" / "brand.css"
    )
    (tmp_path / "talk" / "deck.md").write_text(
        "theme: brand.css\nimages: img\n---\nlayout: split\nimage: fig.png\n\n## Figure\n"
    )
    monkeypatch.chdir(tmp_path)
    assert main(["build", "talk/deck.md"]) == 0
    page = (tmp_path / "talk" / "deck.html").read_text()
    assert "data:image/png;base64," in page
    assert "--bg: #f7f5f0;" in page


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
