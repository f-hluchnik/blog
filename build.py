#!/usr/bin/env python3
"""Static site generator for the blog.

Three kinds of thing:

  * content   -- Markdown you write, in `content/`: posts (dated, tagged) and
                 pages (About, Projects, ...).
  * indexes   -- lists derived from that content: the home page, the tag
                 overview, one archive per tag. Nothing on them is authored.
  * templates -- Jinja2 HTML in `templates/`, one per *shape*: a single item
                 (`post.html`, `page.html`) or a list of items
                 (`post-list.html`, `tag-list.html`).

`build()` reads the content and writes plain HTML into `dist/`. That directory
is the entire website; it is gitignored and rebuilt from scratch every run.

zpevnik-web is a separate repo with its own look, but its build.py is a subset
of this one -- same names, same order. Read one and you can read the other.

Usage:
    python build.py            # build into dist/
    python build.py --serve    # build, then serve dist/ on localhost:8000
"""

from __future__ import annotations

import re
import shutil
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from PIL import Image, ImageOps

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

ROOT = Path(__file__).parent
POSTS_DIR = ROOT / "content" / "posts"
PAGES_DIR = ROOT / "content" / "pages"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "dist"

SERVE_ADDRESS = ("localhost", 8000)

# Photos live in static/images/photos/ as pre-converted WebP files committed
# to git. The build only generates square thumbnails, and only when the
# thumbnail is missing or older than the source (same logic as Make).
PHOTOS_DIR = ROOT / "content" / "photos"
PHOTOS_SRC = ROOT / "static" / "images" / "photos"
THUMB_SIZE = 600   # px, square; originals are served directly as full images

# `extra` is a bundle: md_in_html, tables, fenced_code, attr_list, def_list,
# abbr and footnotes. `footnotes` is named again so MARKDOWN_CONFIG can reach
# it -- config only applies to an extension listed explicitly.
MARKDOWN_EXTENSIONS = ["extra", "footnotes", "sane_lists", "smarty"]

# The two extensions that emit text of their own, which defaults to English.
MARKDOWN_CONFIG = {
    "footnotes": {"BACKLINK_TITLE": "Zpět na odkaz na poznámku {}"},
    "smarty": {
        "substitutions": {
            "left-double-quote": "&bdquo;",  # Czech quotes are „like this“
            "right-double-quote": "&ldquo;",
            "left-single-quote": "&sbquo;",
            "right-single-quote": "&lsquo;",
        }
    },
}

SITE = {
    "lang": "cs",
    "title": "Komorebi",
    "description": "Sluneční paprsky prosvítající skrze listí stromů.",
    "url": "https://f.hluchnikovi.cz",
}

# The <time datetime="..."> attribute stays ISO regardless of this.
DATE_FORMAT = "%Y.%m.%d"

