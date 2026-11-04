import json
import subprocess
import sys
import time

import pytest

from akceo import shape_data

# Mermaid itself is the reference for how shape data reads. This runs in its own process, as the
# check's worker does, so an open V8 context can't hang the test run when it ends.
MERMAID_READS = r"""
import json, os, sys
from py_mini_racer import MiniRacer
from akceo.mermaid import ASSETS, VENDOR

ctx = MiniRacer()
ctx.eval((ASSETS / "mermaid-shims.js").read_text(encoding="utf-8"))
ctx.eval((VENDOR / "mermaid.min.js").read_text(encoding="utf-8"))
ctx.eval('''
globalThis.shapes = async (source) => {
  await mermaid.parse(source);
  const diagram = await mermaid.mermaidAPI.getDiagramFromText(source);
  const node = diagram.db.getVertices().get('a');
  return JSON.stringify({ img: node.img, w: node.assetWidth, h: node.assetHeight });
};
''')
results = []
for source in json.load(sys.stdin):
    try:
        results.append(json.loads(ctx.eval(f"shapes({json.dumps(source)})").get()))
    except Exception as e:
        results.append({"error": str(e)})
print(json.dumps(results), flush=True)
os._exit(0)
"""

# Each is one node, a, whose shape data Mermaid reads without error.
CASES = [
    'a@{ img: "x.png", w: 40 }',
    "a@{ img: my shot.png, w: 40 }",
    "a@{ label: \"a } b\", img: 'it''s.png' }",
    'a@{ label: "Docs, img: no.png", img: "yes.png" }',
    'a@{ label: "w: 10, h: 5", img: x.png }',
    'a@{ label: "two\n      lines", img: x.png }',
    "a@{ img: shot.png #note }",
    "a@{ img: shot.png #note\n }",
    'a@{ img: "C:\\\\shots\\\\x.png" }',
    'a@{ img: "caf\\u00e9.png" }',
    'a@{ label: "\\U00110000 \\ud800", img: x.png }',
    'a@{ w: "60", img: x.png }',
    "a@{ w: 50.5, h: 20, img: x.png }",
    "a@{ img:shot.png }",
    'a@{ "img":"x.png" }',
    # The comma shows the value after "img": is read as a string, not as plain text.
    'a@{ "img":"a, b.png" }',
    'a@{ "img": \'y.png\', "w": 12 }',
    # A quote after a comma opens a quoted key, so the img: in it is text.
    'a@{ w: 4, "k, img: z.png": 1, img: y.png }',
    "a@{ img : x.png , w : 7 }",
    "a@{ img: 'a, b.png' }",
    "a@{ label: It's me, img: 'shot.png' }",
    "a@{ label: L # example, img: missing.png }",
    "a@{ img: x.png # w: 10 }",
    "a@{\n    img: my shot.png#crop=1,2,3,4\n    w: 40\n  }",
    "a@{\n    img: >-\n      folded.png\n    h: 30\n  }",
    "a@{\n    img: >\n      folded.png\n  }",
    "a@{\n    img: |\n      lit.png\n  }",
    "a@{\n    img: >-\n      shot.png\n    # explain the image\n    w: 30\n  }",
    "a@{\n    img: |\n      shot.png\n      # part of the value\n  }",
    'a@{\n    img:\n      "next.png"\n  }',
    "a@{\n    img: my\n      shot.png\n  }",
    "a@{\n    # a comment\n    img: x.png # note\n    label: >\n      img: no.png\n  }",
    'a@{\n    label: "L"\n    img: "x.png"\n    h: 20\n  }',
    # A "…" inside a plain value is the lexer's string, so its line break doesn't make a block.
    'a@{ label: Click "Save\n      and close" when done, img: shot.png, w: 40 }',
    'a@{ img: shot.png, label: Click "Save\n      and close" when done }',
    'a@{\n    label: The "quick\n  start" guide\n    img: x.png\n  }',
    # Single-quoted values run over lines, and text in them isn't a key.
    "a@{\n    img: 'my\n      shot.png'\n    w: 40\n  }",
    # Spaces on either side of the break fold into it.
    "a@{\n    img: 'my  \n      shot.png'\n  }",
    "a@{\n    label: 'see\n    img: logo.png\n    here'\n    img: shot.png\n  }",
    "a@{\n    label: 'one\n  two'\n    img: shot.png\n  }",
    "a@{\n    img: 'one\n\n      two.png'\n  }",
    "a@{\n    img: 'shot.png\n    '\n  }",
    # A quote after a colon inside a plain value is a character.
    "a@{ label: Era:'90s, img: 'x.png', w: 100 }",
    # Blank and comment lines between a key and its value.
    'a@{\n    img:\n      # note\n      "next.png"\n  }',
    'a@{\n    img:\n  # note\n      "next.png"\n  }',
    "a@{\n    img:\n\n      next.png\n  }",
    # Escapes in double quotes, in a value and in a key, and a quoted key that isn't img.
    'a@{ label: "say \\"hi, img: x.png\\"", img: "shot.png" }',
    'a@{ "im\\x67": x.png }',
    'a@{ "img ": x.png }',
    # A plain value folds a blank line into a line break.
    "a@{\n    img: my\n\n      shot.png\n  }",
    # Where the lexer reads @{ as text: strings, edge text and accessibility text.
    'b["x@{y"] --> a@{ img: x.png } --> c["}"]',
    'b["see @{ img: y.png }"] --> a@{ img: x.png }',
    "b -- see @{ img: y.png } --> a@{ img: x.png }",
    "b == see @{ img: y.png } ==> a@{ img: x.png }",
    'b -- "see @{ img: y.png }" --> a@{ img: x.png }',
    "b--c-->a@{ img: x.png }",
    "accTitle: see @{ img: y.png }\n  a@{ img: x.png }",
    "accDescr: it's 5\" tall\n  a@{ img: x.png }",
]
REPLACEMENT = '"data:image/png;base64,AAAA"'


