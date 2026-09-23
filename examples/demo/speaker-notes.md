# Speaker Notes · Akceo demo

Open this file in `md-viewer.html` in a second tab. Share only the deck tab.

---

### 1 · Decks at the speed of text *(0:20)*
Open with the promise: a deck is a text file, and one command turns it into a presentation.

### 2 · Slides are structured text *(0:45)*
Three points, in order:

1. **Markdown**: write in any editor, keep it in git, review changes in a diff.
2. **One file**: images are embedded, so there's nothing to lose when you email it.
3. **Anywhere**: it opens in any browser, even with no network.

If asked: this slide is the `bullets` layout, the default when a slide doesn't name one.

### 3 · A small set of marks *(0:40)*
Walk the list top to bottom. Each item shows the syntax and the result side by side.

- `==accent==` is the one to point out; it's how a lead line gets its color.
- The last item shows that a long line can wrap in the source without breaking on the slide.

### 4 · One command, one file *(0:40)*
Point at the diagram: the deck and a theme go in, one HTML file comes out.

The three phases on the right are the whole workflow. Mention that images are shrunk at build time, so a big screenshot doesn't make a big deck.

### 5 · From zero to a deck *(0:30)*
Read the four steps as a loop, not a one-time setup. After the first install it's write, build, present.

### 6 · Six layouts *(0:30)*
There are only six layouts, on purpose. Most slides are `bullets`; `split` is for a diagram with commentary, and `image` is for a diagram on its own.

> The muted last column is `dim-last-column: yes` on this slide.

### 7 · The image layout *(0:15)*
The same diagram, now on its own. The image fills the slide and the kicker stays in the corner. Leave out `image:` and the slide shows a dashed placeholder until the diagram exists.

### 8 · Same deck, any look *(0:20)*
Close by rebuilding with `--theme paper` live, if time allows. The content doesn't change, only the look.

---
