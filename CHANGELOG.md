# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Links: `[text](url)` in any slide text. A link goes to an `https:`, `http:` or `mailto:`
  address, always in a new tab, or to a slide in the deck as `#N`. Anything else, or a link to
  a slide that doesn't exist, stops the build. Clicking a link follows it without changing the
  slide.
- Three theme tokens style links: `--link`, `--link-hover` and `--link-underline`. Both built-in
  themes set them. A custom theme needs them only for a deck that has links; without them, that
  deck's build stops and names the missing ones.
- `image-crop: left, top, right, bottom` on split and image slides keeps only that part of a
  PNG, JPEG or WebP image, in pixels, before it's shrunk to `image-max`. A crop past the image's
  edge stops the build and gives the image's size.
- An image shape in a Mermaid diagram can name an image file: `img: "screenshot.png"`, relative
  to the `.mmd` file. The build puts it into the diagram as a `data:` URI, so it no longer has
  to be pasted in as base64. When the node sets `w` or `h`, the image is shrunk to twice that.
  `#crop=` and `#max=` after the path crop or size it. A missing file stops the build with the
  diagram's line, and a diagram that its images push over Mermaid's 50,000-character limit
  stops with how much each image uses (#21).
- A guide for AI agents that write decks comes with akceo: the format, tips, and the demo deck
  as an example. `akceo docs` prints where it is, and `akceo docs --print` prints it.
- `akceo init` adds a section to the end of `AGENTS.md` and `CLAUDE.md` in a folder, creating
  them if needed, that tells an agent to read the guide and to run `akceo check` after every
  edit. The rest of each file stays as it was. A second run changes nothing, `--dry-run` shows
  what it would do, and a file that links outside the folder is left alone.
- Three config keys for a deck published on the web: `description:` and `url:` add the tags
  that search engines and link previews read, and `icon:` builds an image into the page as its
  browser-tab icon. A `url:` that isn't a full `https://` or `http://` address stops the build.
- `akceo check --json` prints the result as JSON, for agents and scripts: whether the deck is
  fine, how many slides it has, or the problem with its file, line and slide. Every kind of problem
  has a code that never changes, such as `block-missing` or `diagram-syntax`, listed in
  `docs/syntax.md`.

### Changed

- An error about a slide's content, or about a link in it, names the line where that block
  starts, not the slide's first line.
- An error about the deck's `theme:` or `icon:` names that key's line in the config block.
- `image-max` takes a whole number of at most nine digits 0-9. Other digits, such as full-width
  ones, and longer numbers used to be accepted and now stop the build.

### Fixed

- The key hint in the corner of the deck was hard to read. It used `--line`, which in both
  built-in themes is close to the background. It now uses `--muted`, like the slide count.
- A control character in a deck, such as a stray NUL, stops the build with its line. It
  used to crash with a Python traceback, or put invisible characters on the slide.
- Ctrl-C during a command prints `akceo: interrupted` and exits with code 130, instead of
  a Python traceback.
- An `image-max` with a digit outside ASCII, such as `8²`, or with thousands of digits, stops
  the build with a message. It used to crash with a Python traceback.
- An image that Pillow can't process stops the build with a message naming it, such as a PNG or
  WebP with damaged EXIF data, a 16-bit grayscale PNG shrunk four times or more, or a file that
  declares a huge size. These used to crash with a Python traceback.
- An image or diagram whose file name is too long for the system is reported as not found. It
  used to crash with a Python traceback.
- The diagram check takes each image node's `img:` from Mermaid's own reading of the diagram.
  Text that only looks like one, such as `img: https://…` inside a label, no longer stops the
  build as an outside image, and an image the old scan missed, such as one after a `}` inside a
  quoted label, now stops it.

## [0.2.1] - 2026-10-30

### Fixed

- An image node in a diagram, whose `img:` is a `data:` URI, shows its image again. The page
  dropped the link from every image in a drawn diagram, so the node drew as an empty box. It
  now keeps a `data:` image and still drops any other link that would leave the deck. Broken
  since 0.1.0.

## [0.2.0] - 2026-10-30

### Added

- The `image` layout takes an optional `##` heading above the image and a paragraph under it,
  shown as a caption. `style-h2` and `style-sub` apply to them.
- The demo deck, built, is online at <https://lunarcommand.github.io/akceo/> and kept in the
  repository as `examples/demo/deck.html`, so you can see akceo's output without installing it.

### Changed

- Mermaid is embedded compressed, and the page unpacks it when it opens: a deck with a diagram
  grows by about 2.4 MB instead of 5.8 MB. It still opens straight from disk. Opening it needs
  Chrome or Edge 98, Firefox 113 or Safari 16.4, or newer.

## [0.1.0] - 2026-09-24

The first release.

### Added

- Published on PyPI: `uv tool install akceo` or `pipx install akceo`.
- `akceo build` renders a Markdown deck into one self-contained HTML file.
- `akceo themes` lists the built-in themes.
- Six layouts: `title`, `bullets`, `split`, `steps`, `table` and `image`.
- Built-in `midnight` and `paper` themes. Custom themes are CSS files that set akceo's tokens.
- PNG, JPEG and WebP images are shrunk and embedded; SVG is embedded as-is.
- Mermaid diagrams: `image: flow.mmd` is drawn as SVG when the page opens. akceo includes
  Mermaid, so there's nothing else to install. The build checks each diagram with Mermaid's own
  parser and stops on a syntax error, naming the line in the `.mmd` file. It also stops on a
  diagram that would load or link to anything outside the deck, and on one longer than Mermaid's
  50,000-character limit. A deck with a diagram grows by about 5.6 MB.
- The built page carries a Content-Security-Policy, so the browser refuses to load anything from
  outside the file. A web font or `@import` in a custom theme doesn't load; use installed fonts,
  or embed one as a `data:` URI.
- `akceo check deck.md` runs every check a build runs, diagrams included, without writing a file.
- Per-slide style overrides: `style-h1`, `style-h2`, `style-lead`, `style-ul`, `style-ol` and
  `style-sub` add inline CSS to that element, for one-off spacing fixes. They can't reference
  files or URLs.
- `image-frame: no`, for the whole deck or one slide, drops the white panel behind images.
  Mermaid diagrams without a frame are drawn in the deck theme's colors.
- Deck errors name the file, line and slide; theme and image errors name the file. Content a
  layout doesn't use is reported with the list of what that layout takes.
- The URL hash tracks the current slide: `deck.html#4` opens slide 4, and a reload stays put.
- Author notes: a line starting with `//` is dropped from the page, so reminders can sit next to
  the slide they're about.
- A `split` slide with no `image:` line builds with a dashed placeholder box, so a slide can be
  set up before its image exists.
- `akceo viewer` writes `md-viewer.html`, a speaker-notes viewer for a second browser tab. In
  Chrome and Edge it refreshes live when the notes file changes.
- Example speaker notes for the demo deck.
- Docs: the speaker-notes setup, and how Akceo works (plain terms, user experience, internals),
  with Mermaid diagrams.
