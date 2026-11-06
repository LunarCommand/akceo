---
name: deck
description: Write or edit a slide deck with akceo, which builds one self-contained HTML file from Markdown and checks it as it goes. Always use this skill when the user asks to make, write, draft, build, edit or fix a slide deck, slides, a presentation, a talk or a pitch, or mentions akceo or an akceo deck. Triggers include phrases like "make a deck about", "turn this doc into slides", "draft a talk for", "add a slide to my deck", "fix my akceo deck" and "build the deck". Do not use it when the user asks for a PowerPoint, Keynote or Google Slides file.
---

# Write a deck with akceo

akceo builds a slide deck from one Markdown file into one HTML file that loads nothing from
outside. Its guide holds the format. This skill holds the order of work. The commands below name
the deck `deck.md`; use the deck's own file name.

## 1. Read the guide

Run `akceo docs --print` and read all of it before you write a slide. It comes from the installed
akceo, so it always matches the version that builds the deck. Read it every time you start on a
deck; don't write from memory. The guide is long: if the shell cuts the output short or saves it
to a file, read that file to the end.

- If the shell can't find `akceo`, look for it in the project's own environment first:
  `uv run akceo`, `.venv/bin/akceo` or `python -m akceo`. If one works, use it for the commands
  below. If none does, offer to install akceo with `uv tool install akceo`, or
  `pipx install akceo`, and wait for the user's yes.
- If akceo says `docs` isn't one of its commands, it's older than 0.3.0. Offer to upgrade the copy
  you ran: `uv tool upgrade akceo` or `pipx upgrade akceo` for one installed as a tool, or the
  project's own way for one in a project, such as `uv add 'akceo>=0.3.0'`. Wait for the user's
  yes, then run the guide command again the same way.

## 2. Get the brief (a new deck)

Ask, in one message, for what you can't tell from the request or the files it points to:

- who the audience is, and what they should think or do afterwards
- how long the talk is, or how many slides
- the source material: documents, code, notes or data to draw from
- the theme: `akceo themes` lists them
- where to save the deck

Don't ask about anything the user already said. If they asked you to go ahead without
questions, choose for yourself and say what you chose.

## 3. Outline (a new deck)

Before you write, show a numbered list of the slides: each one's layout, and a line on what it
says. Wait for the user to approve or change it. Pick the layout first, because each layout
takes only certain blocks.

## 4. Write

- Put a new deck where the user's other decks are, named the way they are. If there are none,
  give it its own folder, with the deck in `deck.md`.
- Put each diagram in its own `.mmd` file next to the deck.
- Write only the Markdown the guide describes.
- For an image that doesn't exist yet, leave out `image:`, and the slide shows where it goes.
  Never make up a file name.
- Mark anything the user still has to fill in with a `//` line, which never reaches the page.

## 5. Check

Run `akceo check deck.md` after every edit, and fix what it reports. It stops at the first
error, so run it again until it prints `ok`. Then fix its warnings, unless one is about something
the user meant, such as an image they'll add later. If you can't fix an error, show the user what
it says.

## 6. Build and look

Run `akceo build deck.md`, which writes `deck.html` next to the deck. If you're running on the
user's own computer, open the page for them: `open deck.html` on macOS, `xdg-open deck.html` on
Linux, `start deck.html` on Windows. Otherwise, such as in a cloud session, give them the file's
path.

`ok` means akceo found nothing wrong, not that every slide looks right. Tell the user which
slides to look at: those with a diagram, which can show an error only when the page opens, and
the dense ones, which can overflow. If you can see the page yourself, such as with a browser
tool, look at those slides first.

## Editing a deck that already exists

Skip the brief and the outline. Read the guide, then the deck, make the change, and check and
build as above.
