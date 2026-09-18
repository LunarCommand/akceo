from pathlib import Path

from akceo.errors import DeckError


def read_text(path: Path, what: str) -> str:
    """Read a user-supplied UTF-8 file, turning read and decode failures into a DeckError. `what`
    names the file in the decode message, e.g. "deck" or "theme"."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise DeckError(f"{path}: no such file") from None
    except UnicodeDecodeError as e:
        line = e.object[: e.start].count(b"\n") + 1
        raise DeckError(f"{path}:{line}: not valid UTF-8 text; save the {what} as UTF-8") from None
    except OSError as e:
        raise DeckError(f"{path}: {e.strerror or e}") from None
