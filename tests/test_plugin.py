"""The Claude Code plugin in plugin/, and the marketplace that lists it."""

import json
import re
import shlex
import tomllib
from pathlib import Path
from typing import Any

import pytest

from akceo import cli

ROOT = Path(__file__).parents[1]
PLUGIN = ROOT / "plugin"
SKILLS = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
DESCRIPTION_LIMIT = 1024


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _frontmatter(skill: Path) -> dict[str, str]:
    """The skill's frontmatter, each key written on one line."""
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{skill} opens without frontmatter"
    head = text.removeprefix("---\n").partition("\n---\n")[0]
    return dict(line.split(": ", 1) for line in head.splitlines())


def _commands() -> list[str]:
    """Each `akceo …` command the skills name, without the `akceo`."""
    texts = (skill.read_text(encoding="utf-8") for skill in SKILLS)
    return [command for text in texts for command in re.findall(r"`akceo ([^`]+)`", text)]


def test_the_plugin_has_akceos_version():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert _json(PLUGIN / ".claude-plugin" / "plugin.json")["version"] == pyproject["project"]["version"]


def test_the_marketplace_lists_the_plugin_by_its_own_name():
    [entry] = _json(ROOT / ".claude-plugin" / "marketplace.json")["plugins"]
    assert entry["name"] == _json(PLUGIN / ".claude-plugin" / "plugin.json")["name"]
    assert (ROOT / entry["source"]).resolve() == PLUGIN
    # Claude Code takes the version from plugin.json when both set one, so a second copy here could
    # only disagree.
    assert "version" not in entry


def test_the_plugin_carries_akceos_license():
    assert (PLUGIN / "LICENSE").read_text(encoding="utf-8") == (ROOT / "LICENSE").read_text(encoding="utf-8")


@pytest.mark.parametrize("skill", SKILLS, ids=[skill.parent.name for skill in SKILLS])
def test_each_skill_is_named_for_its_folder_and_says_when_to_use_it(skill: Path):
    frontmatter = _frontmatter(skill)
    assert frontmatter["name"] == skill.parent.name
    assert 0 < len(frontmatter["description"]) <= DESCRIPTION_LIMIT


@pytest.mark.parametrize("command", _commands())
def test_each_akceo_command_in_a_skill_is_one_akceo_takes(command: str):
    try:
        cli._parser().parse_args(shlex.split(command))  # pyright: ignore[reportPrivateUsage]
    except SystemExit:
        pytest.fail(f"akceo doesn't take: akceo {command}")


def test_the_skills_name_akceos_commands():
    assert SKILLS
    assert {shlex.split(command)[0] for command in _commands()} >= {"docs", "check", "build"}
