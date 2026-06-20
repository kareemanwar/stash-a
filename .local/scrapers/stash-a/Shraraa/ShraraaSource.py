#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import urllib.parse
from typing import Any

from Shraraa import (
    SOURCE_TYPE,
    STUDIO_NAME,
    STUDIO_URL,
    absolute_url,
    clean,
    extract_anchor_items,
    extract_tags,
    fetch_html,
)


def preview_blocks(doc: str) -> list[str]:
    blocks = re.findall(r"<!--\s*start preview\s*-->(.*?)<!--\s*end preview\s*-->", doc, flags=re.I | re.S)
    if blocks:
        return blocks

    return re.findall(
        r'(<div[^>]+class=["\'][^"\']*\bpost-preview\b[^"\']*["\'][^>]*>.*?</div>\s*</div>)',
        doc,
        flags=re.I | re.S,
    )


def extract_preview_item(block: str, page_url: str) -> dict[str, Any] | None:
    link = ""
    title = ""

    m = re.search(r'<a[^>]+class=["\'][^"\']*\bpreview-title\b[^"\']*["\'][^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block, flags=re.I | re.S)
    if m:
        link = absolute_url(m.group(1), page_url)
        title = clean(m.group(2))

    if not link:
        m = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]+title=["\']([^"\']+)["\']', block, flags=re.I | re.S)
        if m:
            link = absolute_url(m.group(1), page_url)
            title = clean(m.group(2))

    if not link:
        return None

    if not title:
        m = re.search(r'<img[^>]+alt=["\']([^"\']+)["\']', block, flags=re.I | re.S)
        if m:
            title = clean(m.group(1))

    image = ""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', block, flags=re.I | re.S)
    if m:
        image = absolute_url(m.group(1), page_url)

    tags = extract_tags(block, page_url, include_category=True)

    item: dict[str, Any] = {
        "title": title or link,
        "urls": [link],
        "studio": {
            "name": STUDIO_NAME,
            "url": STUDIO_URL,
        },
        "tags": tags,
    }

    if image:
        item["image"] = image

    return item


def parse_seed_page(url: str) -> int:
    path = urllib.parse.urlparse(url).path
    m = re.search(r"/page/(\d+)/?/?$", path)
    return int(m.group(1)) if m else 1


def replace_or_add_page(path: str, target_page: int) -> str:
    if target_page <= 1:
        path = re.sub(r"/page/\d+/?$", "/", path)
        return path or "/"

    if re.search(r"/page/\d+/?$", path):
        return re.sub(r"/page/\d+/?$", f"/page/{target_page}/", path)

    if not path.endswith("/"):
        path += "/"
    return path + f"page/{target_page}/"


def listing_page_url(seed_url: str, offset_page: int) -> str:
    parsed = urllib.parse.urlparse(seed_url)
    seed_page = parse_seed_page(seed_url)
    target_page = seed_page + offset_page - 1

    path = replace_or_add_page(parsed.path or "/", target_page)

    return urllib.parse.urlunparse((
        parsed.scheme or "https",
        parsed.netloc or "shraraa.com",
        path,
        "",
        parsed.query,
        "",
    ))


def scrape_source(seed_url: str, max_pages: int, limit: int) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for page_index in range(1, max_pages + 1):
        url = listing_page_url(seed_url, page_index)
        doc, final_url = fetch_html(url)
        page_items: list[dict[str, Any]] = []

        for block in preview_blocks(doc):
            item = extract_preview_item(block, final_url)
            if not item:
                continue

            primary_url = (item.get("urls") or [""])[0]
            key = primary_url.rstrip("/")
            if not key or key in seen:
                continue

            seen.add(key)
            page_items.append(item)
            items.append(item)

            if limit and len(items) >= limit:
                break

        if limit and len(items) >= limit:
            break

        if not page_items:
            break

    return {
        "name": "Shraraa source",
        "url": seed_url,
        "items": items,
        "scenes": items,
        "scene_candidates": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    source_parser = sub.add_parser("source-by-url")
    source_parser.add_argument("--url", required=True)
    source_parser.add_argument("--max-pages", type=int, default=10)
    source_parser.add_argument("--limit", type=int, default=0)
    source_parser.add_argument("--preview-only", action="store_true", help="Compatibility flag used by bulk import tools.")

    args = parser.parse_args()

    if args.command == "source-by-url":
        print(json.dumps(scrape_source(args.url, args.max_pages, args.limit), ensure_ascii=False, indent=2))
        return

    raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
