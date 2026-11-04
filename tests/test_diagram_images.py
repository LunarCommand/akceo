import base64
import io
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PIL import Image

from akceo import diagram_images
from akceo.diagram_images import Inlined
from akceo.errors import DeckError
from akceo.mermaid import Checker

Inline = Callable[[Path, str], tuple[str, list[Inlined]]]
URI = re.compile(r'"(data:(image/[a-z+]+);base64,([A-Za-z0-9+/=]+))"')


def png(path: Path, size: tuple[int, int] = (400, 200)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (200, 30, 30)).save(path)
    return path


def sizes(source: str) -> list[tuple[int, int]]:
    """The size of each PNG, JPEG or WebP data: URI in source."""
    found: list[tuple[int, int]] = []
    for m in URI.finditer(source):
        with Image.open(io.BytesIO(base64.b64decode(m[3]))) as im:
            found.append(im.size)
    return found


def node(shape_data: str) -> str:
    return f"flowchart LR\n  a --> b\n  b@{{ {shape_data} }}\n"


@pytest.fixture(scope="module")
def checker() -> Iterator[Checker]:
    with Checker() as c:
        yield c


@pytest.fixture
def inline(checker: Checker) -> Inline:
    """inline, given the node images Mermaid reads in the source, as the build gives it them."""

    def run(path: Path, source: str) -> tuple[str, list[Inlined]]:
        return diagram_images.inline(path, source, checker.images(path, source))

    return run


@pytest.mark.parametrize(
    "spelling",
    ['img: "shot.png"', "img: 'shot.png'", "img: shot.png", '"img": "shot.png"', '"img":"shot.png"'],
)
def test_a_file_path_is_inlined_as_a_data_uri(inline: Inline, tmp_path: Path, spelling: str):
    png(tmp_path / "shot.png")
    source = node(f'{spelling}, label: "Shot"')
    out, inlined = inline(tmp_path / "flow.mmd", source)
    uri = URI.search(out)
    assert uri and uri[2] == "image/png"
    assert "shot.png" not in out
    assert out.replace(uri[0], "X") == source.replace(spelling.split(":", 1)[1].strip(), "X")
    assert inlined == [Inlined("shot.png", 3, len(uri[1]))]


def test_every_line_stays_where_it_was(inline: Inline, tmp_path: Path):
    png(tmp_path / "shot.png")
    source = 'flowchart LR\n  a@{ img: "shot.png" }\n  a --> b\n  b@{\n    img: "shot.png"\n  }\n  b --> c\n'
    out, inlined = inline(tmp_path / "flow.mmd", source)
    assert [line for line in out.splitlines() if "data:" not in line] == [
        line for line in source.splitlines() if "shot.png" not in line
    ]
    assert len(out.splitlines()) == len(source.splitlines())
    assert [image.line for image in inlined] == [2, 5]


def test_a_path_resolves_against_the_diagrams_folder(inline: Inline, tmp_path: Path):
    png(tmp_path / "talk" / "img" / "my shot.png")
    out, _ = inline(tmp_path / "talk" / "flow.mmd", node('img: "img/my shot.png"'))
    assert sizes(out) == [(400, 200)]


def test_svg_is_inlined_unchanged(inline: Inline, tmp_path: Path):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
    (tmp_path / "logo.svg").write_bytes(svg)
    out, _ = inline(tmp_path / "flow.mmd", node('img: "logo.svg"'))
    uri = URI.search(out)
    assert uri and uri[2] == "image/svg+xml" and base64.b64decode(uri[3]) == svg


def test_data_uris_urls_and_comments_are_left_for_the_check(inline: Inline, tmp_path: Path):
    source = (
        "flowchart LR\n"
        '  a@{ img: "data:image/png;base64,AAAA" }\n'
        '  b@{ img: "https://x.example/b.png" }\n'
        '  c@{ img: "//x.example/c.png" }\n'
        '  %% d@{ img: "gone.png" }\n'
        '  e@{ img: "" }\n'
    )
    assert inline(tmp_path / "flow.mmd", source) == (source, [])


def test_values_are_read_as_mermaid_reads_them(inline: Inline, tmp_path: Path):
    # Each of these is an image for Mermaid (see test_shape_data.py), so each is inlined.
    for name in ("my shot.png", "my b.png", "my c.png"):
        png(tmp_path / name)
    source = (
        "flowchart LR\n"
        '  a@{ label: "a } b", img: my shot.png }\n'
        "  b@{\n    img: >-\n      my b.png\n    w: 50\n  }\n"
        "  c@{\n    img:\n      'my c.png'\n  }\n"
        "  a --> b --> c\n"
    )
    out, inlined = inline(tmp_path / "flow.mmd", source)
    assert sizes(out) == [(400, 200), (100, 50), (400, 200)]
    assert [image.line for image in inlined] == [2, 4, 10]
    assert len(out.splitlines()) == len(source.splitlines())
    assert out.splitlines()[-1] == "  a --> b --> c"


