# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

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
  outside the file. A web font or `@import` in a custom theme no longer loads; use installed
  fonts, or embed one as a `data:` URI.
- `akceo check deck.md` runs every check a build runs, diagrams included, without writing a file.
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
