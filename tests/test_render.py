import textwrap
from pathlib import Path

from akceo.parse import BREAK, parse
from akceo.render import inline, render_slide


def slide_html(text: str, image_src: str = "") -> str:
    deck = parse("---\n" + textwrap.dedent(text).lstrip("\n"), Path("deck.md"))
    return render_slide(deck.slides[0], image_src)


def test_inline_markup():
    assert inline("**b**") == "<b>b</b>"
    assert inline("***s***") == '<b class="strong">s</b>'
    assert inline("==hi==") == '<span class="hl">hi</span>'
    assert inline("((aside))") == '<span class="dim">(aside)</span>'
    assert inline("a" + BREAK + "b") == "a<br>b"


def test_inline_escapes_html_and_protects_code():
    assert inline("<b> & ≥") == "&lt;b&gt; &amp; &ge;"
    assert inline("`**x** <y>`") == "<code>**x** &lt;y&gt;</code>"
    assert inline("`a` and **b**") == "<code>a</code> and <b>b</b>"


def test_title_slide():
    html = slide_html("""
        layout: title
        kicker: Hello
        meta: A subtitle

        # Big ==Title==
    """)
    assert html == "\n".join(
        [
            '  <section class="slide title-wrap">',
            '    <div class="kicker">Hello</div>',
            '    <h1>Big <span class="hl">Title</span></h1>',
            '    <div class="rule"></div>',
            '    <div class="meta">A subtitle</div>',
            "  </section>",
        ]
    )


def test_title_slide_without_kicker_or_meta():
    html = slide_html("layout: title\n\n# Only a title\n")
    assert "kicker" not in html
    assert 'class="meta"' not in html


def test_bullets_slide():
    html = slide_html("""
        kicker: K
        style-lead: max-width:40ch

        ## Heading
        > The lead
        - one
        - two

        Closing words.
    """)
    assert html == "\n".join(
        [
            '  <section class="slide">',
            '    <div class="kicker">K</div>',
            "    <h2>Heading</h2>",
            '    <p class="lead" style="max-width:40ch">The lead</p>',
            "    <ul>",
            "      <li>one</li>",
            "      <li>two</li>",
            "    </ul>",
            '    <p class="sub">Closing words.</p>',
            "  </section>",
        ]
    )


def test_split_slide_renders_blocks_in_order_and_note_last():
    html = slide_html(
        """
        layout: split
        image: fig.png
        image-wide: yes
        image-alt: A "quoted" <figure>

        ## Heading
        *the note*
        ### first
        body one
        - item
    """,
        image_src="data:image/png;base64,AAAA",
    )
    assert '<div class="split img-wide">' in html
    assert '<img src="data:image/png;base64,AAAA" alt="A &quot;quoted&quot; &lt;figure&gt;">' in html
    phase = html.index('<div class="phase"><h3>first</h3><p>body one</p></div>')
    item = html.index("<li>item</li>")
    note = html.index('<p class="note-inline">the note</p>')
    assert phase < item < note


def test_split_slide_puts_kicker_in_the_text_column():
    html = slide_html("layout: split\nimage: x.png\nkicker: K\n\n## A\n")
    assert html.count('<div class="kicker">K</div>') == 1
    assert '<div>\n        <div class="kicker">K</div>\n        <h2>A</h2>' in html


def test_split_slide_without_an_image_shows_a_placeholder():
    html = slide_html("layout: split\nimage-wide: yes\n\n## A\n")
    assert '<div class="split img-wide">' in html
    assert '<div class="figwrap"><div class="placeholder"></div></div>' in html
    assert "<img" not in html


def test_phase_without_description_has_no_empty_paragraph():
    html = slide_html("layout: split\nimage: x.png\n\n## A\n### solo\n")
    assert '<div class="phase"><h3>solo</h3></div>' in html


def test_steps_slide():
    html = slide_html("""
        layout: steps
        style-sub: margin-top:0

        ## Steps
        Intro.
        1. first
        2. second
    """)
    assert '    <p class="sub" style="margin-top:0">Intro.</p>' in html
    assert '    <ol class="steps">\n      <li>first</li>\n      <li>second</li>\n    </ol>' in html


def test_table_slide_dims_last_column_only_when_asked():
    source = """
        layout: table
        {flag}

        ## T
        | Name | Cost |
        | **a** | high |
    """
    plain = slide_html(source.format(flag=""))
    dimmed = slide_html(source.format(flag="dim-last-column: yes"))
    assert "<thead><tr><th>Name</th><th>Cost</th></tr></thead>" in plain
    assert "<tr><td><b>a</b></td><td>high</td></tr>" in plain
    assert '<tr><td><b>a</b></td><td class="dim">high</td></tr>' in dimmed


def test_style_values_are_attribute_escaped():
    html = slide_html('style-h2: font-family:"Serif"\n\n## H\n')
    assert '<h2 style="font-family:&quot;Serif&quot;">H</h2>' in html


def test_image_slide_keeps_the_kicker_at_the_top():
    html = slide_html('layout: image\nkicker: K\nimage: x.png\nimage-alt: A "b"\n', image_src="data:x")
    assert html == "\n".join(
        [
            '  <section class="slide">',
            '    <div class="kicker">K</div>',
            '    <div class="figure-full"><img src="data:x" alt="A &quot;b&quot;"></div>',
            "  </section>",
        ]
    )


def test_image_slide_without_an_image_shows_a_placeholder():
    html = slide_html("layout: image\n")
    assert '<div class="figure-full"><div class="placeholder"></div></div>' in html


def test_an_unframed_image_is_bare_and_a_placeholder_is_unchanged():
    html = render_slide(
        parse("---\nlayout: image\nimage: x.png\n", Path("deck.md")).slides[0], "data:x", False
    )
    assert '<img class="bare" src="data:x" alt="">' in html
    assert "bare" not in render_slide(parse("---\nlayout: image\n", Path("deck.md")).slides[0], "", False)


def test_a_diagram_carries_its_escaped_source_for_the_page_to_draw():
    slide = parse('---\nlayout: split\nimage: f.mmd\nimage-alt: A "b"\n\n## H\n', Path("deck.md")).slides[0]
    framed = render_slide(slide, framed=True, diagram="flowchart LR\n  a --> b[<x> & y]\n")
    assert (
        '<div class="figwrap"><div class="diagram" role="img" aria-label="A &quot;b&quot;" '
        'data-mermaid="default"><pre class="diagram-src">flowchart LR\n  a --&gt; b[&lt;x&gt; &amp; y]\n'
        "</pre></div></div>"
    ) in framed
    assert "<img" not in framed
    bare = render_slide(slide, framed=False, diagram="flowchart LR\n")
    assert '<div class="diagram bare" role="img" aria-label="A &quot;b&quot;" data-mermaid="theme">' in bare
