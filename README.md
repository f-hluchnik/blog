# blog

A minimal static blog. No framework, no database, no server: a Python
script (`build.py`, ~150 lines) reads Markdown posts and writes plain HTML
into `dist/`.

## How it works

- `content/posts/*.md` — one file per post. Each starts with a small YAML
  front-matter block, then the post body in Markdown.
- `content/pages/*.md` — standalone pages (About, etc.), same format minus
  `date`/`tags`.
- `templates/*.html` — Jinja2 templates (the HTML shell around your content).
- `static/` — CSS and images, copied into `dist/static/` as-is.
- `build.py` — reads everything above and writes `dist/`. That directory is
  the entire website; it's gitignored and rebuilt from scratch every time.

## Writing a post

Create a new file in `content/posts/`, named however you like (the date in
the filename is just for your own sorting — the front matter is what
actually controls publish order):

```markdown
---
title: Some Title
date: 2026-07-21
tags: [books, life]
summary: One sentence shown in the post list.
---

Your post, in Markdown. **Bold**, *italic*, [links](https://example.com),
lists, headings (`##`, `###`), code blocks, and blockquotes all work.
```

A post can carry as many tags as you like — a post tagged `[baking, life]`
shows up under both the "baking" and "life" tag pages. `/tags/` lists every
tag with a count.

## Adding pictures

Drop image files anywhere under `static/images/` (e.g.
`static/images/posts/sourdough-loaf.jpg`), then reference them from a post
with a normal Markdown image, using the path starting at `/static/...`:

```markdown
![A fresh loaf cooling on a rack](/static/images/posts/sourdough-loaf.jpg)
```

## Previewing locally

```bash
pip install -r requirements.txt
python build.py --serve
```

Then open http://localhost:8000. Re-run the command after any edit (there's
no auto-reload — one less moving part to maintain).

## Deploying to GitHub Pages

1. Push this repo to GitHub.
2. In the repo's **Settings → Pages**, set **Source** to **GitHub Actions**.
3. Push to `main`. `.github/workflows/deploy.yml` builds the site and
   publishes `dist/` automatically. Check the **Actions** tab for the run
   and the live URL.
4. Optional custom domain: add it under **Settings → Pages → Custom domain**
   (GitHub will create a `CNAME` file and handle HTTPS for you), then point
   your domain's DNS at GitHub Pages per
   [GitHub's instructions](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site).

## Posting from your phone

Add or edit a `.md` file under `content/posts/` using the GitHub mobile app
(or any Git client), commit to `main`, and the Action above rebuilds and
redeploys the site automatically — no laptop required.

## Editing the design

Everything visual lives in `static/style.css` — colors and fonts are set
once as CSS custom properties at the top of the file. No build step, no
CSS framework.
