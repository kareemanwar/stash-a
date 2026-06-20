#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_DIR = SCRIPT_DIR.parent / "_shared"
if SHARED_DIR.exists():
    sys.path.insert(0, str(SHARED_DIR))

try:
    import online_hosts  # type: ignore
except Exception:
    online_hosts = None  # type: ignore

SOURCE_TYPE = "Shraraa"
STUDIO_NAME = "Shraraa"
STUDIO_URL = "https://shraraa.com/"
USER_AGENT = "Mozilla/5.0 (compatible; Stash-a Shraraa scraper)"


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = html_lib.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def absolute_url(url: str, base_url: str = STUDIO_URL) -> str:
    url = html_lib.unescape((url or "").strip())
    if not url:
        return ""
    return urllib.parse.urljoin(base_url, url)


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


def meta_content(doc: str, key: str) -> str:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(key)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(key)}["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, doc, flags=re.I | re.S)
        if m:
            return html_lib.unescape(m.group(1)).strip()
    return ""


def canonical_url(doc: str, fallback_url: str) -> str:
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', doc, flags=re.I | re.S)
    if m:
        return absolute_url(m.group(1), fallback_url)
    og = meta_content(doc, "og:url")
    if og:
        return absolute_url(og, fallback_url)
    return fallback_url


def extract_title(doc: str) -> str:
    for pattern in [
        r'<h1[^>]+id=["\']post-title["\'][^>]*>(.*?)</h1>',
        r'<h1[^>]*>(.*?)</h1>',
    ]:
        m = re.search(pattern, doc, flags=re.I | re.S)
        if m:
            title = clean(m.group(1))
            if title:
                return title

    for key in ("og:title", "twitter:title"):
        title = clean(meta_content(doc, key))
        if title:
            return re.sub(r"\s+-\s+.*$", "", title).strip()

    m = re.search(r"<title[^>]*>(.*?)</title>", doc, flags=re.I | re.S)
    if m:
        return re.sub(r"\s+-\s+.*$", "", clean(m.group(1))).strip()

    return ""


def extract_image(doc: str, base_url: str) -> str:
    image = meta_content(doc, "og:image")
    if image:
        return absolute_url(image, base_url)

    m = re.search(r'<img[^>]+class=["\'][^"\']*wp-post-image[^"\']*["\'][^>]+src=["\']([^"\']+)["\']', doc, flags=re.I | re.S)
    if m:
        return absolute_url(m.group(1), base_url)

    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]+class=["\'][^"\']*wp-post-image[^"\']*["\']', doc, flags=re.I | re.S)
    if m:
        return absolute_url(m.group(1), base_url)

    return ""


def extract_date(doc: str) -> str:
    value = meta_content(doc, "article:published_time")
    if value and re.match(r"\d{4}-\d{2}-\d{2}", value):
        return value[:10]

    m = re.search(r'<time[^>]+datetime=["\']([^"\']+)["\']', doc, flags=re.I | re.S)
    if m and re.match(r"\d{4}-\d{2}-\d{2}", m.group(1)):
        return m.group(1)[:10]

    return ""


def find_first_class_block(doc: str, class_name: str) -> str:
    pattern = rf'<(?:div|span|p)[^>]+class=["\'][^"\']*\b{re.escape(class_name)}\b[^"\']*["\'][^>]*>(.*?)</(?:div|span|p)>'
    m = re.search(pattern, doc, flags=re.I | re.S)
    return m.group(1) if m else ""


def extract_anchor_items(block: str, base_url: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block, flags=re.I | re.S):
        url = absolute_url(m.group(1), base_url)
        name = clean(m.group(2))
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        item: dict[str, Any] = {"name": name}
        if url:
            item["urls"] = [url]
        out.append(item)
    return out


