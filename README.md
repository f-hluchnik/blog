# blog — Komorebi

A minimal static blog at [f.hluchnikovi.cz](https://f.hluchnikovi.cz). No
framework, no database, no server: `build.py` reads Markdown and writes plain
HTML into `dist/`.

Sibling repo: [zpevnik-web](https://zpevnik.hluchnikovi.cz) — a separate,
standalone site with its own look, but the same layout, the same `build.py`
structure, and the same section order in its stylesheet. Read one and you can
read the other.

## Layout

```
content/posts/*.md   one file per post   (dated, tagged)
content/pages/*.md   one file per page   (About, Projects, ...)
templates/*.html     one file per shape  (see below)
static/              CSS, JS, icons, images — copied to dist/static/ as-is
build.py             reads all of the above, writes dist/
dist/                the entire website; gitignored, rebuilt every run
```

## The mental model

Three kinds of thing, and the templates follow directly from them:

| | |
|---|---|
| **Content** you author | `content/posts/`, `content/pages/` |
| **Indexes** the build derives | home, `/tags/`, one archive per tag |
| **Templates**, one per shape | single item: `post.html`, `page.html`<br>list of items: `post-list.html`, `tag-list.html` |

`post-list.html` is used twice — for the home page and for every tag archive,
which are the same shape with a different heading. Partials start with an
underscore (`_tags.html`, `_theme-toggle.html`) and are `include`d, not
extended.

`/tags/` has no Markdown file behind it because nothing on it is authored:
it is computed from the `tags:` in every post's front matter. That is the
line between a page and an index.

## Writing a post

Create a file in `content/posts/`. The filename is only for your own sorting —
the front matter is what counts.

```markdown
---
title: Some Title
date: 2026-07-21
tags: [knihy, život]
summary: One sentence shown in the post list.
---

Your post in Markdown. **Bold**, *italic*, [links](https://example.com),
lists, headings (`##`, `###`), code blocks, blockquotes and footnotes work.
```

`title` and `date` are required; the build fails loudly without them. The URL
slug comes from the title, or from an explicit `slug:` if you want to change
a title without breaking a link. Tags can carry diacritics — the URL gets an
ASCII slug (`Čerstvý chléb` → `/tags/cerstvy-chleb/`) while the display name
stays as written.

## Adding a page

Create a file in `content/pages/`. `about.md` becomes `/about/`.

```markdown
---
title: O blogu
---
```

The nav is four hardcoded links in `templates/base.html` — add yours there too.
(Deriving the nav from front matter was tried and removed: sixteen lines of
machinery to save one line of editing.)

## Adding pictures

Drop files under `static/images/`, then reference them with a path starting
at `/static/`:

```markdown
![A fresh loaf cooling on a rack](/static/images/posts/sourdough-loaf.jpg)
```

## Previewing locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python build.py --serve
```

Open <http://localhost:8000>. Re-run after any edit — there is no auto-reload,
which is one less moving part to maintain.

## Editing the design

Everything visual is in `static/style.css`. Colours are declared once as
custom properties at the top, each with its light and dark value side by side
via `light-dark()`; nothing below that block hardcodes a colour. The
light/dark toggle is `static/theme.js`, byte-identical to the songbook's copy.

Footer alignment follows the header: left here, centred in the songbook.

Czech strings live in the templates that show them, not in a config dict. The
site is only ever going to be in Czech.

## What the odd files are for

- **`static/theme.js`** — the light/dark *toggle*, and only the toggle. Dark
  mode itself needs no JavaScript: `color-scheme: light dark` plus the
  `light-dark()` tokens already follow the reader's system setting. This file
  exists so someone on a light OS can read the site dark anyway. It is loaded
  render-blocking from `<head>` on purpose — it has to set `data-theme` before
  first paint, or a dark-mode reader sees a white flash. Deleting it and
  `templates/_theme-toggle.html` would leave dark mode fully working.
- **`static/site.webmanifest`** — only used when someone adds the site to a
  phone home screen on Android; it supplies the name, icon and colours there.
  iOS uses the `apple-touch-icon` link instead. Invisible to normal visitors.
- **`templates/404.html`** — GitHub Pages serves `dist/404.html` for any path
  it cannot match. It has no Markdown file behind it for the same reason
  `/tags/` doesn't: there is nothing to author. Without it, a mistyped URL
  gets GitHub's generic English error page instead of this site.

## Deploying

`.github/workflows/deploy.yml` builds on every push and every pull request,
but publishes to GitHub Pages only from `main`. A branch or a pull request
therefore tells you the site still builds, without touching what is live.

The custom domain is derived from `SITE["url"]` — `build.py` writes
`dist/CNAME` from it, so the domain is configured in exactly one place. In the
repo's **Settings → Pages**, set **Source** to **GitHub Actions**, then point
your DNS at GitHub Pages per
[their instructions](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site).

## Posting from your phone

Add or edit a `.md` file under `content/posts/` in the GitHub mobile app,
commit to `main`, and the workflow rebuilds and redeploys. No laptop required.
