---
name: markdown-docs
description: Turn Markdown into polished, shareable documents and slide decks, as HTML and PDF, in any project. Documents get a cover, contents, page numbers, styled tables, callouts, highlighted code and Mermaid diagrams. Decks (*.slides.md) become 16:9 HTML presentations with keyboard navigation and speaker notes, plus a PDF with one slide per page. Comes with a modern default theme and supports project or customer styling (brand colour, fonts, logo, CSS, or a full custom theme). Use when asked to make, export or refresh a PDF or HTML from Markdown, to build a slide deck or presentation from Markdown, to start a new deck or write-up, or to set up or change a project's document or deck styling. Projects with a .md2pdf/ folder (for example this project's Circana style) get their branding automatically.
---

# Markdown docs: documents and decks as HTML and PDF

One script, `scripts/md2pdf.py`, builds everything with pandoc and headless Chrome. The Markdown
is never modified. Outputs are written next to the source unless `-o DIR` is given.

| Source | Output (default) |
| --- | --- |
| `name.md`: a document | `name.pdf`: A4 or Letter, with a cover, contents and "Page X of Y" footers. Add `--html` for the self-contained HTML as well. |
| `name.slides.md`, or front matter `type: slides`: a deck | `name.html` (16:9 presentation: arrow keys, F for fullscreen, N for notes, `#7` jumps to slide 7) **and** `name.pdf` (one slide per page) |

```bash
MD=.claude/skills/markdown-docs/scripts/md2pdf.py   # run from the project root
python3 $MD doctor                                   # check pandoc / Chrome / mmdc once
python3 $MD report.md                                # report.pdf
python3 $MD talk.slides.md --shots 1,4               # talk.html + talk.pdf + slide previews
python3 $MD docs/ --recursive --changed -o out/      # folders: only what changed
python3 $MD new docs/q4-review --title "Q4 Review"   # starter deck + document from the active style
```

`--format pdf|html|both` overrides the defaults. A project can also set them in config:
`"outputs": {"document": "both", "deck": "both"}`. Folder builds skip `README.md` and any folder
starting with `_` or `.`, such as templates and caches.

## Workflow

1. **Find the style first.** Look for a `.md2pdf/` folder in the file's directory or any above it.
   It applies automatically, and the build prints `(style: …)` when one is used.
   - **Asked for project or customer branding:** create the style once at the project root with
     `init-style` (below), not per file.
   - **One-off look:** use command-line flags instead.
2. **New material:** run `new <folder> --title …`, which copies the style's starter deck and
   document. Write the deck first, as an overview that is light and visual, then the document
   with the detail.
3. Build only what was asked for.
4. **Check visually before handing over.**
   - **Decks:** use `--shots 1,5,9` (or `all`). The PNGs go to `~/.cache/md2pdf/shots/`.
   - **Documents:** on macOS run `swift $(dirname $MD)/pdf_pages.swift file.pdf <scratch-dir> 1,3`.
     On Linux use `pdftoppm -png -r 80`.

   Then read the images and check:
   - text overflowing or colliding with the footer;
   - diagrams too small to read;
   - squeezed table columns;
   - a heading stranded at the bottom of a page;
   - nearly empty pages;
   - section cross-references.

   Fix and rebuild.
5. **Hand over** the `.pdf` (to send), the `.html` (to present or open) and the `.md` (to edit). Say
   which style was applied and what you checked.

## Writing documents

No front matter is needed:

| Field | Where it comes from |
| --- | --- |
| Title | The first `# H1`, removed from the body so it isn't repeated |
| Status | A leading `Status: **…**` line, moved onto the cover |
| Date | The file's modification date |
| Section numbers | Added automatically, unless the headings already carry numbers |

Optional front matter, in plain `key: value` lines:

- **Cover fields:** `title`, `subtitle`, `author`, `date`, `status`, `version`, `audience`,
  `classification`.
- **Style:** `accent`, `cover` (`band` / `plain` / `none`), `toc`, `numbered`.

Links to sibling `.md` files are rewritten to point at `.pdf` (turn off with `--keep-md-links`).
GitHub-style lists, `- [ ]` task lists and bare URLs work.

## Writing decks (`*.slides.md`)

- **Front matter:**
  - `title`;
  - `footer` (short title shown in every slide footer);
  - `label` (e.g. `Internal · Draft`);
  - `date`.
- **New slide:** a line containing only `---`.
- **Slide layout:** an HTML comment at the top of the slide.
  - `<!-- slide: title -->`: the opening slide. Use `#` for the title, a paragraph as the
    subtitle, and a `::: small` div for the meta line. The logo appears automatically.
  - `<!-- slide: section -->`: a divider, e.g. `## 02 · Problems` plus one line.
  - `<!-- slide: statement -->`: one big message.
  - No comment: a standard slide with `##` as its title.
- **Speaker notes:** a `::: notes` div. Hidden; press **N** to show. Never printed.
- **Keep slides light:** at most about 6 bullets, a table of about 6 rows, or one diagram per slide.

## Components (decks and documents)

````markdown
:::: cols       ::: col … :::  (2–3 columns)          :::: cards   ::: card ### Title … :::
:::: stats      ::: stat **42%** ⏎⏎ label :::          ::: lead / ::: small
> [!NOTE] / [!TIP] / [!IMPORTANT] / [!WARNING] / [!CAUTION]   (or ::: note / tip / warning …)
[Adopt]{.yes}  [Avoid]{.no}  [label]{.pill}           ::: pagebreak ⏎ :::   (documents)
````

