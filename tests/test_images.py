import base64
import io
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from akceo import images
from akceo.errors import DeckError
from akceo.images import data_uri


def decode(uri: str) -> tuple[str, bytes]:
    header, payload = uri.split(",", 1)
    return header, base64.b64decode(payload)


def save(path: Path, size: tuple[int, int], fmt: str) -> Path:
    Image.new("RGB", size, (200, 30, 30)).save(path, format=fmt)
    return path


def test_png_is_shrunk_to_max_px(tmp_path: Path):
    header, data = decode(data_uri(save(tmp_path / "a.png", (400, 200), "PNG"), 100))
    assert header == "data:image/png;base64"
    with Image.open(io.BytesIO(data)) as im:
        assert im.size == (100, 50)


def test_small_images_are_not_enlarged(tmp_path: Path):
    _, data = decode(data_uri(save(tmp_path / "a.png", (40, 20), "PNG"), 100))
    with Image.open(io.BytesIO(data)) as im:
        assert im.size == (40, 20)


@pytest.mark.parametrize(
    ("fmt", "suffix", "mime"), [("JPEG", "jpg", "image/jpeg"), ("WEBP", "webp", "image/webp")]
)
def test_jpeg_and_webp_keep_their_format(tmp_path: Path, fmt: str, suffix: str, mime: str):
    header, data = decode(data_uri(save(tmp_path / f"a.{suffix}", (300, 300), fmt), 150))
    assert header == f"data:{mime};base64"
    with Image.open(io.BytesIO(data)) as im:
        assert im.format == fmt
        assert im.size == (150, 150)


def test_svg_is_embedded_unchanged(tmp_path: Path):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
    (tmp_path / "a.svg").write_bytes(svg)
    assert decode(data_uri(tmp_path / "a.svg", 100)) == ("data:image/svg+xml;base64", svg)


def test_missing_image(tmp_path: Path):
    with pytest.raises(DeckError, match="image not found"):
        data_uri(tmp_path / "nope.png", 100)


def test_unsupported_format(tmp_path: Path):
    with pytest.raises(DeckError, match="unsupported image format GIF"):
        data_uri(save(tmp_path / "a.gif", (10, 10), "GIF"), 100)


