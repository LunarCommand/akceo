import textwrap
from pathlib import Path

import pytest

from akceo.errors import DeckError
from akceo.parse import BREAK, Block, Deck, load, parse


def deck(text: str) -> Deck:
    return parse(textwrap.dedent(text).lstrip("\n"), Path("deck.md"))


def test_config_and_slides():
    d = deck("""
        title: My Talk
        theme: paper

        ---

        layout: title
        kicker: Hello

        # Welcome

        ---

        ## Plain slide
    """)
    assert d.config == {"title": "My Talk", "theme": "paper"}
    assert d.title == "My Talk"
    assert [s.layout for s in d.slides] == ["title", "bullets"]
    assert d.slides[0].meta["kicker"] == "Hello"
    assert d.slides[0].blocks == (Block("h1", text="Welcome"),)
    assert [s.number for s in d.slides] == [1, 2]


def test_title_defaults_to_file_stem():
    assert deck("---\n## Slide\n").title == "deck"


def test_trailing_separator_and_blank_chunks_are_not_slides():
    assert len(deck("---\n## One\n---\n\n---\n## Two\n---\n").slides) == 2


def test_slide_line_is_its_first_non_blank_line():
    d = deck("title: T\n\n---\n\nlayout: bullets\n\n## A\n")
    assert d.slides[0].line == 5


def test_every_block_kind():
    d = deck("""
        ---
        layout: split
        image: x.png

        ## Heading
        ### ingest
        land raw payloads
        - one
        - two
        *a note*
    """)
    assert d.slides[0].blocks == (
        Block("h2", text="Heading"),
        Block("phase", text="ingest", body="land raw payloads"),
        Block("ul", items=("one", "two")),
        Block("note", text="a note"),
    )

    d = deck("""
        ---
        layout: steps

        ## Steps
        Intro line one
        and line two.

        1. first
        2. second
    """)
    assert d.slides[0].blocks == (
        Block("h2", text="Steps"),
        Block("para", text="Intro line one and line two."),
        Block("ol", items=("first", "second")),
    )

    d = deck("""
        ---
        ## Lead slide

        > part one
        > part two
    """)
    assert d.slides[0].blocks[1] == Block("lead", text="part one part two")


def test_indent_continues_a_line_and_backslash_breaks_it():
    d = deck("""
        ---
        ## Two\\
        lines

        - a long item
          that wraps
    """)
    assert d.slides[0].blocks == (
        Block("h2", text="Two" + BREAK + "lines"),
        Block("ul", items=("a long item that wraps",)),
    )


def test_table_rows_skip_gfm_delimiter():
    d = deck("""
        ---
        layout: table

        ## T

        | A | B |
        | --- | :---: |
        | 1 | 2 |
    """)
    assert d.slides[0].blocks[1] == Block("table", rows=(("A", "B"), ("1", "2")))


@pytest.mark.parametrize(
    ("row", "cells"),
    [
        ("| a | b |", ("a", "b")),
        ("| `a|b` | c |", ("`a|b`", "c")),
        (r"| a \| b | c |", ("a | b", "c")),
        ("| `unclosed | c |", ("`unclosed", "c")),
        ("|| b |", ("", "b")),
    ],
)
def test_table_cells(row: str, cells: tuple[str, ...]):
    table = deck(f"---\nlayout: table\n\n## T\n{row}\n").slides[0].first("table")
    assert table is not None
    assert table.rows[0] == cells


def test_phase_description_is_optional():
    d = deck("""
        ---
        layout: split
        image: x.png

        ## A
        ### named only
        - a list, not a description
        ### blank after

        ### with body
        the description
        ### before a note
        *the note*
    """)
    assert d.slides[0].blocks == (
        Block("h2", text="A"),
        Block("phase", text="named only"),
        Block("ul", items=("a list, not a description",)),
        Block("phase", text="blank after"),
        Block("phase", text="with body", body="the description"),
        Block("phase", text="before a note"),
        Block("note", text="the note"),
    )


