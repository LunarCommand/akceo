title: Akceo demo
theme: midnight

---

layout: title
kicker: Akceo demo
meta: Markdown in, one self-contained HTML file out

# Decks at the speed of text

---

kicker: Why

## Slides are structured text

- Write in **Markdown**, keep the deck in git, and review it in a diff.
- Build to a **single HTML file** with images embedded and no external assets.
- Open it anywhere: a browser, offline, or from an email attachment.

This slide uses the ***bullets*** layout: a heading, a list and a closing paragraph.

---

kicker: Inline markup
style-lead: max-width:40ch;margin-bottom:3vh

## A small set of marks

> A lead line sets the tone and can carry an ==accent==.

- `**bold**` gives **bold**, and `***strong***` gives ***strong***.
- `==accent==` gives ==accent==, and `((dim))` gives ((a muted aside)).
- Backticks give code, and markup inside them stays literal: `==like this==`.
- Indent a line by two spaces to wrap a long item across lines
  in the source without breaking it on the slide.

---

layout: split
kicker: How it works
image: flow.svg
image-alt: deck.md and a theme go into akceo build, which writes deck.html
style-h2: margin-bottom:3vh

## One command,\
one file

### write
slides in deck.md, then pick a theme

### build
akceo build deck.md

### present
open deck.html and press F for full screen

*Images are shrunk and embedded at build time.*

---

layout: steps
kicker: Getting started

## From zero to a deck

Install once. After that it's a write, build, present loop.

1. Install: `uv tool install git+https://github.com/LunarCommand/akceo`
2. Write `deck.md`: a config block, then slides separated by `---`.
3. Build: `akceo build deck.md`
4. Present: open `deck.html` and use the arrow keys.

---

layout: table
kicker: Reference
dim-last-column: yes

## Five layouts

| Layout | Best for | Content |
| --- | --- | --- |
| **title** | Opening and section slides | `#` heading, kicker, meta line |
| **bullets** | Most slides | `##` heading, lead, list, paragraph |
| **split** | A diagram with commentary | image, `##` heading, phases, lists, note |
| **steps** | A sequence | `##` heading, paragraph, numbered list |
| **table** | Comparisons | `##` heading, table |

---

layout: title
kicker: Themes
meta: Rebuild with --theme paper for the light version

# Same deck, any look
