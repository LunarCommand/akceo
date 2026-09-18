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


def test_theme_that_would_close_the_style_block_is_rejected(tmp_path: Path):
    (tmp_path / "evil.css").write_text(FULL + "/* </STYLE><script>alert(1)</script> */\n")
    with pytest.raises(DeckError, match="contains '</style'"):
        themes.load("evil.css", tmp_path)


def test_non_utf8_theme_names_the_line(tmp_path: Path):
    (tmp_path / "brand.css").write_bytes(FULL.encode() + b"/* caf\xe9 */\n")
    with pytest.raises(DeckError, match=r"brand\.css:14: not valid UTF-8 text; save the theme as UTF-8"):
        themes.load("brand.css", tmp_path)


def test_theme_read_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "brand.css").write_text(FULL)

    def denied(self: Path, encoding: str | None = None) -> str:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(DeckError, match=r"brand\.css: Permission denied$"):
        themes.load("brand.css", tmp_path)


def test_missing_tokens_are_listed(tmp_path: Path):
    partial = FULL.replace("  --bg: x;\n", "").replace("  --mono: x;\n", "")
    (tmp_path / "partial.css").write_text(partial)
    with pytest.raises(DeckError, match=r"doesn't set: --bg, --mono$"):
        themes.load("partial.css", tmp_path)