env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
    # Fail the build on a missing or misspelled variable rather than quietly
    # rendering an empty string.
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def slugify(text: str) -> str:
    """'Čerstvý chléb' -> 'cerstvy-chleb'. URL-safe ASCII, nothing clever."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def format_date(value: date) -> str:
    return value.strftime(DATE_FORMAT)


# Posts link to their own tags, where only the display name is in scope, so
# templates need the same slug rule the tag URLs were built from.
env.filters["slugify"] = slugify
env.filters["format_date"] = format_date


def split_front_matter(raw: str) -> tuple[dict, str]:
    """Split '---\\nyaml\\n---\\nbody' into (metadata, body). A file that only
    opens with a thematic break is returned untouched."""
    if not raw.startswith("---\n") or raw.count("---", 1) == 0:
        return {}, raw
    _, front_matter, body = raw.split("---", 2)
    return yaml.safe_load(front_matter) or {}, body.strip()


def render_markdown(body: str) -> str:
    # A fresh converter per document: a reused Markdown instance carries state
    # between conversions (footnote numbering, most visibly).
    return markdown.markdown(
        body, extensions=MARKDOWN_EXTENSIONS, extension_configs=MARKDOWN_CONFIG
    )


def parse_post(path: Path) -> dict:
    """One file in content/posts/ -> a post dict."""
    meta, body = split_front_matter(path.read_text(encoding="utf-8"))
    missing = [key for key in ("title", "date") if key not in meta]
    if missing:
        raise ValueError(f"{path}: front matter is missing {', '.join(missing)}")

    # YAML turns an unquoted 2026-07-27 into a date already; a quoted one
    # arrives as a string.
    post_date = meta["date"]
    if isinstance(post_date, str):
        post_date = datetime.strptime(post_date, "%Y-%m-%d").date()
    if not isinstance(post_date, date):
        raise ValueError(f"{path}: 'date' must look like YYYY-MM-DD")

    slug = meta.get("slug") or slugify(meta["title"])
    return {
        "title": meta["title"],
        "date": post_date,
        "tags": meta.get("tags") or [],
        "summary": meta.get("summary", ""),
        "slug": slug,
        "url": f"/posts/{slug}/",
        "content": render_markdown(body),
    }


def parse_page(path: Path) -> dict:
    """One file in content/pages/ -> a page dict."""
    meta, body = split_front_matter(path.read_text(encoding="utf-8"))
    slug = meta.get("slug") or path.stem
    return {
        "title": meta.get("title", slug),
        "slug": slug,
        "url": f"/{slug}/",
        "content": render_markdown(body),
    }


def load_posts() -> list[dict]:
    """All posts, newest first. Ties break on slug so builds are reproducible."""
    posts = [parse_post(path) for path in sorted(POSTS_DIR.glob("*.md"))]
    posts.sort(key=lambda post: (post["date"], post["slug"]), reverse=True)

    clashes = [slug for slug, n in Counter(p["slug"] for p in posts).items() if n > 1]
    if clashes:
        raise ValueError(f"two posts share a slug: {', '.join(sorted(clashes))}")
    return posts


def load_pages() -> list[dict]:
    return [parse_page(path) for path in sorted(PAGES_DIR.glob("*.md"))]


def parse_photo(path: Path) -> dict:
    """One .md file in content/photos/ -> a photo dict.

    Only `source` is required — it names a WebP in static/images/photos/.
    All other fields (caption, date, film, lens, location) are optional.
    The build generates a square thumbnail; the original is served as-is.
    """
    meta, _ = split_front_matter(path.read_text(encoding="utf-8"))
    if "source" not in meta:
        raise ValueError(f"{path}: front matter is missing 'source'")

    source = PHOTOS_SRC / meta["source"]
    if not source.exists():
        raise ValueError(f"{path}: '{meta['source']}' not found in {PHOTOS_SRC}")

    photo_date = meta.get("date")
    if isinstance(photo_date, str):
        photo_date = datetime.strptime(photo_date, "%Y-%m-%d").date()

    date_label = ""
    if meta.get("display_date") and photo_date:
        date_label = f"{photo_date.strftime('%b')} {photo_date.day}, {photo_date.year}"

    # Build the quiet secondary line from whatever optional fields are present.
    # Omit any that are missing -- no placeholder dashes.
    detail_fields = ["film", "lens", "location"]
    meta_line = " · ".join(str(meta[f]) for f in detail_fields if meta.get(f))

    slug = meta.get("slug") or slugify(source.stem)
    thumb_name = f"{slug}-thumb.webp"

    return {
        "slug": slug,
        "source": source,
        "caption": meta.get("caption", ""),
        "date": photo_date,
        "date_label": date_label,
        "meta": meta_line,
        "full_url": f"/static/images/photos/{source.name}",
        "thumb_url": f"/static/images/photos/thumbs/{thumb_name}",
        "thumb_dest": ROOT / "static" / "images" / "photos" / "thumbs" / thumb_name,
    }


def load_photos() -> list[dict]:
    """All photos, newest first. Photos without a date sort last."""
    if not PHOTOS_DIR.exists():
        return []
    photos = [parse_photo(p) for p in sorted(PHOTOS_DIR.glob("*.md"))]
    photos.sort(key=lambda p: p["date"] or date.min, reverse=True)
    return photos


def make_thumbnail(source: Path, dest: Path, size: int = THUMB_SIZE) -> None:
    """Square center-crop thumbnail. Skipped when dest is newer than source."""
    if dest.exists() and dest.stat().st_mtime >= source.stat().st_mtime:
        return
    img = ImageOps.exif_transpose(Image.open(source)).convert("RGB")
    w, h = img.size
    edge = min(w, h)
    left, top = (w - edge) // 2, (h - edge) // 2
    img = img.crop((left, top, left + edge, top + edge))
    img = img.resize((size, size), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "WEBP", quality=82)


def group_by_tag(posts: list[dict]) -> list[dict]:
    """Collect posts under each tag. The display name stays as written; the URL
    gets an ASCII slug, so a tag with diacritics still works."""
    grouped: dict[str, dict] = {}
    for post in posts:
        for name in post["tags"]:
            slug = slugify(name)
            tag = grouped.setdefault(
                slug, {"name": name, "slug": slug, "url": f"/tags/{slug}/", "posts": []}
            )
            tag["posts"].append(post)
    # Sort on the slug, so "štítek" lands under S rather than after Z.
    return sorted(grouped.values(), key=lambda tag: tag["slug"])


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def render(template_name: str, out_path: Path, **context) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        env.get_template(template_name).render(
            site=SITE, current_year=date.today().year, **context
        ),
        encoding="utf-8",
    )


def build() -> None:
    # Parse before deleting dist/, so a broken post leaves the previous build
    # in place instead of an empty directory.
    posts = load_posts()
    pages = load_pages()
    photos = load_photos()
    tags = group_by_tag(posts)

    # Thumbnails are generated before dist/ is wiped so we can detect
    # freshness via mtime. They live in static/, which gets copied into dist/.
    for photo in photos:
        make_thumbnail(photo["source"], photo["thumb_dest"])

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # post-list.html is used twice: bare for the home page, and with a heading
    # and a way back for each tag archive. Both arguments are always passed so
    # StrictUndefined keeps catching genuine typos.
    render("post-list.html", OUTPUT_DIR / "index.html", posts=posts, heading=None,
           back_link=None)

    for post in posts:
        render("post.html", OUTPUT_DIR / "posts" / post["slug"] / "index.html", post=post)

    render("tag-list.html", OUTPUT_DIR / "tags" / "index.html", tags=tags)

    for tag in tags:
        render(
            "post-list.html",
            OUTPUT_DIR / "tags" / tag["slug"] / "index.html",
            posts=tag["posts"],
            heading=f"Příspěvky se štítkem „{tag['name']}“",
            back_link={"url": "/tags/", "title": "Všechny štítky"},
        )

    render("photos.html", OUTPUT_DIR / "photos" / "index.html", photos=photos)

    for page in pages:
        render("page.html", OUTPUT_DIR / page["slug"] / "index.html", page=page)

    # GitHub Pages serves /404.html for any path it cannot match.
    render("404.html", OUTPUT_DIR / "404.html")

    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static")

    # Derived from SITE["url"], so the domain is configured in one place
    # instead of also being hardcoded in the deploy workflow.
    (OUTPUT_DIR / "CNAME").write_text(urlparse(SITE["url"]).netloc + "\n", encoding="utf-8")

    print(f"Built {len(posts)} post(s), {len(tags)} tag(s), {len(pages)} page(s), {len(photos)} photo(s) -> dist/")


def serve() -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(OUTPUT_DIR))
    print("Serving http://{}:{}  (Ctrl+C to stop)".format(*SERVE_ADDRESS))
    try:
        HTTPServer(SERVE_ADDRESS, handler).serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        serve()
