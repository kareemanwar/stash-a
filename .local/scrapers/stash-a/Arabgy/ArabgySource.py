#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import Arabgy


def canonical_source_url(seed_url: str) -> str:
    parsed = urlparse(seed_url)
    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc or urlparse(Arabgy.STUDIO_URL).netloc,
            parsed.path or "/",
            "",
            parsed.query,
            "",
        )
    )


def listing_page_url(seed_url: str, page_number: int) -> str:
    parsed = urlparse(canonical_source_url(seed_url))
    query = parse_qs(parsed.query, keep_blank_values=True)
    query.pop("paged", None)
    query.pop("page", None)

    path = parsed.path or "/"
    match = re.match(r"^(?P<base>.*?)/page/(?P<page>\d+)/?$", path)

    if match:
        base_path = match.group("base") or "/"
        seed_page = int(match.group("page"))
    else:
        base_path = path
        seed_page = 1

    target_page = seed_page + page_number - 1

    if target_page > 1:
        path = f"{base_path.rstrip('/')}/page/{target_page}/"
    else:
        path = base_path or "/"

    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc or urlparse(Arabgy.STUDIO_URL).netloc,
            path or "/",
            "",
            urlencode(query, doseq=True),
            "",
        )
    )


def preview_blocks(doc: str) -> list[str]:
    blocks = re.findall(r"<!--\s*start preview\s*-->(.*?)<!--\s*end preview\s*-->", doc, re.I | re.S)
    if blocks:
        return blocks

    return re.findall(
        r"<div\b[^>]*class\s*=\s*['\"][^'\"]*\bpost-preview\b[^'\"]*['\"][^>]*>(.*?)</div>\s*</div>",
        doc,
        re.I | re.S,
    )


def extract_preview_item(block: str, page_url: str) -> dict[str, Any] | None:
    title_tag = None
    for tag in re.findall(r"<a\b[^>]*>.*?</a>", block, re.I | re.S):
        cls = Arabgy.attr_value(tag, "class") or ""
        if "preview-title" in cls:
            title_tag = tag
            break

    if not title_tag:
        anchors = re.findall(r"<a\b[^>]*>.*?</a>", block, re.I | re.S)
        title_tag = anchors[0] if anchors else None

    if not title_tag:
        return None

    href = Arabgy.attr_value(title_tag, "href")
    title = Arabgy.clean_text(title_tag)
    if not href or not title:
        return None

    item_url = Arabgy.normalize_url(href, page_url)

    image = None
    match = re.search(r"<img\b[^>]*>", block, re.I | re.S)
    if match:
        src = Arabgy.attr_value(match.group(0), "src")
        if src:
            image = Arabgy.normalize_url(src, page_url)

    item: dict[str, Any] = {
        "title": title,
        "urls": [item_url],
        "studio": {"name": Arabgy.STUDIO_NAME, "url": Arabgy.STUDIO_URL},
        "tags": Arabgy.extract_tags(block),
        "performers": Arabgy.extract_performers(block),
    }

    if image:
        item["image"] = image

    return {k: v for k, v in item.items() if v not in (None, "", [], {})}


def scrape_source(seed_url: str, max_pages: int, limit: int | None) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    seen_urls = set()

    for page_number in range(1, max_pages + 1):
        page_url = listing_page_url(seed_url, page_number)
        doc, final_url = Arabgy.fetch_html(page_url)
        page_items = []

        for block in preview_blocks(doc):
            item = extract_preview_item(block, final_url)
            if not item:
                continue

            first_url = (item.get("urls") or [None])[0]
            if not first_url or first_url in seen_urls:
                continue

            seen_urls.add(first_url)
            page_items.append(item)
            items.append(item)

            if limit and len(items) >= limit:
                break

        if not page_items:
            break

        if limit and len(items) >= limit:
            break

    return {
        "name": "Arabgy source",
        "url": seed_url,
        "items": items,
        "scenes": items,
        "scene_candidates": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Arabgy listing/source pages.")
    sub = parser.add_subparsers(dest="operation", required=True)

    source_parser = sub.add_parser("source-by-url")
    source_parser.add_argument("--url", required=True)
    source_parser.add_argument("--max-pages", type=int, default=10)
    source_parser.add_argument("--limit", type=int, default=0)
    source_parser.add_argument("--preview-only", action="store_true", help="Compatibility flag used by bulk import tools.")

    args = parser.parse_args()

    if args.operation == "source-by-url":
        limit = args.limit if args.limit > 0 else None
        print(json.dumps(scrape_source(args.url, args.max_pages, limit), ensure_ascii=False, indent=2))
        return 0

    parser.error(f"unsupported operation: {args.operation}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
