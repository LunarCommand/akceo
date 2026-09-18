# CLAUDE.md

Akceo is a CLI that renders a Markdown deck into one self-contained HTML file. Pillow is the only
runtime dependency.

## Layout

- `src/akceo/parse.py`: the Markdown dialect into a validated `Deck`. All input checks live here.
- `src/akceo/render.py`: slides to HTML, inline markup, page assembly.
- `src/akceo/images.py`: image files to data URIs.
- `src/akceo/themes.py`: theme lookup and the token check.
- `src/akceo/cli.py`: the `akceo` command.
- `src/akceo/assets/`: the page template, `base.css` (layout rules; all colors and fonts come from
  theme tokens), and `deck.js` (navigation).
- `src/akceo/themes/`: built-in themes, one CSS file each. The first-line comment is the
  description `akceo themes` prints.
- `examples/demo/`: a deck that uses every layout. The end-to-end test builds it.

## Commands

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run akceo build examples/demo/deck.md
```

## Rules

- The built HTML must not reference any external file or URL.
- `docs/syntax.md` is the format reference. Update it in the same change as any parser, renderer
  or token change.
- A new theme token goes in `themes.TOKENS`, every built-in theme, and `docs/syntax.md`.
- Keep the `Unreleased` section of `CHANGELOG.md` current.
