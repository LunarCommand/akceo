# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `akceo build` renders a Markdown deck into one self-contained HTML file.
- `akceo themes` lists the built-in themes.
- Five layouts: `title`, `bullets`, `split`, `steps` and `table`.
- Built-in `midnight` and `paper` themes. Custom themes are CSS files that set akceo's tokens.
- PNG, JPEG and WebP images are shrunk and embedded; SVG is embedded as-is.
- Deck errors name the file, line and slide; theme and image errors name the file. Content a
  layout doesn't use is reported with the list of what that layout takes.
- The URL hash tracks the current slide: `deck.html#4` opens slide 4, and a reload stays put.
- Author notes: a line starting with `//` is dropped from the page, so reminders can sit next to
  the slide they're about.
- `akceo viewer` writes `md-viewer.html`, a speaker-notes viewer for a second browser tab. In
  Chrome and Edge it refreshes live when the notes file changes.
- Example speaker notes for the demo deck.
- Docs: the speaker-notes setup, and how Akceo works (plain terms, user experience, internals),
  with Mermaid diagrams.
