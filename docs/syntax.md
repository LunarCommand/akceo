# Deck syntax

A deck is one Markdown file. It starts with a config block. Then come the slides, each one after
a line that holds only `---`.

```markdown
title: My Talk
theme: paper
images: ./img

---

layout: title
kicker: Welcome

# My Talk

---

kicker: Agenda

## What we'll cover

- First thing
- Second thing
```

Mistakes stop the build with a message that names the file, the line and the slide. Examples
are an unknown key, a key on the wrong layout, a missing heading, or content the layout doesn't
use.

## Config block

The config block is everything before the first `---`. It may hold only `key: value` lines.

| Key | Meaning | Default |
| --- | --- | --- |
| `title` | Page title shown in the browser tab | The file name without `.md` |
| `theme` | Built-in theme name, or a path to a `.css` file relative to the deck | `midnight` |
| `images` | Folder to read slide images from, relative to the deck | The deck's folder |
| `image-frame` | `no` puts every image straight on the slide, with no panel behind it. See [Images](#images). | `yes` |

## Slides

A slide starts with `key: value` header lines. Then comes a blank line, then the content.

### Slide keys

| Key | Layouts | Meaning |
| --- | --- | --- |
| `layout` | all | `title`, `bullets`, `split`, `steps`, `table` or `image`. Default `bullets`. |
| `kicker` | all | Small uppercase label above the heading. |
| `meta` | title | A line of text under the title. |
| `image` | split, image | Image file, relative to the `images` folder. Leave it out to show a dashed placeholder while the image doesn't exist yet. |
| `image-alt` | split, image | Alt text for the image. |
| `image-max` | split, image | Longest side in pixels after shrinking. Default `2400`. |
| `image-wide` | split | `yes` gives the image the wider column. |
| `image-frame` | split, image | `yes` or `no` for this slide's image, overriding the deck's `image-frame`. |
| `dim-last-column` | table | `yes` shows the last column in muted text. |
| `style-h1`, `style-h2`, `style-lead`, `style-ul`, `style-ol`, `style-sub` | all | Inline CSS for that element, for one-off spacing fixes. `style-sub` applies to the paragraph. It can't reference files or URLs. |

### Layouts

| Layout | Shows | Takes | Requires |
| --- | --- | --- | --- |
| `title` | A centered title | `#` heading | `#` heading |
| `bullets` | A heading and a list | `##` heading, `>` lead, `-` list, paragraph | `##` heading |
| `split` | An image left, text right | `##` heading, any number of `###` phases and `-` lists, one `*note*` | `##` heading |
| `steps` | A numbered sequence | `##` heading, paragraph, `1.` list | `##` heading, `1.` list |
| `table` | A table | `##` heading, `\|` table | `##` heading, `\|` table |
| `image` | An image filling the slide, the kicker top left | nothing | nothing |

Each kind of content may appear once per slide. In the `split` layout, phases and lists may
repeat and render in the order written. There, the note always renders last.

## Blocks

| Write | Get |
| --- | --- |
| `# Text` | Title heading (`title` layout) |
| `## Text` | Slide heading |
| `### Name` and a line under it | A phase: a name and a one-line description (`split` layout). The description is optional; a blank line or another block right after the name leaves it out. |
| `- item` | Bulleted list |
| `1. item` | Numbered list |
| `> text` | Lead: larger text. Consecutive `>` lines join into one. |
| `\| a \| b \|` | Table row. The first row is the header. A `\| --- \| --- \|` row after it is skipped. |
| `*text*` | Note: a whole line in single asterisks (`split` layout) |
| Anything else | Paragraph. Consecutive lines join into one. |

Table cells split on `|`. A pipe inside backticks stays in its cell, as in `` `a|b` ``. Anywhere
else, write `\|` for a literal pipe.

Two rules join lines:

- A line indented by two spaces joins the line above with a space. Use it to wrap long list
  items.
- A trailing `\` joins the next line with a hard line break.

## Author notes

A line whose first non-space characters are `//` is a note to yourself. It never reaches the
page. Use it for reminders such as "this becomes a split once the diagram exists".

```markdown
## Integrations
// TODO: add the partner API row once it ships
| Path | Returns |
```

A note can go anywhere: in the config block, among a slide's header lines, or between the
lines of a list or paragraph. The content around it reads as if the note weren't there, so a
note between two list items doesn't split the list. A slide that holds only notes is skipped,
which lets you stub a slide you haven't written yet. There's no escape, so a line of slide text
can't start with `//`.

## Inline markup

| Write | Get |
| --- | --- |
| `**text**` | Bold |
| `***text***` | Bold in the theme's `--strong` color |
| `==text==` | Accent color |
| `((text))` | Muted text, shown in parentheses |
| `` `text` `` | Code. Markup inside it stays literal. |

Characters like `<` and `&` are escaped, so raw HTML shows as text.

## Images

The `split` and `image` layouts embed their image in the page.

- **PNG, JPEG and WebP** are shrunk so the longest side is at most `image-max`. Smaller images
  are never enlarged. JPEG and WebP are re-saved at quality 90 and turned upright using their
  EXIF orientation.
- **SVG** is embedded unchanged.
- **Mermaid** diagrams in a `.mmd` file are drawn as SVG at build time, then embedded. This
  needs the Mermaid CLI, which is a separate install: `npm install -g @mermaid-js/mermaid-cli`.
  Without it, a deck that uses a `.mmd` file stops with a message that says so. Each diagram adds
  a few seconds to the build. A diagram that Mermaid can't draw stops the build with Mermaid's
  own error message.

Other formats stop the build.

### Frames

By default an image sits on a panel in the theme's `--figure-bg` color, with a shadow. Both
built-in themes use white, which suits screenshots and photos. `image-frame: no` drops the
panel, so the image sits straight on the slide. Set it in the config block for the whole deck,
or on one `split` or `image` slide. A slide's setting wins over the deck's.

A Mermaid diagram with no frame is drawn in the deck theme's colors, so it matches the slides:

- node fill: `--line`
- node border: `--accent`
- text: `--text`
- arrows: `--muted`
- font: `--font`

A diagram in a frame keeps Mermaid's own default colors, which read well on white. Mermaid
also needs to know whether the background is dark. akceo works that out from `--bg` when it is
a hex color such as `#0b0f16`. Other color formats leave Mermaid to guess. For finer control,
start the `.mmd` file with Mermaid's own `%%{init: …}%%` line.

The frame setting doesn't change the image itself. A screenshot with a white background still
shows white.

A `split` or `image` slide with no `image:` line shows a dashed box where the image will go, so
you can set up the slide before the image exists. An `image:` that names a missing file still stops the
build.

## Themes

A theme is a CSS file. akceo adds it after its own layout rules, so a theme sets the tokens below
and can also override any layout rule. A theme that leaves out any token stops the build, and
the message lists the missing ones.

| Token | Used for |
| --- | --- |
| `--bg` | Page background, and the numbers in `steps` |
| `--line` | Table rules, the key hint, and the border of an image placeholder |
| `--text` | Body text |
| `--muted` | Paragraphs, notes, the meta line, `((dimmed))` text |
| `--strong` | Bold text in lists and the first table column, phase names, `***strong***` |
| `--accent` | Kickers, list markers, `==accent==`, table headers, the progress bar |
| `--accent2` | Code |
| `--figure-bg` | Background behind `split` and `image` images |
| `--figure-shadow` | Shadow under `split` and `image` images (a `box-shadow` value) |
| `--font` | Body font stack |
| `--mono` | Code font stack |

A comment on a theme's first line is its description in `akceo themes`. Fonts loaded from the
web won't show when the deck is opened offline, so prefer fonts installed on the machine you
present from.
