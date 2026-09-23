# Akceo

Build self-contained HTML slide decks from Markdown.

You write slides in one Markdown file and run one command. You get a single HTML file with every
image embedded in it. Large PNG, JPEG and WebP images are shrunk first. The file has no external
assets, so it opens straight from disk, works offline, and survives being emailed or copied
anywhere.

## Install

Needs Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```sh
uv tool install git+https://github.com/LunarCommand/akceo
```

To work on akceo itself, install your checkout in editable mode so the `akceo` command always
runs your latest source:

```sh
git clone https://github.com/LunarCommand/akceo.git
uv tool install --editable ./akceo
```

## Quickstart

Write `deck.md`:

```markdown
title: Q3 Review
theme: midnight

---

layout: title
kicker: Q3 review
meta: Platform team · September 2026

# Shipping faster

---

kicker: The problem

## Builds take too long

- **Full rebuilds** on every change.
- CI queues back up at ==peak hours==.
```

Build it:

```sh
akceo build deck.md          # writes deck.html next to deck.md
akceo build deck.md -o talk.html --theme paper
```

Open `deck.html` in a browser to present:

| Key | Action |
| --- | --- |
| `→`, `Space`, `PageDown`, click right half | Next slide |
| `←`, `PageUp`, click left half | Previous slide |
| `Home`, `End` | First, last slide |
| `F` | Toggle full screen |

A click while text is selected doesn't change slides, so you can copy text from a slide.

The address bar shows the current slide as `#N`, so `deck.html#4` opens on slide 4 and a reload
stays on the slide you were on.

`examples/demo/deck.md` uses every layout and markup feature. Build it with
`akceo build examples/demo/deck.md`.

## Layouts

| Layout | For | Content |
| --- | --- | --- |
| `title` | Opening and section slides | `#` heading, kicker, meta line |
| `bullets` | Most slides (the default) | `##` heading, lead, list, paragraph |
| `split` | A diagram with commentary | image, `##` heading, phases, lists, note |
| `steps` | A sequence | `##` heading, paragraph, numbered list |
| `table` | Comparisons | `##` heading, table |
| `image` | A diagram on its own | image, kicker |

The full format is in [docs/syntax.md](docs/syntax.md). It covers config keys, slide keys, blocks
and inline markup.

## Themes

```sh
akceo themes                          # list the built-in themes
akceo build deck.md --theme paper     # a built-in theme
akceo build deck.md --theme brand.css # your own theme
```

A deck can also set `theme:` in its config block. The `--theme` flag overrides it.

`midnight` (dark, the default) and `paper` (light) are built in. A custom theme is a CSS file
that sets akceo's color and font tokens. The simplest start is a copy of
[`src/akceo/themes/midnight.css`](src/akceo/themes/midnight.css). The token list is in
[docs/syntax.md](docs/syntax.md#themes).

## Speaker notes

Keep your notes in a Markdown file and read them in a second browser tab, while you share only
the deck tab in your call.

```sh
akceo viewer    # writes md-viewer.html into the current folder
```

Open `md-viewer.html` next to your deck, for example with Chrome's split view, and open your
notes file in it. In Chrome and Edge it refreshes by itself when you save the notes.
`examples/demo/speaker-notes.md` goes with the demo deck. The setup is in
[docs/speaker-notes.md](docs/speaker-notes.md).

## How it works

[docs/how-it-works.md](docs/how-it-works.md) explains Akceo at three levels: in plain terms,
from the user's side, and under the hood. It has diagrams of the build pipeline, the data model
and the notes viewer.

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pre-commit install   # optional: run these checks on every commit
```

## Branding

Akceo comes from the Latin *actio*, "the act of doing". The spelling ends in *ceo* to tie it to
the executives who give so many decks: executive action. The full naming rationale is in
[docs/branding.md](docs/branding.md). The domain is akceo.ai.

## License

MIT. See [LICENSE](LICENSE).
