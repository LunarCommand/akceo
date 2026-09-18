import base64
import io
from pathlib import Path

import pytest
from PIL import Image

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
