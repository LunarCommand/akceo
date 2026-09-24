# Vendored Mermaid

`mermaid.min.js` is the browser build of [Mermaid](https://mermaid.js.org), taken from the npm
package. akceo uses it twice:

- At build time, `akceo.mermaid` runs its `parse()` in V8 (through mini-racer) to check each `.mmd`
  diagram, so syntax errors stop the build.
- In the built page, it draws each diagram as inline SVG when the deck opens.

`manifest.json` records the version, the tarball it came from, npm's integrity hash, the lockfile
the notices come from, and the SHA-256 of the file here. A test checks the file against that SHA-256.

## Licenses

Mermaid is MIT licensed; see `LICENSE`. The file also bundles other packages, listed with their
license texts in `THIRD_PARTY_NOTICES`. The list comes from `pnpm-lock.yaml` in Mermaid's
repository at the release tag, the lockfile the bundle was built from, so each version matches the
bundle. It covers Mermaid's production dependencies, optional ones included, plus the
devDependencies that the linked workspace package `@mermaid-js/parser` compiles into its own output,
such as langium.

Not covered yet: Mermaid's own devDependencies (about 40). If esbuild inlines one of them into the
bundle, it is missing from the notices, and the script doesn't notice.

One bundled package, elkjs, is EPL-2.0, which asks that recipients be told where its source is:
https://github.com/kieler/elkjs. Every built deck that has a diagram carries the notices, and that
line, in a comment.

## The one change from upstream

A raw control character inside a string literal is replaced with its `\xNN` escape. JavaScript reads
both forms the same way, but a raw control character is unsafe in an HTML page, and a test checks
that the packaged assets carry none. `manifest.json` records how many were escaped.

## Updating

```sh
uv run python scripts/update_mermaid.py 12.0.0   # the new version
uv run pytest
```

The script downloads the tarball, checks it against npm's integrity hash, applies the change above
and builds the notices by downloading each locked package and checking it against the lockfile's
integrity hash. It writes the folder only after every step succeeds, so a failed update leaves it
as it was. It stops, and writes nothing, when:

- a linked workspace package (today only `@mermaid-js/parser`) has a devDependency the script
  hasn't sorted. Check whether that package ends up in `mermaid.min.js`, then add it to
  `BUNDLED_DEV_DEPENDENCIES` or `BUILD_ONLY_DEV_DEPENDENCIES` in the script.
- the walk misses a package the bundle certainly holds (`ANCHOR_PACKAGES`), which means the
  lockfile's layout has changed under the script's reader.
- a package has no license file. Find its copyright notice, then add it to `NO_LICENSE_FILE`.

Then run the full test suite: `tests/test_mermaid.py` runs the real parser, so a Mermaid release
that no longer works with the stand-ins in `assets/mermaid-shims.js` fails there. Build
`examples/demo/deck.md` and look at the diagram slide too, since drawing isn't covered by the tests.