def merge_named_items(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            name = clean(item.get("name"))
            if not name:
                continue
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out


def extract_tags(doc: str, base_url: str, include_category: bool = True) -> list[dict[str, Any]]:
    tag_blocks = [
        find_first_class_block(doc, "post-page-tags"),
        find_first_class_block(doc, "post-preview-tags"),
        find_first_class_block(doc, "sticky-post-preview-tags"),
    ]
    category_blocks = []
    if include_category:
        category_blocks = [
            find_first_class_block(doc, "post-page-category"),
            find_first_class_block(doc, "post-preview-category"),
            find_first_class_block(doc, "sticky-post-preview-category"),
        ]

    tag_items: list[dict[str, Any]] = []
    for block in tag_blocks + category_blocks:
        if block:
            tag_items.extend(extract_anchor_items(block, base_url))

    # Yoast JSON-LD often exposes scene tags as keywords and categories as articleSection.
    for key in ("keywords", "articleSection"):
        for match in re.finditer(rf'"{key}"\s*:\s*(\[[^\]]+\]|"[^"]+")', doc, flags=re.I | re.S):
            raw = match.group(1)
            names: list[str] = []
            if raw.startswith("["):
                names = re.findall(r'"([^"]+)"', raw)
            else:
                names = [raw.strip('"')]
            for name in names:
                clean_name = clean(name)
                if clean_name:
                    tag_items.append({"name": clean_name})

    return merge_named_items(tag_items)


def extract_details(doc: str) -> str:
    title = clean(extract_title(doc))
    content = doc

    post_match = re.search(
        r'<div[^>]+id=["\']post["\'][^>]*>(.*?)(?:<header>|<div[^>]+class=["\']row["\'])',
        doc,
        flags=re.I | re.S,
    )
    if post_match:
        content = post_match.group(1)

    paragraphs: list[str] = []
    skip_fragments = [
        "الصفحة الرئيسة",
        "أنطلاق موقع",
        "انطلاق موقع",
        "اذا لم يعمل لديك الفيديو",
        "إذا لم يعمل لديك الفيديو",
        "اترك تعليق",
        "لن يتم نشر عنوان بريدك الإلكتروني",
        "الحقول الإلزامية",
    ]

    for paragraph_match in re.finditer(
        r'<p[^>]*class=["\']wp-block-paragraph["\'][^>]*>(.*?)</p>',
        content,
        flags=re.I | re.S,
    ):
        value = clean(paragraph_match.group(1))
        if not value or len(value) <= 8:
            continue
        if title and value == title:
            continue
        if any(fragment in value for fragment in skip_fragments):
            continue
        paragraphs.append(value)

    return "\n\n".join(dict.fromkeys(paragraphs[:3]))

def extract_embed_urls(doc: str, base_url: str) -> list[str]:
    urls: list[str] = []

    for m in re.finditer(r'<iframe[^>]+src=["\']([^"\']+)["\']', doc, flags=re.I | re.S):
        urls.append(absolute_url(m.group(1), base_url))

    for m in re.finditer(r"go\(\s*['\"]([^'\"]+)['\"]\s*\)", doc, flags=re.I | re.S):
        urls.append(absolute_url(m.group(1), base_url))

    out: list[str] = []
    seen: set[str] = set()
    blocked_hosts = {
        "diagnosedecorationvideotape.com",
        "www.diagnosedecorationvideotape.com",
    }

    for url in urls:
        if not url:
            continue
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc.lower() in blocked_hosts:
            continue
        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        out.append(url)

    return out


def enhance_media(page_url: str, doc: str, media: dict[str, Any]) -> dict[str, Any]:
    if online_hosts is None or not hasattr(online_hosts, "enhance_online_media"):
        return media

    func = online_hosts.enhance_online_media

    # Current shared helper signature:
    # enhance_online_media(media, page_url, *, user_agent, source_slug, clean_text, max_embed_probes=8)
    try:
        enhanced = func(
            media,
            page_url,
            user_agent=USER_AGENT,
            source_slug=SOURCE_TYPE.lower(),
            clean_text=clean,
        )
        if isinstance(enhanced, dict):
            return enhanced
    except TypeError:
        pass
    except Exception:
        return media

    # Compatibility fallback for older local helper signatures.
    attempts = [
        lambda: func(media),
        lambda: func(page_url, media),
        lambda: func(doc, page_url, media),
    ]

    for attempt in attempts:
        try:
            enhanced = attempt()
            if isinstance(enhanced, dict):
                return enhanced
        except TypeError:
            continue
        except Exception:
            continue

    return media

def build_online_media(page_url: str, doc: str, image: str) -> dict[str, Any] | None:
    embeds = extract_embed_urls(doc, page_url)
    if not embeds:
        return None

    streams = []
    for index, embed_url in enumerate(embeds, start=1):
        label = "Primary embed" if index == 1 else f"Embed {index}"
        streams.append({
            "label": label,
            "url": embed_url,
            "embed_url": embed_url,
            "type": "embed",
            "format": "embed",
        })

    media: dict[str, Any] = {
        "source_type": SOURCE_TYPE,
        "page_url": page_url,
        "embed_url": embeds[0],
        "thumbnail": image,
        "streams": streams,
    }

    return enhance_media(page_url, doc, media)


def scrape_scene(url: str) -> dict[str, Any]:
    doc, final_url = fetch_html(url)
    page_url = canonical_url(doc, final_url)

    title = extract_title(doc) or page_url
    image = extract_image(doc, page_url)
    date = extract_date(doc)
    tags = extract_tags(doc, page_url, include_category=True)
    details = extract_details(doc)
    online_media = build_online_media(page_url, doc, image)

    urls = []
    for candidate in [page_url, final_url, url]:
        candidate = absolute_url(candidate, page_url)
        if candidate and candidate not in urls:
            urls.append(candidate)

    scene: dict[str, Any] = {
        "title": title,
        "urls": urls,
        "studio": {
            "name": STUDIO_NAME,
            "url": STUDIO_URL,
        },
        "tags": tags,
    }

    if date:
        scene["date"] = date
    if details:
        scene["details"] = details
    if image:
        scene["image"] = image
        scene["thumbnail"] = image
    if online_media:
        scene["online_media"] = online_media

    return scene


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    scene_parser = sub.add_parser("scene-by-url")
    scene_parser.add_argument("--url", required=True)

    args = parser.parse_args()

    if args.command == "scene-by-url":
        print(json.dumps(scrape_scene(args.url), ensure_ascii=False, indent=2))
        return

    raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
