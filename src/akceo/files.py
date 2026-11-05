import os
from pathlib import Path

from akceo.errors import DeckError


def is_file(path: Path) -> bool:
    """Whether path is a file. Unlike Path.is_file(), this is False for a name the system refuses,
    such as one too long, rather than an OSError."""
    return os.path.isfile(path)


def read_text(path: Path, what: str, newline: str | None = None) -> str:
    """Read a user-supplied UTF-8 file, turning read and decode failures into a DeckError. `what`
    names the file in the decode message, e.g. "deck" or "theme". `newline` is open()'s: "" keeps
    line endings as they are in the file."""
    try:
        with path.open(encoding="utf-8", newline=newline) as f:
            return f.read()
    except FileNotFoundError:
        raise DeckError("file-not-found", "no such file", path) from None
    except UnicodeDecodeError as e:
        line = e.object[: e.start].count(b"\n") + 1
        raise DeckError(
            "file-not-utf8", f"not valid UTF-8 text; save the {what} as UTF-8", path, line
        ) from None
    except OSError as e:
        raise DeckError("file-unreadable", str(e.strerror or e), path) from None
