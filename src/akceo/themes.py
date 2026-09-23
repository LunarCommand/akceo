"""Find and check themes. A theme is a CSS file that sets the tokens listed in TOKENS."""

import re
from importlib import resources
from pathlib import Path

from akceo import files
from akceo.errors import DeckError

DEFAULT = "midnight"
TOKENS = (
    "bg",
    "line",
    "text",
    "muted",
    "strong",
    "accent",
    "accent2",
    "figure-bg",
    "figure-shadow",
    "font",
    "mono",
)
BUILTIN = resources.files("akceo") / "themes"
LEADING_COMMENT = re.compile(r"^\s*/\*\s*(.*?)\s*\*/", re.DOTALL)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
TOKEN_VALUE = re.compile(r"(?<![\w-])--([\w-]+)\s*:\s*([^;}]+)")


def builtin() -> dict[str, str]:
    """Map each built-in theme's name to the description in its leading comment."""
    names: dict[str, str] = {}
    for entry in sorted(BUILTIN.iterdir(), key=lambda e: e.name):
        if entry.name.endswith(".css"):
            m = LEADING_COMMENT.match(entry.read_text(encoding="utf-8"))
            names[entry.name.removesuffix(".css")] = m.group(1) if m else ""
    return names


def load(spec: str, base: Path) -> str:
    """Return a theme's CSS. A spec ending in .css or containing a slash is a file path, resolved
    against base; anything else names a built-in theme."""
    if spec.endswith(".css") or "/" in spec or "\\" in spec:
        path = base / Path(spec).expanduser()
        if not path.is_file():
            raise DeckError(f"theme file not found: {path}")
        css, label = files.read_text(path, "theme"), str(path)
    else:
        entry = BUILTIN / f"{spec}.css"
        if not entry.is_file():
            raise DeckError(f"unknown theme '{spec}' (built-in themes: {', '.join(builtin())})")
        css, label = entry.read_text(encoding="utf-8"), spec
    if re.search(r"</style", css, re.IGNORECASE):
        raise DeckError(f"theme {label} contains '</style', which would end the page's style block")
    declarations = _declarations(css)
    missing = [t for t in TOKENS if not re.search(rf"(?<![\w-])--{re.escape(t)}\s*:", declarations)]
    if missing:
        raise DeckError(f"theme {label} doesn't set: {', '.join('--' + t for t in missing)}")
    return css


def values(css: str) -> dict[str, str]:
    """Map each token a theme sets to its value, without the leading --. A later setting wins, as in
    CSS."""
    return {name: value.strip() for name, value in TOKEN_VALUE.findall(_declarations(css))}


def _declarations(css: str) -> str:
    """The CSS without its comments, so a `--token:` written in a comment is neither read nor counted."""
    return CSS_COMMENT.sub(" ", css)
