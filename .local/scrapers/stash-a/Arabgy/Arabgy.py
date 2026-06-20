#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

CURRENT_DIR = Path(__file__).resolve().parent
SHARED_DIR = CURRENT_DIR.parent / "_shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

try:
    import online_hosts  # type: ignore
except Exception:
    online_hosts = None

USER_AGENT = "Mozilla/5.0 (compatible; Stash-a Arabgy scraper)"
STUDIO_NAME = "Arabgy"
STUDIO_SLUG = "arabgy"
STUDIO_URL = "https://arabgy.com/"
SOURCE_TYPE = "Arabgy"

AD_HOST_FRAGMENT_DENYLIST = (
    "diagnosedecorationvideotape.com",
    "doubleclick.net",
    "googlesyndication.com",
    "google.com",
    "adsterra",
)


def fetch_html(url: str, timeout: int = 60) -> tuple[str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        body = res.read()
        header_charset = res.headers.get_content_charset()

        head = body[:4096].decode("ascii", errors="ignore").lower()
        if "charset=utf-8" in head or 'charset="utf-8"' in head or "charset='utf-8'" in head:
            charset = "utf-8"
        else:
            charset = header_charset or "utf-8"

        return body.decode(charset, errors="replace"), res.geturl()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def attr_value(tag: str, name: str) -> str | None:
    pattern = re.compile(rf"\b{re.escape(name)}\s*=\s*(['\"])(.*?)\1", re.I | re.S)
    match = pattern.search(tag)
    return html.unescape(match.group(2)).strip() if match else None


def meta_content(doc: str, key: str) -> str | None:
    for tag in re.findall(r"<meta\b[^>]*>", doc, re.I | re.S):
        prop = attr_value(tag, "property") or attr_value(tag, "name")
        if prop == key:
            return attr_value(tag, "content")
    return None


def canonical_url(doc: str, fallback: str) -> str:
    match = re.search(r"<link\b[^>]*rel\s*=\s*['\"]canonical['\"][^>]*>", doc, re.I | re.S)
    if match:
        href = attr_value(match.group(0), "href")
        if href:
            return href
    og = meta_content(doc, "og:url")
    return og or fallback


def strip_site_suffix(title: str) -> str:
    title = clean_text(title)
    title = re.sub(r"\s*-\s*عربجي\s*$", "", title).strip()
    return title


def extract_title(doc: str) -> str | None:
    for pattern in (
        r"<h1\b[^>]*id\s*=\s*['\"]post-title['\"][^>]*>(.*?)</h1>",
        r"<h1\b[^>]*>(.*?)</h1>",
    ):
        match = re.search(pattern, doc, re.I | re.S)
        if match:
            title = strip_site_suffix(match.group(1))
            if title:
                return title

    og = meta_content(doc, "og:title")
    if og:
        return strip_site_suffix(og)

    match = re.search(r"<title\b[^>]*>(.*?)</title>", doc, re.I | re.S)
    if match:
        return strip_site_suffix(match.group(1))

    return None


def extract_date(doc: str) -> str | None:
    for pattern in (
        r"<meta\b[^>]*(?:property|name)\s*=\s*['\"]article:published_time['\"][^>]*>",
        r"<meta\b[^>]*content\s*=\s*['\"][^'\"]+['\"][^>]*(?:property|name)\s*=\s*['\"]article:published_time['\"][^>]*>",
    ):
        match = re.search(pattern, doc, re.I | re.S)
        if match:
            content = attr_value(match.group(0), "content")
            if content:
                return content[:10]

    match = re.search(r"<time\b[^>]*datetime\s*=\s*(['\"])(.*?)\1", doc, re.I | re.S)
    if match:
        return html.unescape(match.group(2)).strip()[:10]

    return None


def extract_image(doc: str, page_url: str) -> str | None:
    image = meta_content(doc, "og:image")
    if image:
        return urljoin(page_url, image)

    match = re.search(r"<img\b[^>]*class\s*=\s*['\"][^'\"]*wp-post-image[^'\"]*['\"][^>]*>", doc, re.I | re.S)
    if match:
        src = attr_value(match.group(0), "src")
        if src:
            return urljoin(page_url, src)

    return None


def extract_first_description(doc: str) -> str | None:
    post_match = re.search(r"<div\b[^>]*id\s*=\s*['\"]post['\"][^>]*>(.*?)<iframe\b", doc, re.I | re.S)
    if post_match:
        text = clean_text(post_match.group(1))
        if text:
            return text

    desc = meta_content(doc, "description") or meta_content(doc, "og:description")
    return clean_text(desc) if desc else None


def unique_named(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out: list[dict[str, Any]] = []
    for item in items:
        name = clean_text(item.get("name"))
        if not name or name in seen:
            continue
        seen.add(name)
        new_item = {"name": name}
        urls = item.get("urls")
        if urls:
            new_item["urls"] = urls
        out.append(new_item)
    return out


def link_items_from_block(block: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tag in re.findall(r"<a\b[^>]*>.*?</a>", block, re.I | re.S):
        name = clean_text(tag)
        if not name:
            continue
        href = attr_value(tag, "href")
        item: dict[str, Any] = {"name": name}
        if href:
            item["urls"] = [href]
        items.append(item)
    return unique_named(items)


def extract_class_blocks(doc: str, class_name: str) -> list[str]:
    pattern = re.compile(
        rf"<div\b[^>]*class\s*=\s*['\"][^'\"]*\b{re.escape(class_name)}\b[^'\"]*['\"][^>]*>(.*?)</div>",
        re.I | re.S,
    )
    return [m.group(1) for m in pattern.finditer(doc)]


def extract_tags(doc: str) -> list[dict[str, Any]]:
    tags: list[dict[str, Any]] = []
    for class_name in ("post-page-tags", "post-preview-tags"):
        for block in extract_class_blocks(doc, class_name):
            tags.extend(link_items_from_block(block))
    return unique_named(tags)


def extract_performers(doc: str) -> list[dict[str, Any]]:
    # Arabgy stores performer-like names in WordPress categories.
    performers: list[dict[str, Any]] = []
    for class_name in ("post-page-category", "post-preview-category"):
        for block in extract_class_blocks(doc, class_name):
            performers.extend(link_items_from_block(block))
    return unique_named(performers)


def is_ad_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(fragment in host for fragment in AD_HOST_FRAGMENT_DENYLIST)


def normalize_url(url: str, page_url: str) -> str:
    return urljoin(page_url, html.unescape(url).replace("\\/", "/").strip())


def extract_embeds(doc: str, page_url: str) -> list[dict[str, str]]:
    embeds: list[dict[str, str]] = []
    seen = set()

    def add(url: str, label: str = "Primary embed") -> None:
        normalized = normalize_url(url, page_url)
        if not normalized or is_ad_url(normalized):
            return
        if normalized in seen:
            return
        seen.add(normalized)
        embeds.append({"kind": "embed", "label": label, "url": normalized})

    for tag in re.findall(r"<iframe\b[^>]*>", doc, re.I | re.S):
        src = attr_value(tag, "src")
        if src:
            add(src, "Primary embed" if not embeds else f"Embed {len(embeds) + 1}")

    # TubeAce-style server switcher used by related Arabic source sites.
    for match in re.finditer(
        r"\bgo\s*\(\s*(['\"])(?P<url>https?://.*?|//.*?)\1\s*,\s*(['\"])(?P<label>.*?)\3\s*\)",
        doc,
        re.I | re.S,
    ):
        add(match.group("url"), clean_text(match.group("label")) or f"Server {len(embeds) + 1}")

    return embeds


def enhance_online_media(media: dict[str, Any], page_url: str) -> dict[str, Any]:
    if online_hosts is None or not hasattr(online_hosts, "enhance_online_media"):
        return media

    enhancer = online_hosts.enhance_online_media
    attempts = (
        lambda: enhancer(media, page_url=page_url, user_agent=USER_AGENT),
        lambda: enhancer(media, page_url, USER_AGENT),
        lambda: enhancer(media, page_url),
        lambda: enhancer(media),
    )

    for attempt in attempts:
        try:
            enhanced = attempt()
            return enhanced if isinstance(enhanced, dict) else media
        except TypeError:
            continue
        except Exception:
            return media

    return media


def build_online_media(doc: str, page_url: str) -> dict[str, Any] | None:
    embeds = extract_embeds(doc, page_url)
    if not embeds:
        return None

    media: dict[str, Any] = {
        "source_type": SOURCE_TYPE,
        "page_url": page_url,
        "embed_url": embeds[0]["url"],
        "streams": embeds,
    }

    return enhance_online_media(media, page_url)


def scrape_scene(url: str) -> dict[str, Any]:
    doc, final_url = fetch_html(url)
    scene_url = canonical_url(doc, final_url)
    title = extract_title(doc)
    image = extract_image(doc, scene_url)
    details = extract_first_description(doc)
    tags = extract_tags(doc)
    performers = extract_performers(doc)
    online_media = build_online_media(doc, scene_url)

    scene: dict[str, Any] = {
        "title": title,
        "urls": [scene_url],
        "date": extract_date(doc),
        "details": details,
        "image": image,
        "studio": {
            "name": STUDIO_NAME,
            "url": STUDIO_URL,
        },
        "tags": tags,
        "performers": performers,
    }

    if online_media:
        scene["online_media"] = online_media

    # Drop null/empty values but keep empty arrays out too.
    return {k: v for k, v in scene.items() if v not in (None, "", [], {})}


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Arabgy scenes.")
    sub = parser.add_subparsers(dest="operation", required=True)

    scene_parser = sub.add_parser("scene-by-url")
    scene_parser.add_argument("--url", required=True)

    args = parser.parse_args()

    if args.operation == "scene-by-url":
        print(json.dumps(scrape_scene(args.url), ensure_ascii=False, indent=2))
        return 0

    parser.error(f"unsupported operation: {args.operation}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
