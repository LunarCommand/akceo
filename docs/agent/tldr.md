# Writing akceo decks

akceo builds a slide deck from one Markdown file into one HTML file that loads nothing from
outside, so it opens from disk, offline, or as an email attachment.

It isn't a free-form HTML tool, and it reads only its own small set of Markdown. A deck holds no
raw HTML: `<` and `&` show as text. Each slide has one of six layouts, and each layout takes only
certain kinds of content. Many mistakes stop the build with a message that names the file, the
slide and a line: an unknown key, content the layout doesn't take, a missing image, or a diagram
Mermaid can't parse. Not every mistake does. Markdown that akceo doesn't support shows as plain
text, with no error; the recipes below list what to avoid.

## How to work

1. Pick each slide's layout first: `title`, `bullets`, `split`, `steps`, `table` or `image`.
2. Write the deck.
3. Run `akceo check deck.md` after every edit, and fix what it reports. It stops at the first
   problem, so run it again until it prints `ok`.
4. Run `akceo build deck.md` to write `deck.html` next to the deck.
5. `ok` means akceo found nothing wrong, not that every slide looks right. Have the built page
   looked at, above all the slides with a diagram, which can show an error only when the page
   opens, and the dense ones, which can overflow.

## Commands

| Command | Does |
| --- | --- |
| `akceo check deck.md` | Runs every check, diagrams included, and writes nothing |
| `akceo build deck.md` | Writes `deck.html`. `-o` names another file, and `--theme` overrides the deck's theme |
| `akceo themes` | Lists the built-in themes |
| `akceo docs` | Prints where this guide is. `--print` prints the guide itself |
| `akceo init` | Adds a section to `AGENTS.md` and `CLAUDE.md` in a folder that points agents to this guide |