def test_truncated_png(tmp_path: Path):
    noise = Image.frombytes("RGB", (200, 200), bytes(range(256)) * 468 + bytes(192))
    buf = io.BytesIO()
    noise.save(buf, format="PNG")
    (tmp_path / "a.png").write_bytes(buf.getvalue()[: len(buf.getvalue()) // 2])
    with pytest.raises(DeckError, match="can't read image .*a.png: image file is truncated"):
        data_uri(tmp_path / "a.png", 100)


def test_svg_read_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "a.svg").write_text("<svg/>")

    def denied(self: Path) -> bytes:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_bytes", denied)
    with pytest.raises(DeckError, match="can't read image .*a.svg: Permission denied"):
        data_uri(tmp_path / "a.svg", 100)


def test_unreadable_file(tmp_path: Path):
    (tmp_path / "a.png").write_text("not an image")
    with pytest.raises(DeckError, match="not a readable image"):
        data_uri(tmp_path / "a.png", 100)


MERMAID_SVG = b'<svg id="m" width="100%" style="max-width: 477.4px;" viewBox="0 0 477.41 174"><g/></svg>'


def mmdc_found(name: str) -> str | None:
    return "/bin/mmdc"


def mmdc_missing(name: str) -> str | None:
    return None


def fake_mmdc(
    monkeypatch: pytest.MonkeyPatch, returncode: int = 0, stderr: str = "", svg: bytes = MERMAID_SVG
):
    """Stand in for mmdc: write svg to the -o path and return the given result."""
    monkeypatch.setattr(images.shutil, "which", mmdc_found)
    calls: list[list[str]] = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if returncode == 0:
            Path(command[command.index("-o") + 1]).write_bytes(svg)
        return subprocess.CompletedProcess(command, returncode, "", stderr)

    monkeypatch.setattr(images.subprocess, "run", run)
    return calls


def test_mermaid_is_rendered_to_svg_with_a_pixel_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    calls = fake_mmdc(monkeypatch)
    (tmp_path / "flow.mmd").write_text("flowchart LR\n  a --> b\n")
    header, data = decode(data_uri(tmp_path / "flow.mmd", 100))
    assert header == "data:image/svg+xml;base64"
    assert data.startswith(b'<svg width="477" height="174" id="m" style="max-width: 477.4px;" ')
    assert data.endswith(b'viewBox="0 0 477.41 174"><g/></svg>')
    assert calls[0][:3] == ["/bin/mmdc", "-i", str(tmp_path / "flow.mmd")]
    assert calls[0][-3:] == ["-b", "transparent", "-q"]


def test_mermaid_without_mmdc_says_how_to_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(images.shutil, "which", mmdc_missing)
    (tmp_path / "flow.mmd").write_text("flowchart LR\n")
    with pytest.raises(
        DeckError, match=r"needs the Mermaid CLI \(mmdc\): npm install -g @mermaid-js/mermaid-cli"
    ):
        data_uri(tmp_path / "flow.mmd", 100)


def test_mermaid_syntax_errors_keep_the_message_and_drop_the_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    stderr = (
        "\nError: Parse error on line 2:\n...a -->\n----^\n"
        "    at Parser.parse (mermaid.js:1:1)\n    at run (cli.js:2:2)\n"
    )
    fake_mmdc(monkeypatch, returncode=1, stderr=stderr)
    (tmp_path / "flow.mmd").write_text("flowchart LR\n  a -->\n")
    with pytest.raises(DeckError) as e:
        data_uri(tmp_path / "flow.mmd", 100)
    assert str(e.value).endswith("flow.mmd: Error: Parse error on line 2: ...a --> ----^")


def test_mermaid_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(images.shutil, "which", mmdc_found)

    def slow(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(images.subprocess, "run", slow)
    (tmp_path / "flow.mmd").write_text("flowchart LR\n")
    with pytest.raises(DeckError, match=r"Mermaid took over 60s to render .*flow.mmd"):
        data_uri(tmp_path / "flow.mmd", 100)


@pytest.mark.skipif(shutil.which("mmdc") is None, reason="needs the Mermaid CLI (mmdc)")
def test_mermaid_renders_for_real(tmp_path: Path):
    (tmp_path / "flow.mmd").write_text("flowchart LR\n  a[deck.md] --> b([akceo build])\n")
    _, data = decode(data_uri(tmp_path / "flow.mmd", 100))
    assert data.startswith(b"<svg width=")
    assert b"akceo build" in data
    assert b"@import" not in data and b"url(http" not in data


MIDNIGHT = {"bg": "#0b0f16", "line": "#23324a", "text": "#e8eef6", "muted": "#93a4bd", "accent": "#5eead4"}


def test_mermaid_config_uses_the_theme_colors():
    config = images.mermaid_config({**MIDNIGHT, "font": "Inter, sans-serif"})
    assert config["theme"] == "base"
    variables = config["themeVariables"]
    assert variables["background"] == "#0b0f16"
    assert variables["primaryColor"] == "#23324a"
    assert variables["primaryBorderColor"] == "#5eead4"
    assert variables["primaryTextColor"] == variables["textColor"] == "#e8eef6"
    assert variables["lineColor"] == "#93a4bd"
    assert variables["fontFamily"] == "Inter, sans-serif"
    assert variables["darkMode"] is True


@pytest.mark.parametrize(
    ("bg", "dark"), [("#f7f5f0", False), ("#fff", False), ("#123", True), ("black", None)]
)
def test_mermaid_dark_mode_follows_the_background(bg: str, dark: bool | None):
    variables = images.mermaid_config({**MIDNIGHT, "bg": bg, "font": "x"})["themeVariables"]
    assert variables.get("darkMode") is dark


def test_mermaid_config_is_passed_to_mmdc_only_when_given(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    seen: list[str | None] = []
    monkeypatch.setattr(images.shutil, "which", mmdc_found)

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.append(Path(command[command.index("-c") + 1]).read_text() if "-c" in command else None)
        Path(command[command.index("-o") + 1]).write_bytes(MERMAID_SVG)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(images.subprocess, "run", run)
    (tmp_path / "flow.mmd").write_text("flowchart LR\n")
    data_uri(tmp_path / "flow.mmd", 100)
    data_uri(tmp_path / "flow.mmd", 100, {"theme": "base"})
    assert seen == [None, '{"theme": "base"}']
