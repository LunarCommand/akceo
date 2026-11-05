"""The packaged guide, src/akceo/AGENTS.md, is what scripts/build_agents_md.py writes."""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "build_agents_md.py"
GUIDE = ROOT / "src" / "akceo" / "AGENTS.md"


@pytest.fixture(scope="module")
def generator() -> Any:
    spec = importlib.util.spec_from_file_location("build_agents_md", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_packaged_guide_is_current(generator: Any):
    assert GUIDE.read_text(encoding="utf-8") == generator.build(), (
        "run: uv run python scripts/build_agents_md.py"
    )


def test_the_guide_holds_the_syntax_reference_and_the_demo_deck():
    guide = GUIDE.read_text(encoding="utf-8")
    assert guide.startswith("# Writing akceo decks\n")
    assert "\n## Deck syntax\n" in guide and "\n### Config block\n" in guide
    assert "\n## Deck recipes\n" in guide
    assert (ROOT / "examples" / "demo" / "deck.md").read_text(encoding="utf-8").strip() in guide


def test_headings_in_code_fences_stay_as_written(generator: Any):
    text = (
        "# Title\n\n```markdown\n# My Talk\n## Agenda\n```\n\n"
        "## Next\n\n````\n```\n# kept\n````\n#5 is a link\n"
    )
    assert generator.demoted(text) == (
        "## Title\n\n```markdown\n# My Talk\n## Agenda\n```\n\n"
        "### Next\n\n````\n```\n# kept\n````\n#5 is a link"
    )


@pytest.mark.parametrize(
    ("text", "refused"),
    [
        ("See [how it works](how-it-works.md).", True),
        ("See [Images](#images) and [the repo](https://github.com/LunarCommand/akceo).", False),
        ("Write `[text](url)` for a link.", False),
        ("```\n[text](url)\n```", False),
    ],
)
def test_a_link_to_another_file_is_refused(
    generator: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str, refused: bool
):
    # The guide ships without the docs, so a relative link in it would lead nowhere.
    (tmp_path / "doc.md").write_text(text, encoding="utf-8")
    monkeypatch.setattr(generator, "ROOT", tmp_path)
    if refused:
        with pytest.raises(SystemExit, match="doc.md links to another file"):
            generator._read("doc.md")
    else:
        assert generator._read("doc.md") == text
