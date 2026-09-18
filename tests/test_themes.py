from pathlib import Path

import pytest

from akceo import themes
from akceo.errors import DeckError

FULL = ":root {\n" + "".join(f"  --{t}: x;\n" for t in themes.TOKENS) + "}\n"


def test_builtin_themes_and_descriptions():
    names = themes.builtin()
    assert list(names) == ["midnight", "paper"]
    assert all(names.values())
    assert themes.DEFAULT in names


@pytest.mark.parametrize("name", ["midnight", "paper"])
def test_builtin_themes_set_every_token(name: str):
    assert themes.load(name, Path("/unused"))


def test_theme_file_resolves_against_base(tmp_path: Path):
    (tmp_path / "brand.css").write_text(FULL)
    assert themes.load("brand.css", tmp_path) == FULL


def test_unknown_builtin_lists_the_real_ones():
    with pytest.raises(DeckError, match=r"unknown theme 'neon' \(built-in themes: midnight, paper\)"):
        themes.load("neon", Path("."))


def test_missing_theme_file(tmp_path: Path):
    with pytest.raises(DeckError, match="theme file not found"):
        themes.load("nope.css", tmp_path)


def test_missing_tokens_are_listed(tmp_path: Path):
    partial = FULL.replace("  --bg: x;\n", "").replace("  --mono: x;\n", "")
    (tmp_path / "partial.css").write_text(partial)
    with pytest.raises(DeckError, match=r"doesn't set: --bg, --mono$"):
        themes.load("partial.css", tmp_path)
