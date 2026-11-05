import re
from pathlib import Path

import pytest

from akceo import themes
from akceo.errors import DeckError

FULL = ":root {\n" + "".join(f"  --{t}: x;\n" for t in themes.TOKENS) + "}\n"
# The tokens base.css colors text with. It also colors the step numbers --bg, on --accent.
TEXT_TOKENS = ("text", "muted", "strong", "accent", "accent2", "link", "link-hover")
TEXT_COLOR = re.compile(r"(?<![\w-])color:\s*var\(--([a-z0-9-]+)\)")


def test_builtin_themes_and_descriptions():
    names = themes.builtin()
    assert list(names) == ["midnight", "paper"]
    assert all(names.values())
    assert themes.DEFAULT in names


@pytest.mark.parametrize("name", ["midnight", "paper"])
def test_builtin_themes_set_every_token(name: str):
    css = themes.load(name, Path("/unused"))
    assert themes.missing(css, themes.LINK_TOKENS) == []


def test_text_is_colored_only_with_text_tokens():
    base = (Path(themes.__file__).with_name("assets") / "base.css").read_text()
    assert set(TEXT_COLOR.findall(base)) - {"bg"} <= set(TEXT_TOKENS)


@pytest.mark.parametrize("name", ["midnight", "paper"])
def test_builtin_text_tokens_are_readable_on_the_background(name: str):
    # WCAG 2.2 §1.4.3: text needs 4.5:1 against its background.
    tokens = themes.values(themes.load(name, Path("/unused")))
    ratios = {t: round(contrast(tokens[t], tokens["bg"]), 2) for t in TEXT_TOKENS}
    assert {t: r for t, r in ratios.items() if r < 4.5} == {}


def contrast(a: str, b: str) -> float:
    """The WCAG contrast ratio of two colors written #rgb or #rrggbb."""

    def luminance(color: str) -> float:
        digits = color.removeprefix("#")
        if len(digits) == 3:
            digits = "".join(d * 2 for d in digits)
        channels = [int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


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

    def denied(self: Path, *args: object, **kwargs: object) -> str:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(DeckError, match=r"brand\.css: Permission denied$"):
        themes.load("brand.css", tmp_path)


def test_missing_tokens_are_listed(tmp_path: Path):
    partial = FULL.replace("  --bg: x;\n", "").replace("  --mono: x;\n", "")
    (tmp_path / "partial.css").write_text(partial)
    with pytest.raises(DeckError, match=r"doesn't set: --bg, --mono$"):
        themes.load("partial.css", tmp_path)


def test_values_reads_each_token_and_a_later_setting_wins():
    css = ':root { --bg: #000; --font: "Inter", sans-serif; }\n.x { --bg: #fff }\n'
    assert themes.values(css) == {"bg": "#fff", "font": '"Inter", sans-serif'}


def test_values_ignore_tokens_inside_comments():
    css = ":root { --bg: #000; /* --bg: page background */\n  --line: #234; }"
    assert themes.values(css) == {"bg": "#000", "line": "#234"}


def test_a_token_set_only_in_a_comment_is_missing(tmp_path: Path):
    css = FULL.replace("  --accent: x;\n", "  /* --accent: x; */\n")
    (tmp_path / "t.css").write_text(css)
    with pytest.raises(DeckError, match="doesn't set: --accent$"):
        themes.load("t.css", tmp_path)
