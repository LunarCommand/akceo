import json
import subprocess
import sys

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
    'a@{ w: "60", img: x.png }',
    "a@{ w: 50.5, h: 20, img: x.png }",
    "a@{ img:shot.png }",
    'a@{ "img":"x.png" }',
    'a@{ "img": \'y.png\', "w": 12 }',
    "a@{ img : x.png , w : 7 }",
    "a@{ img: 'a, b.png' }",
    "a@{\n    img: my shot.png#crop=1,2,3,4\n    w: 40\n  }",
    "a@{\n    img: >-\n      folded.png\n    h: 30\n  }",
    "a@{\n    img: >\n      folded.png\n  }",
    "a@{\n    img: |\n      lit.png\n  }",
    'a@{\n    img:\n      "next.png"\n  }',
    "a@{\n    img: my\n      shot.png\n  }",
    "a@{\n    # a comment\n    img: x.png # note\n    label: >\n      img: no.png\n  }",
    'a@{\n    label: "L"\n    img: "x.png"\n    h: 20\n  }',
]
REPLACEMENT = '"data:image/png;base64,AAAA"'


def source(case: str) -> str:
    return f"flowchart LR\n  {case}\n"


def ours(text: str) -> dict[str, object]:
    """What the reader finds for a's img, w and h, with sizes as numbers, as Mermaid gives them."""
    (entries,) = shape_data.blocks(text)
    found: dict[str, object] = {}
    for entry in entries:
        if entry.key == "img":
            found["img"] = entry.value
        elif entry.key in ("w", "h"):
            found[entry.key] = float(entry.value)
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


def test_values_keep_their_place_in_the_source():
    text = 'flowchart LR\n  a@{ label: "a } b", img: "x.png" }\n  b@{\n    img: >-\n      y.png\n  }\n'
    first, second = shape_data.blocks(text)
    assert [(e.key, text[e.start : e.end], e.plain) for e in first] == [
        ("label", '"a } b"', False),
        ("img", '"x.png"', False),
    ]
    assert [(e.key, text[e.start : e.end], e.plain) for e in second] == [("img", ">-\n      y.png", False)]