def source(case: str) -> str:
    return f"flowchart LR\n  {case}\n"


def ours(text: str) -> dict[str, object]:
    """What the reader finds for a's img, w and h, with sizes as numbers, as Mermaid gives them. A
    key found twice gives a list, which Mermaid never does for one block: it refuses a repeated key.
    Without that, text in a label read as an img would pass whenever the real img came after it.
    Text read as more or fewer than one block gives the count, so that case fails by name instead
    of the whole module failing to load."""
    blocks = list(shape_data.blocks(text))
    if len(blocks) != 1:
        return {"blocks": len(blocks)}
    found: dict[str, object] = {}
    for entry in blocks[0]:
        if entry.key in ("img", "w", "h"):
            value = entry.value if entry.key == "img" else float(entry.value)
            found[entry.key] = [found[entry.key], value] if entry.key in found else value
    return found


def replaced(text: str) -> str:
    """text with a's img value replaced in place, followed by the line breaks it spanned."""
    (entries,) = shape_data.blocks(text)
    entry = next(e for e in entries if e.key == "img")
    return (
        text[: entry.start]
        + REPLACEMENT
        + "\n" * text.count("\n", entry.start, entry.end)
        + text[entry.end :]
    )


@pytest.fixture(scope="module")
def mermaid() -> dict[str, dict[str, object]]:
    sources = [source(case) for case in CASES]
    sources += [replaced(text) for text in sources if "img" in ours(text)]
    run = subprocess.run(
        [sys.executable, "-c", MERMAID_READS],
        input=json.dumps(sources),
        capture_output=True,
        text=True,
        check=True,
    )
    reads = [{k: v for k, v in read.items() if v is not None} for read in json.loads(run.stdout)]
    return dict(zip(sources, reads, strict=True))


@pytest.mark.parametrize("case", CASES)
def test_shape_data_reads_as_mermaid_reads_it(mermaid: dict[str, dict[str, object]], case: str):
    text = source(case)
    assert "error" not in mermaid[text]
    assert ours(text) == mermaid[text]


@pytest.mark.parametrize("case", [case for case in CASES if "img" in ours(source(case))])
def test_a_replaced_value_reads_back_with_every_line_in_place(
    mermaid: dict[str, dict[str, object]], case: str
):
    text = source(case)
    new = replaced(text)
    assert mermaid[new] == {**mermaid[text], "img": json.loads(REPLACEMENT)}
    assert new.count("\n") == text.count("\n")


@pytest.mark.parametrize(
    "text",
    [
        "flowchart LR\n" + "a@{ " * 50_000,
        "flowchart LR\n  a -- " + "@{ " * 50_000,
        "flowchart LR\n  a@{ x" + " " * 200_000 + "}\n",
    ],
    ids=["unclosed-shape-data", "unclosed-edge-text", "long-key"],
)
def test_reading_takes_one_pass(text: str):
    # Each of these took minutes when the scan restarted at every @{ or every space.
    start = time.perf_counter()
    list(shape_data.blocks(text))
    assert time.perf_counter() - start < 1


def test_an_escape_that_isnt_a_character_is_left_as_written():
    text = 'flowchart LR\n  a@{ label: "\\U00110000 \\ud800" }\n'
    (entries,) = shape_data.blocks(text)
    assert [(e.key, e.value) for e in entries] == [("label", "\\U00110000 \\ud800")]


def test_values_keep_their_place_in_the_source():
    text = 'flowchart LR\n  a@{ label: "a } b", img: "x.png" }\n  b@{\n    img: >-\n      y.png\n  }\n'
    first, second = shape_data.blocks(text)
    assert [(e.key, text[e.start : e.end], e.plain) for e in first] == [
        ("label", '"a } b"', False),
        ("img", '"x.png"', False),
    ]
    assert [(e.key, text[e.start : e.end], e.plain) for e in second] == [("img", ">-\n      y.png", False)]
