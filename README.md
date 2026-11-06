# Akceo

Build self-contained HTML slide decks from Markdown.

You write slides in one Markdown file and run one command. You get a single HTML file with every
image embedded in it. Large PNG, JPEG and WebP images are shrunk first. Mermaid `.mmd` diagrams
are checked at build time and drawn when the page opens, with a copy of Mermaid that akceo
includes, so there's nothing else to install. The file has no external assets, so it opens
straight from disk, works offline, and survives being emailed or copied anywhere.

## Install

Needs Python 3.12 or newer. Install the `akceo` command from PyPI with
[uv](https://docs.astral.sh/uv/) or [pipx](https://pipx.pypa.io/):

```sh
uv tool install akceo
pipx install akceo
```

To try changes that aren't released yet, install from the repository instead:

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
akceo check deck.md          # runs every check, diagrams included, and writes nothing
akceo check --json deck.md   # the same, with the result as JSON for agents and scripts
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

`examples/demo/deck.md` uses every layout and markup feature. See it built at
<https://lunarcommand.github.io/akceo/>. The same file is `examples/demo/deck.html`, which opens
straight from disk too. Build it yourself with `akceo build examples/demo/deck.md`.

## For AI agents

akceo comes with a guide for an AI agent that writes decks: the format, tips that work, and the
demo deck as an example.

```sh
akceo docs           # prints where the guide is
akceo docs --print   # prints the guide
akceo init           # points agents to it from AGENTS.md and CLAUDE.md in this folder
```

`akceo init` adds a short section to the end of `AGENTS.md` and `CLAUDE.md`, and creates either
file if it doesn't exist. The section tells an agent to read the guide before it starts and to run
`akceo check` after every edit. The rest of each file stays as it was, line endings included.
Running `init` again changes nothing, and `--dry-run` shows what it would do.

### The Claude Code plugin

This repository is also a Claude Code plugin marketplace. Its plugin, `akceo`, has a skill that
writes a deck with you: it asks for a brief, shows you an outline to approve, writes the deck,
runs `akceo check` until it passes, and builds the page. Call it as `/akceo:deck`, or ask Claude
for a deck. It needs the `akceo` command, and offers to install it if it's missing.

In a Claude Code session:

```
/plugin marketplace add LunarCommand/akceo
/plugin install akceo@akceo
```

The plugin changes with each akceo release. To get the new one, run
`/plugin marketplace update akceo`.

To try the skill from a branch, or to change it, add your clone instead. Claude Code runs the
skill from the checkout as it stands, and `/reload-plugins` picks up an edit:

```
/plugin marketplace add /absolute/path/to/akceo
/plugin install akceo@akceo
```

Use one or the other. Both add a marketplace named `akceo`, so to switch, first run
`/plugin uninstall akceo@akceo` and `/plugin marketplace remove akceo`.

The skill runs `akceo check`, `akceo build` and `akceo docs` many times, and Claude Code asks
before each one. To let them run without asking, merge these rules into
`~/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": ["Bash(akceo check:*)", "Bash(akceo build:*)", "Bash(akceo docs:*)"]
  }
}
```

## Layouts

| Layout | For | Content |
| --- | --- | --- |
| `title` | Opening and section slides | `#` heading, kicker, meta line |
| `bullets` | Most slides (the default) | `##` heading, lead, list, paragraph |
| `split` | A diagram with commentary | image, `##` heading, phases, lists, note |
| `steps` | A sequence | `##` heading, paragraph, numbered list |
| `table` | Comparisons | `##` heading, table |
| `image` | A diagram on its own | image, kicker, `##` heading, caption |

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

Releases are published to PyPI by pushing a version tag; [docs/RELEASING.md](docs/RELEASING.md)
has the steps.

## Branding

Akceo comes from the Latin *actio*, "the act of doing". The spelling ends in *ceo* to tie it to
the executives who give so many decks: executive action. The full naming rationale is in
[docs/branding.md](docs/branding.md). The domain is akceo.ai.

## License

MIT. See [LICENSE](LICENSE).