def test_a_colon_without_a_space_isnt_a_key(inline: Inline, tmp_path: Path):
    # Mermaid reads img:shot.png as one plain word, so the node has no image.
    source = node("img:shot.png")
    assert inline(tmp_path / "flow.mmd", source) == (source, [])


def test_an_img_in_a_quoted_label_isnt_read_as_a_key(inline: Inline, tmp_path: Path):
    png(tmp_path / "shot.png")
    out, inlined = inline(tmp_path / "flow.mmd", node('label: "Docs, img: gone.png", img: "shot.png"'))
    assert [image.name for image in inlined] == ["shot.png"]
    assert 'label: "Docs, img: gone.png"' in out


@pytest.mark.parametrize(
    "source",
    [
        # Mermaid reads these as text, or as no image, so the file isn't read or put in.
        'flowchart LR\n  a["write @{ img: shot.png } on a node"] --> b\n',
        'flowchart LR\n  a -- "see @{ img: shot.png }" --> b\n',
        "timeline\n  2024 : a node takes @{ img: shot.png }\n",
        "flowchart LR\n  b@{ img: null }\n",
    ],
)
def test_what_mermaid_doesnt_read_as_an_image_is_left_alone(inline: Inline, tmp_path: Path, source: str):
    png(tmp_path / "shot.png")
    assert inline(tmp_path / "flow.mmd", source) == (source, [])


@pytest.mark.parametrize(
    "source",
    [
        # The label names the same file as the real image, and stays as it is.
        'flowchart LR\n  a["see @{ img: shot.png }"] --> b@{ img: "shot.png" }\n',
        'flowchart LR\n  a -- see @{ img: shot.png } --> b@{ img: "shot.png" }\n',
        # Front matter and directives aren't scanned: here they'd open a string or edge text.
        '---\ntitle: The "new -- form\n---\nflowchart LR\n  b@{ img: "shot.png" }\n',
        '%%{init: {"themeCSS": ".x { fill: var(--c) }"}}%%\nflowchart LR\n  b@{ img: "shot.png" }\n',
    ],
)
def test_only_the_image_mermaid_reads_is_replaced(inline: Inline, tmp_path: Path, source: str):
    png(tmp_path / "shot.png")
    out, inlined = inline(tmp_path / "flow.mmd", source)
    uri = URI.search(out)
    assert uri and [image.line for image in inlined] == [source.count("\n")]
    assert out.replace(uri[0], '"shot.png"') == source


@pytest.mark.parametrize("shape_data", ["img: &p shot.png", "? img : shot.png"])
def test_an_image_mermaid_reads_that_akceo_cant_find_stops_the_build(
    inline: Inline, tmp_path: Path, shape_data: str
):
    png(tmp_path / "shot.png")
    with pytest.raises(DeckError) as e:
        inline(tmp_path / "flow.mmd", node(shape_data))
    assert str(e.value) == (
        f"{tmp_path / 'flow.mmd'}: akceo can't tell where node b's img: shot.png is written, to put the "
        'file in; write it on one line, such as img: "shot.png"'
    )


def test_a_missing_image_names_the_diagram_line(inline: Inline, tmp_path: Path):
    with pytest.raises(DeckError) as e:
        inline(tmp_path / "flow.mmd", node('img: "gone.png"'))
    assert str(e.value) == f"{tmp_path / 'flow.mmd'}:3: image not found: {tmp_path / 'gone.png'}"


@pytest.mark.parametrize(
    ("shape_data", "size"),
    [
        # Without w or h Mermaid draws the image at its own size, so it isn't shrunk.
        ('img: "shot.png"', (400, 200)),
        ('img: "shot.png", w: 50', (100, 50)),
        ('img: "shot.png", h: 25', (100, 50)),
        ('img: "shot.png", w: 150, h: 25', (100, 50)),
        ('w: "60", img: "shot.png"', (120, 60)),
        ('\n    img: "shot.png"\n    w: 50\n ', (100, 50)),
        ('img: "shot.png", w: 1000', (400, 200)),
        # Text in a quoted label isn't a key.
        ('label: "w: 10, h: 5", img: "shot.png"', (400, 200)),
        ('img: "shot.png", label: "w: 10", w: 50', (100, 50)),
        ('img: "shot.png#max=200", w: 50', (200, 100)),
        ('img: "shot.png#max=100"', (100, 50)),
        ('img: "shot.png#crop=0,0,100,50"', (100, 50)),
        ('img: "shot.png#crop=0, 0, 200, 200&max=50"', (50, 50)),
        ('img: "shot.png#max=50&crop=0,0,200,200"', (50, 50)),
        # w and h are numbers as Mermaid reads them; one it can't use leaves the image as it is.
        ('img: "shot.png", w: 1e2', (200, 100)),
        ('img: "shot.png", w: -5', (400, 200)),
        ('img: "shot.png", w: 1' + "0" * 308, (400, 200)),
    ],
)
def test_size_and_options(inline: Inline, tmp_path: Path, shape_data: str, size: tuple[int, int]):
    png(tmp_path / "shot.png")
    out, inlined = inline(tmp_path / "flow.mmd", node(shape_data))
    assert sizes(out) == [size]
    assert [image.name for image in inlined] == ["shot.png"]


