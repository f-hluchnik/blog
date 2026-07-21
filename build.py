#!/usr/bin/env python3
"""
Static site generator for the blog.

How it works, in one paragraph: every post is a Markdown file with a small
YAML front-matter header (title, date, tags, summary). This script reads
every post, renders it through a Jinja2 template, and writes plain HTML
files into dist/. There is no server, no database, no build magic beyond
what's written here -- run `python build.py` and read every line if you
want to know exactly what your site does.

Usage:
    python build.py          # build the site into dist/
    python build.py --serve  # build, then serve dist/ at http://localhost:8000
"""

import re
import shutil
import sys
from datetime import date, datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).parent
POSTS_DIR = ROOT / "content" / "posts"
PAGES_DIR = ROOT / "content" / "pages"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "dist"

# Edit this to describe your own site.
SITE = {
    "title": "A Notebook of Ordinary Things",
    "description": "Bread, running, books, and other notes from life.",
    "url": "https://f.hluchnikovi.cz",
}

env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def slugify(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def split_front_matter(raw: str) -> tuple[dict, str]:
    """Split '---\\nyaml\\n---\\nbody' into (metadata dict, body string)."""
    if not raw.startswith("---"):
        return {}, raw
    _, fm_raw, body_raw = raw.split("---", 2)
    meta = yaml.safe_load(fm_raw) or {}
    return meta, body_raw.strip()


def parse_post(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    meta, body = split_front_matter(raw)
    if "title" not in meta or "date" not in meta:
        raise ValueError(f"{path} is missing 'title' or 'date' in its front matter")

    html = markdown.markdown(body, extensions=["extra", "sane_lists", "smarty"])

    post_date = meta["date"]
    if isinstance(post_date, str):
        post_date = datetime.strptime(post_date, "%Y-%m-%d").date()
    elif isinstance(post_date, datetime):
        post_date = post_date.date()
    elif not isinstance(post_date, date):
        raise ValueError(f"{path}: 'date' must look like YYYY-MM-DD")

    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    slug = meta.get("slug") or slugify(meta["title"])

    return {
        "title": meta["title"],
        "date": post_date,
        "tags": tags,
        "summary": meta.get("summary", ""),
        "slug": slug,
        "content": html,
        "url": f"/posts/{slug}/",
    }


def parse_page(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    meta, body = split_front_matter(raw)
    html = markdown.markdown(body, extensions=["extra", "sane_lists", "smarty"])
    return {
        "title": meta.get("title", path.stem.replace("-", " ").title()),
        "slug": path.stem,
        "content": html,
        "url": f"/{path.stem}/",
    }


def load_posts() -> list[dict]:
    posts = [parse_post(p) for p in sorted(POSTS_DIR.glob("*.md"))]
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def load_pages() -> list[dict]:
    return [parse_page(p) for p in sorted(PAGES_DIR.glob("*.md"))]


def group_by_tag(posts: list[dict]) -> dict:
    tags: dict[str, list[dict]] = {}
    for post in posts:
        for tag in post["tags"]:
            tags.setdefault(tag, []).append(post)
    return dict(sorted(tags.items()))


def render(template_name: str, out_path: Path, **context) -> None:
    template = env.get_template(template_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        template.render(site=SITE, current_year=datetime.now().year, **context),
        encoding="utf-8",
    )


def build() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    posts = load_posts()
    pages = load_pages()
    tags = group_by_tag(posts)

    render("index.html", OUTPUT_DIR / "index.html", posts=posts, tags=tags)

    for post in posts:
        render("post.html", OUTPUT_DIR / "posts" / post["slug"] / "index.html", post=post)

    for tag, tag_posts in tags.items():
        render("tag.html", OUTPUT_DIR / "tags" / tag / "index.html", tag=tag, posts=tag_posts)

    render("tags.html", OUTPUT_DIR / "tags" / "index.html", tags=tags)

    for page in pages:
        render("page.html", OUTPUT_DIR / page["slug"] / "index.html", page=page)

    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static")

    print(f"Built {len(posts)} post(s), {len(tags)} tag(s), {len(pages)} page(s) -> {OUTPUT_DIR}/")


def serve() -> None:
    import functools

    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(OUTPUT_DIR))
    server = HTTPServer(("localhost", 8000), handler)
    print("Serving http://localhost:8000  (Ctrl+C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        serve()