**Mermaid** fenced blocks become themed inline SVG; this needs `mmdc`.

- Optional lines inside a block: `%% caption: …` and `%% height: 400`.
- In flowcharts, `class X accent` and `class X alert` colour a node with the style's accent or
  red.
- Quote labels that start with `/` or contain brackets: `A["/health"]`.
- Long left-to-right chains render tiny: use `subgraph`s or `flowchart TB`.

## Styling layers (later wins)

1. **Theme:** the built-in `themes/default/` uses Inter and JetBrains Mono with an indigo `#3B4CCA`
   accent. Its files:

   | File | Purpose |
   | --- | --- |
   | `config.json` | Default settings (keys below) |
   | `components.css` | Shared components |
   | `theme.css` + `template.html` | Documents (pandoc template) |
   | `deck.css` + `deck.html` | Decks (`{{TITLE}}`, `{{HEAD}}`, `{{CSS}}`, `{{SLIDES}}`) |
   | `mermaid.json` | Diagram theme |
   | `starter/` | `deck.slides.md`, `document.md` |

2. **Project style:** the nearest `.md2pdf/`. Every file is optional:
   - `config.json` and `mermaid.json` are merged over the theme's;
   - `theme.css` (documents) and `deck.css` (decks) are appended after the theme's CSS;
   - `template.html`, `deck.html` and `starter/` replace the theme's;
   - `"theme": "<folder>"` in `config.json` loads a whole theme folder from inside `.md2pdf/`.
3. **Front matter** of the individual file.
4. **Command-line flags:**
   - colours and fonts: `--accent`, `--ink`, `--font`, `--heading-font`, `--mono-font`,
     `--no-google-fonts`;
   - documents: `--logo`, `--page Letter`, `--cover`, `--no-toc`, `--numbered` / `--no-numbered`,
     `--no-footer`;
   - CSS and style folders: `--css file.css` (repeatable), `--theme NAME|DIR`, `--style DIR`,
     `--no-project-style`.

### config.json keys

```json
{
  "theme": "default",
  "accent": "#3B4CCA", "ink": "#1F2430",
  "fonts": { "heading": "Inter", "body": "Inter", "mono": "JetBrains Mono" },
  "google_fonts": true,
  "page": { "size": "A4", "margin": "18mm 17mm 20mm 17mm" },
  "cover": "band", "toc": true, "toc_depth": 2, "numbered": "auto",
  "logo": "logo.png",
  "footer": { "left": "{title}", "center": "", "right": "Page {page} of {pages}" },
  "meta": { "author": "Platform Team", "classification": "Internal" },
  "outputs": { "document": "pdf", "deck": "both" }
}
```

- **One `accent` drives both documents and decks:** tints, table headers, links, list markers,
  the title slide and cover, section dividers and diagrams. A brand usually needs only `accent`,
  `fonts` and `logo`.
- **Fonts** are Google Fonts family names. Set `"google_fonts": false` for locally installed or
  licensed fonts.
- **Footer placeholders** (documents): `{page}`, `{pages}`, and any cover field. Use `""` to hide a
  slot.

### Setting up project or customer styling

```bash
python3 $MD init-style <project-root> --accent '#0F766E' --font 'IBM Plex Sans' \
    --mono-font 'IBM Plex Mono' --logo brand/logo.png --cover plain
```

This creates `.md2pdf/` with `config.json`, a commented `theme.css`, and the logo. Then:

- Add `meta`, footer text and `outputs` to `config.json` as needed.
- Put extra rules in `theme.css` (documents) or `deck.css` (decks), using these CSS variables:
  - colours: `--accent`, `--accent-dark`, `--accent-ink`, `--tint`, `--tint-2`, `--tint-3`,
    `--ink`, `--muted`, `--line`;
  - fonts: `--font-heading`, `--font-body`, `--font-mono`.
- When a brand is described in words, map it: the primary colour becomes `accent`, the text
  colour becomes `ink`, typefaces become `fonts`. Confirm hex values that weren't given.
- **For a completely different look** (an existing corporate template), make a full theme folder
  and set `"theme": "<path>"` in `config.json`. The path is relative to the `.md2pdf/` folder, so
  the theme can live with the project's design assets as one source of truth, without symlinks
  (which break on Windows checkouts). This project's Circana theme works this way: it lives in
  `.claude/skills/markdown-docs/themes/circana/`, and the repository's root `.md2pdf/` loads it with
  `"../.claude/skills/markdown-docs/themes/circana"`, plus `theme.css` overrides for dense notes.
- Commit `.md2pdf/` with the project.

## Notes

- **Requirements:**
  - `pandoc` 3.x;
  - Google Chrome, Chromium or Edge (or `CHROME_PATH`);
  - `mmdc` (`npm i -g @mermaid-js/mermaid-cli`), only for Mermaid;
  - Python 3.9+ standard library.
- **Diagrams use Arial**, so text measured when the diagram is drawn matches what viewers see.
  They are cached in `~/.cache/md2pdf/`.
- **The HTML is self-contained:** local images and diagrams are embedded. Only web fonts load from
  Google Fonts, and it falls back to system fonts offline.
- **Page breaks:** document tables may break across pages, with the header row repeated. Figures,
  callouts and the cover never split.
