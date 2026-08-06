#!/usr/bin/env python3
"""Convert source images to web-ready WebP for the blog.

Run this script once on any new image before committing it. It resizes and
converts in-place to a WebP file next to the original, which you then commit.
The original (JPEG/PNG/TIFF) is left untouched so you can re-run with
different settings if you want.

Usage:
    python convert.py static/images/photos/praded-01.jpg
    python convert.py static/images/photos/*.jpg
    python convert.py static/images/posts/sourdough-loaf.jpg

Output:
    static/images/photos/praded-01.webp   (max 2400px, quality 88)
    static/images/posts/sourdough-loaf.webp  (max 1600px, quality 85)

The max-edge and quality values differ by folder because photos are shown
full-screen in the lightbox while post images are inline at 640px max-width.
You can override either with --max-edge and --quality flags.

What gets skipped:
    - A .webp file that already exists and is newer than the source.
      Re-run with --force to overwrite.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

# Defaults differ by destination folder, chosen here because photos are
# shown full-screen while post images are inline at 640px max-width.
DEFAULTS = {
    "photos": {"max_edge": 2400, "quality": 88},
    "posts":  {"max_edge": 1600, "quality": 85},
    "other":  {"max_edge": 1600, "quality": 85},
}


def folder_defaults(path: Path) -> dict:
    """Pick sensible defaults based on which images/ subfolder the file is in."""
    for part in path.parts:
        if part in DEFAULTS:
            return DEFAULTS[part]
    return DEFAULTS["other"]


def convert(source: Path, max_edge: int, quality: int, force: bool) -> bool:
    """Convert source to WebP. Returns True if the file was written."""
    dest = source.with_suffix(".webp")

    if not force and dest.exists() and dest.stat().st_mtime >= source.stat().st_mtime:
        print(f"  skip  {source.name}  (up to date)")
        return False

    img = ImageOps.exif_transpose(Image.open(source)).convert("RGB")
    w, h = img.size
    if max(w, h) > max_edge:
        scale = max_edge / max(w, h)
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)

    img.save(dest, "WEBP", quality=quality)
    orig_kb = source.stat().st_size // 1024
    dest_kb = dest.stat().st_size // 1024
    print(f"  wrote {dest.name}  ({orig_kb} KB -> {dest_kb} KB)")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path, help="Source image(s) to convert")
    parser.add_argument("--max-edge", type=int, default=None, help="Override longest-edge cap (px)")
    parser.add_argument("--quality", type=int, default=None, help="Override WebP quality (1-100)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing WebP even if up to date")
    args = parser.parse_args()

    errors = 0
    written = 0

    for path in args.files:
        if not path.exists():
            print(f"  error {path}: file not found", file=sys.stderr)
            errors += 1
            continue
        if path.suffix.lower() == ".webp":
            print(f"  skip  {path.name}  (already WebP)")
            continue

        defaults = folder_defaults(path)
        max_edge = args.max_edge or defaults["max_edge"]
        quality = args.quality or defaults["quality"]

        try:
            if convert(path, max_edge, quality, args.force):
                written += 1
        except Exception as exc:
            print(f"  error {path}: {exc}", file=sys.stderr)
            errors += 1

    print(f"\n{written} file(s) written, {errors} error(s).")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