def test_paragraph_starting_like_a_block_marker_terminates():
    # "-5" matches no block rule, so the paragraph rule must still consume it or the parser stops advancing.
    d = deck("---\n## Weather\n\n-5 degrees overnight\n")
    assert d.slides[0].blocks[1] == Block("para", text="-5 degrees overnight")


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("diagrams: ../x\n---\n## A\n", "deck.md:1: unknown config key 'diagrams'"),
        ("title: T\nstray text\n---\n## A\n", "deck.md:1: the config block may only hold key: value lines"),
        ("title: T\n", "deck.md: the deck has no slides"),
        ("---\nlayout: grid\n\n## A\n", "deck.md:2: slide 1: unknown layout 'grid'"),
        ("---\nkicker: K\nimgae: x.png\n\n## A\n", "deck.md:3: slide 1: unknown key 'imgae'"),
        (
            "---\nlayout: bullets\nimage: x.png\n\n## A\n",
            "deck.md:3: slide 1: 'image' only applies to the split",
        ),
        ("---\nlayout: table\ndim-last-column: true\n\n## A\n| a |\n", "must be yes or no, not 'true'"),
        (
            "---\nlayout: split\nimage: x.png\nimage-max: big\n\n## A\n",
            "'image-max' must be a positive whole",
        ),
        (
            "---\nkicker: K\nstyle-h2: background:URL (https://x.test/a.png)\n\n## A\n",
            "deck.md:3: slide 1: 'style-h2' can't reference files or URLs",
        ),
        (
            '---\nstyle-lead: background-image:image-set("a.png" 1x)\n\n## A\n',
            "deck.md:2: slide 1: 'style-lead' can't reference files or URLs",
        ),
        (
            "---\n## A\n\n| a | b |\n",
            "slide 1: a | table isn't used by the bullets layout, which takes a ## heading, "
            "a > lead, a - list and a paragraph",
        ),
        (
            "---\nlayout: table\n\n## A\n| a | b |\n\nClosing words.\n",
            "a paragraph isn't used by the table layout, which takes a ## heading and a | table",
        ),
        ("---\nlayout: title\n\n## A\n", "isn't used by the title layout, which takes a # heading"),
        ("---\n## A\n\n- one\n\nMiddle.\n\n- two\n", "the bullets layout takes only one - list"),
        ("---\nlayout: steps\n\n## A\n\nNo list.\n", "the steps layout needs a 1. list"),
        ("---\n- no heading\n", "the bullets layout needs a ## heading"),
        ("---\n## One\n---\n## Two\n\n# Big\n", "deck.md:4: slide 2: a # heading isn't used"),
    ],
)
def test_errors_name_line_and_slide(source: str, message: str):
    with pytest.raises(DeckError) as e:
        parse(source, Path("deck.md"))
    assert message in str(e.value)


def test_non_utf8_deck_names_the_line(tmp_path: Path):
    (tmp_path / "deck.md").write_bytes(b"---\n## A\n\xff\n")
    with pytest.raises(DeckError, match=r"deck\.md:3: not valid UTF-8 text"):
        load(tmp_path / "deck.md")


def test_split_allows_repeated_phases_and_lists():
    d = deck("""
        ---
        layout: split
        image: x.png

        ## A
        - one
        ### p1
        body 1
        - two
        ### p2
        body 2
    """)
    assert [b.kind for b in d.slides[0].blocks] == ["h2", "ul", "phase", "ul", "phase"]


def test_author_notes_are_dropped_everywhere():
    d = deck("""
        // config note
        title: T
        // between config keys

        // after a blank line
        ---
        // before the header
        layout: bullets
        // among header lines
        kicker: K

        ## A
        // between heading and list
        - one
        // between items
        - two
          // indented under an item
        - three

        Closing
        // inside a paragraph
        words.
    """)
    assert d.config == {"title": "T"}
    slide = d.slides[0]
    assert slide.meta == {"layout": "bullets", "kicker": "K"}
    assert slide.blocks == (
        Block("h2", text="A"),
        Block("ul", items=("one", "two", "three")),
        Block("para", text="Closing words."),
    )


def test_author_notes_keep_error_line_numbers():
    with pytest.raises(DeckError, match=r"deck\.md:5: slide 1: unknown key 'imgae'"):
        parse("---\n// a\nkicker: K\n// b\nimgae: x.png\n\n## A\n", Path("deck.md"))
    assert deck("---\n// note\n\n## A\n").slides[0].line == 4


def test_a_chunk_of_only_author_notes_is_not_a_slide():
    d = deck("---\n## One\n---\n// the pricing slide goes here\n---\n## Two\n")
    assert [s.first("h2") for s in d.slides] == [Block("h2", text="One"), Block("h2", text="Two")]


def test_split_without_an_image_parses():
    d = deck("---\nlayout: split\nimage-wide: yes\n\n## Diagram to come\n- a point\n")
    assert "image" not in d.slides[0].meta


def test_image_layout_takes_image_keys_and_no_content():
    d = deck("---\nlayout: image\nkicker: K\nimage: x.png\nimage-alt: A\nimage-max: 800\n")
    assert d.slides[0].layout == "image"
    assert d.slides[0].blocks == ()
    assert deck("---\nlayout: image\n").slides[0].meta == {"layout": "image"}


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            "---\nlayout: image\n\n## A\n",
            "a ## heading isn't used by the image layout, which takes no content",
        ),
        ("---\nlayout: image\nimage-wide: yes\n", "'image-wide' only applies to the split layout"),
        ("---\nimage: x.png\n\n## A\n", "'image' only applies to the split and image layouts"),
    ],
)
def test_image_layout_errors(source: str, message: str):
    with pytest.raises(DeckError) as e:
        parse(source, Path("deck.md"))
    assert message in str(e.value)


def test_image_frame_comes_from_the_slide_then_the_deck():
    d = deck("""
        image-frame: no
        ---
        layout: image
        ---
        layout: split
        image-frame: yes

        ## A
    """)
    assert [d.framed(s) for s in d.slides] == [False, True]
    assert deck("---\nlayout: image\n").framed(deck("---\nlayout: image\n").slides[0])


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("image-frame: off\n---\n## A\n", "deck.md:1: 'image-frame' must be yes or no, not 'off'"),
        ("---\nlayout: image\nimage-frame: 0\n", "'image-frame' must be yes or no, not '0'"),
        ("---\nimage-frame: no\n\n## A\n", "'image-frame' only applies to the split and image layouts"),
    ],
)
def test_image_frame_errors(source: str, message: str):
    with pytest.raises(DeckError) as e:
        parse(source, Path("deck.md"))
    assert message in str(e.value)
