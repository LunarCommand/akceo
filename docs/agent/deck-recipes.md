# Deck recipes

The syntax says what a deck can hold. These say what works.

- **Pick the layout before the words.** `bullets` is the default. `split` suits a diagram or
  screenshot with commentary, and `image` gives one the whole slide. `akceo check` names the
  blocks a layout takes when a slide has one it doesn't.
- **An image that doesn't exist yet:** leave out `image:`, and the slide shows a dashed box where
  it will go. Don't make up a file name, because a missing file stops the build.
- **Diagrams:** put each one in its own `.mmd` file and use `image: name.mmd`. On a dark theme,
  `image-frame: no` draws it in the theme's colors.
- **Screenshots:** `image-crop` keeps only the part that matters, which reads better than
  shrinking the whole screen.
- **Notes to yourself:** a line that starts with `//` never reaches the page. Use it for TODOs,
  and for a slide you haven't written yet: a slide that holds only notes is skipped.
- **Long list items:** indent the next line by two spaces to continue an item. A trailing `\`
  is a hard line break.
- **`style-…` keys** are a last resort for spacing. If you reach for one often, the slide wants
  a different layout.
- **Dense slides:** akceo can't tell yet whether text overflows a slide. Past about 100 words,
  have the built page looked at, or split the slide.