@pytest.mark.parametrize(
    ("shape_data", "message"),
    [
        (
            'img: "shot.png#zoom=2"',
            "an img: path takes crop= and max= after its #, joined with &, not 'zoom=2' "
            "(a file name can't contain #)",
        ),
        ('img: "shot.png#"', "an img: path takes crop= and max= after its #, joined with &, not ''"),
        ('img: "shot.png#crop"', "an img: path takes crop= and max= after its #, joined with &, not 'crop'"),
        ('img: "shot.png#max=10&max=20"', "an img: path takes max= only once"),
        ('img: "shot.png#crop=0,0,10"', "'crop' must be four whole numbers of pixels"),
        ('img: "shot.png#crop=10,0,10,10"', "'crop' 10,0,10,10 is empty"),
        ('img: "shot.png#max=0"', "'max' must be a positive whole number of pixels"),
        (
            'img: "shot.png#crop=0,0,500,100"',
            "the crop 0, 0, 500, 100 goes past the edge of {dir}/shot.png, which is 400 by 200 pixels",
        ),
        (
            "img: shot.png#max=10",
            'quote an img: path that has options, such as img: "shot.png#crop=120,80,920,580"',
        ),
        ('img: "#max=300"', 'an img: needs a file path before its #, such as img: "shot.png#max=300"'),
        (
            'img: "logo.svg#max=30"',
            "max= can't shrink an SVG image, so set the node's w and h instead: {dir}/logo.svg",
        ),
    ],
)
def test_option_errors_name_the_diagram_line(inline: Inline, tmp_path: Path, shape_data: str, message: str):
    png(tmp_path / "shot.png")
    (tmp_path / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"/>')
    with pytest.raises(DeckError) as e:
        inline(tmp_path / "flow.mmd", node(shape_data))
    assert str(e.value).startswith(f"{tmp_path / 'flow.mmd'}:3: {message.format(dir=tmp_path)}")


@pytest.mark.parametrize(
    ("source", "size"),
    [
        # Mermaid gives a node the w and h from every @{…} for it.
        ('flowchart LR\n  b@{ img: "shot.png" }\n  b@{ w: 50 }\n', (100, 50)),
        # An image several nodes use is sized for the largest. Mermaid draws a side a node doesn't
        # set at the image's own size, so that side isn't shrunk.
        ('flowchart LR\n  a@{ img: "shot.png", w: 25 }\n  b@{ img: "shot.png", w: 50 }\n', (100, 50)),
        ('flowchart LR\n  a@{ img: "shot.png", h: 25 }\n  b@{ img: "shot.png", w: 25 }\n', (400, 200)),
        ('flowchart LR\n  a@{ img: "shot.png" }\n  b@{ img: "shot.png", w: 50 }\n', (400, 200)),
    ],
)
def test_sizes_come_from_every_node_using_the_image(
    inline: Inline, tmp_path: Path, source: str, size: tuple[int, int]
):
    png(tmp_path / "shot.png")
    out, inlined = inline(tmp_path / "flow.mmd", source)
    assert set(sizes(out)) == {size}
    assert len(inlined) == source.count("shot.png")


def test_each_inlined_image_is_listed_with_its_size(inline: Inline, tmp_path: Path):
    png(tmp_path / "a.png", (40, 40))
    png(tmp_path / "b.png", (80, 40))
    source = 'flowchart LR\n  a@{ img: "a.png" }\n  a --> b\n  b@{ img: "b.png" } --> c@{ img: "a.png" }\n'
    out, inlined = inline(tmp_path / "flow.mmd", source)
    uris = [m[1] for m in URI.finditer(out)]
    assert inlined == [
        Inlined("a.png", 2, len(uris[0])),
        Inlined("b.png", 4, len(uris[1])),
        Inlined("a.png", 4, len(uris[2])),
    ]
