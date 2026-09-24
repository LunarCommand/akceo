# CLAUDE.md

Akceo is a CLI that renders a Markdown deck into one self-contained HTML file. The runtime
dependencies are Pillow (images) and mini-racer (V8, to check Mermaid diagrams at build time).

## Layout

- `src/akceo/parse.py`: the Markdown dialect into a validated `Deck`. All input checks live here.
- `src/akceo/render.py`: slides to HTML, inline markup, page assembly.
- `src/akceo/images.py`: image files to data URIs.
- `src/akceo/mermaid.py`: the build-time diagram check, the theme's Mermaid config, and the
  vendored Mermaid script with its license notices, ready for the page.
- `src/akceo/themes.py`: theme lookup and the token check.
- `src/akceo/files.py`: reads user-supplied text files, turning read failures into `DeckError`.
- `src/akceo/cli.py`: the `akceo` command.
- `src/akceo/assets/`: the page template, `base.css` (layout rules; all colors and fonts come from
  theme tokens), `deck.js` (navigation), `diagrams.js` (draws Mermaid diagrams in the page),
  `mermaid-shims.js` (browser stand-ins for the build-time check), and `md-viewer.html` (the
  standalone speaker-notes viewer that `akceo viewer` writes out).
- `src/akceo/assets/vendor/mermaid/`: Mermaid, vendored. Never edit it by hand; run
  `scripts/update_mermaid.py` (see the README there).
- `src/akceo/themes/`: built-in themes, one CSS file each. The first-line comment is the
  description `akceo themes` prints.
- `examples/demo/`: a deck that uses every layout, and its speaker notes. The end-to-end test
  builds the deck.
- `docs/`: `syntax.md` (format reference), `speaker-notes.md` (notes setup), `how-it-works.md`
  (design, with Mermaid diagrams), `branding.md`.

## Commands

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run akceo build examples/demo/deck.md
uv run akceo check examples/demo/deck.md
```

## Rules

- The built HTML must not reference any external file or URL.
- `docs/syntax.md` is the format reference. Update it in the same change as any parser, renderer
  or token change.
- A new theme token goes in `themes.TOKENS`, every built-in theme, and `docs/syntax.md`.
- `docs/how-it-works.md` describes the modules and pipeline. Update it when either changes.
- Keep JavaScript escapes such as `\u0000` as text in the assets. A raw control character breaks
  the page, and a test checks for it.
- The vendored Mermaid is excluded from the external-reference test and has its own narrower
  check. Everything else in the page must pass the full one.
- Keep the `Unreleased` section of `CHANGELOG.md` current.
