# Vendored Mermaid

`mermaid.min.js` is the browser build of [Mermaid](https://mermaid.js.org), taken from the npm
package. akceo uses it twice:

- At build time, `akceo.mermaid` runs its `parse()` in V8 (through mini-racer) to check each `.mmd`
  diagram, so syntax errors stop the build.
- In the built page, it draws each diagram as inline SVG when the deck opens.

`manifest.json` records the version, the tarball it came from, npm's integrity hash and the SHA-256
of the file here. A test checks the file against that SHA-256.

## Licenses

Mermaid is MIT licensed; see `LICENSE`. The file also bundles other packages, listed with their
license texts in `THIRD_PARTY_NOTICES`. One of them, elkjs, is EPL-2.0, which asks that recipients
be told where its source is: https://github.com/kieler/elkjs. Every built deck that has a diagram
carries a comment saying so.

## The one change from upstream

A raw control character inside a string literal is replaced with its `\xNN` escape. JavaScript reads
both forms the same way, but a raw control character is unsafe in an HTML page, and a test checks
that the packaged assets carry none. `manifest.json` records how many were escaped.

## Updating

```sh
uv run python scripts/update_mermaid.py 12.0.0   # the new version; needs npm for the notices
uv run pytest
```

The script downloads the tarball, checks it against npm's integrity hash, applies the change above
and rewrites every file in this folder. Then run the full test suite: `tests/test_mermaid.py` runs
the real parser, so a Mermaid release that no longer works with the stand-ins in
`assets/mermaid-shims.js` fails there. Build `examples/demo/deck.md` and look at the diagram slide
too, since drawing isn't covered by the tests.
