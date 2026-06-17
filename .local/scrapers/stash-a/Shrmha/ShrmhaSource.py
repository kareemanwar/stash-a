import argparse
import html
import json
import re
import sys
from typing import Any
from urllib.parse import parse_qs, unquote_plus, urljoin, urlparse

import Shrmha


ARABIC_MONTHS = {
    "يناير": 1,
    "فبراير": 2,
    "مارس": 3,
    "أبريل": 4,
    "ابريل": 4,
    "مايو": 5,
    "يونيو": 6,
    "يوليو": 7,
    "أغسطس": 8,
    "اغسطس": 8,
    "سبتمبر": 9,
    "أكتوبر": 10,
    "اكتوبر": 10,
    "نوفمبر": 11,
    "ديسمبر": 12,
}


def strip_tags(value: str | None) -> str:
    if not value:
        return ""
    return Shrmha.clean_text(re.sub(r"<[^>]+>", " ", html.unescape(value)))


def attr_value(attrs: str, name: str) -> str | None:
    pattern = rf"\b{re.escape(name)}=[\"'](?P<value>.*?)[\"']"
    match = re.search(pattern, attrs, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return html.unescape(match.group("value")).strip()


def normalize_preview_date(value: str | None) -> str | None:
    text = Shrmha.clean_text(value)
    if not text:
        return None

    iso_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if iso_match:
        return f"{int(iso_match.group(1)):04d}-{int(iso_match.group(2)):02d}-{int(iso_match.group(3)):02d}"

    arabic_match = re.search(r"([\u0600-\u06FF]+)\s+(\d{1,2})\s*,\s*(\d{4})", text)
    if arabic_match:
        month_name = arabic_match.group(1)
        month = ARABIC_MONTHS.get(month_name)
        if month:
            return f"{int(arabic_match.group(3)):04d}-{month:02d}-{int(arabic_match.group(2)):02d}"

    return text


def extract_query(url: str, document: str) -> str | None:
    parsed = urlparse(url)
    query_value = parse_qs(parsed.query).get("s")
    if query_value:
        return Shrmha.clean_text(unquote_plus(query_value[0]))

    search_title = re.search(r'<h1\b[^>]*id=["\']search-title["\'][^>]*>(?P<title>.*?)</h1>', document, re.IGNORECASE | re.DOTALL)
    if search_title:
        title_text = strip_tags(search_title.group("title"))
        title_text = re.sub(r"^Search Results for:\s*", "", title_text, flags=re.IGNORECASE).strip()
        if title_text:
            return title_text

    return None


def extract_source_title(url: str, document: str) -> str:
    query = extract_query(url, document)
    if query:
        return f"{query} - {Shrmha.STUDIO_NAME}"

    title_match = re.search(r"<title[^>]*>(?P<title>.*?)</title>", document, re.IGNORECASE | re.DOTALL)
    title = strip_tags(title_match.group("title") if title_match else None)
    title = re.sub(r"\s+-\s+شرمها\s*$", "", title).strip()
    return title or Shrmha.STUDIO_NAME


def extract_source_thumbnail(document: str, base_url: str) -> str | None:
    for pattern in [
        r'<meta\b[^>]*(?:property|name)=["\']og:image["\'][^>]*content=["\'](?P<url>[^"\']+)["\']',
        r'<meta\b[^>]*content=["\'](?P<url>[^"\']+)["\'][^>]*(?:property|name)=["\']og:image["\']',
        r'"thumbnailUrl"\s*:\s*"(?P<url>https?:\\?/\\?/[^"\\]+(?:\\/[^"\\]+)*)"',
    ]:
        match = re.search(pattern, document, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        value = html.unescape(match.group("url")).replace("\\/", "/")
        if value:
            return urljoin(base_url, value)
    return None


def extract_pagination_urls(document: str, base_url: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    pagination = re.search(r'<div\b[^>]*id=["\']tubeace-pagination["\'][^>]*>(?P<body>.*?)</div>\s*</nav>', document, re.IGNORECASE | re.DOTALL)
    body = pagination.group("body") if pagination else document
    for match in re.finditer(r'<a\b[^>]*href=["\'](?P<url>[^"\']+)["\'][^>]*class=["\'][^"\']*page-numbers[^"\']*["\']', body, re.IGNORECASE | re.DOTALL):
        candidate = urljoin(base_url, html.unescape(match.group("url")))
        if candidate not in seen:
            seen.add(candidate)
            urls.append(candidate)
    return urls


def extract_external_id(candidate_url: str, block: str) -> str | None:
    parsed = urlparse(candidate_url)
    query_id = Shrmha.first(parse_qs(parsed.query).get("p"))
    if query_id:
        return str(query_id)

    class_id = re.search(r"\bpost-(\d+)\b", block)
    if class_id:
        return class_id.group(1)

    return None


def extract_preview_tags(block: str) -> list[dict[str, str]]:
    tags: list[dict[str, str]] = []
    seen: set[str] = set()
    tag_block = re.search(r'<div\b[^>]*class=["\'][^"\']*post-preview-tags[^"\']*["\'][^>]*>(?P<body>.*?)</div>', block, re.IGNORECASE | re.DOTALL)
    if not tag_block:
        return tags

    for match in re.finditer(r"<a\b[^>]*>(?P<name>.*?)</a>", tag_block.group("body"), re.IGNORECASE | re.DOTALL):
        name = strip_tags(match.group("name"))
        if not name or name in seen:
            continue
        seen.add(name)
        tags.append({"name": name})
    return tags


def parse_preview_block(block: str, base_url: str, position: int) -> dict[str, Any] | None:
    title_match = re.search(
        r'<a\b(?P<attrs>[^>]*class=["\'][^"\']*preview-title[^"\']*["\'][^>]*)>(?P<title>.*?)</a>',
        block,
        re.IGNORECASE | re.DOTALL,
    )
    if not title_match:
        return None

    candidate_url = attr_value(title_match.group("attrs"), "href")
    if not candidate_url:
        return None
    candidate_url = urljoin(base_url, candidate_url)

    title = strip_tags(title_match.group("title"))
    image_url = None
    image_match = re.search(r"<img\b(?P<attrs>[^>]*)>", block, re.IGNORECASE | re.DOTALL)
    if image_match:
        image_url = attr_value(image_match.group("attrs"), "src")
        if image_url:
            image_url = urljoin(base_url, image_url)

    date = None
    date_match = re.search(r'<div\b[^>]*class=["\'][^"\']*preview-date[^"\']*["\'][^>]*>(?P<body>.*?)</div>', block, re.IGNORECASE | re.DOTALL)
    if date_match:
        date = normalize_preview_date(strip_tags(date_match.group("body")))

    external_id = extract_external_id(candidate_url, block)
    candidate: dict[str, Any] = {
        "title": title,
        "urls": [candidate_url],
        "image": image_url,
        "date": date,
        "remote_site_id": external_id,
        "details": title,
        "studio": {
            "name": Shrmha.STUDIO_NAME,
            "urls": [Shrmha.STUDIO_URL],
            "remote_site_id": Shrmha.STUDIO_SLUG,
        },
        "tags": extract_preview_tags(block),
        "candidate_status": "NEW",
        "candidate_position": position,
    }

    return {k: v for k, v in candidate.items() if v not in (None, [], "")}


def extract_scene_candidates(document: str, base_url: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    blocks = re.findall(r"<!--\s*start preview\s*-->(?P<block>.*?)<!--\s*end preview\s*-->", document, re.IGNORECASE | re.DOTALL)

    if not blocks:
        blocks = re.findall(
            r'<div\b[^>]*class=["\'][^"\']*post-preview[^"\']*["\'][^>]*>(?P<block>.*?)</div>\s*<!--\s*end preview\s*-->',
            document,
            re.IGNORECASE | re.DOTALL,
        )

    for block in blocks:
        candidate = parse_preview_block(block, base_url, len(candidates))
        if not candidate:
            continue
        url = candidate["urls"][0]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append(candidate)

    return candidates


def scrape_source_by_url(url: str) -> dict[str, Any]:
    document = Shrmha.fetch_html(url)
    source_title = extract_source_title(url, document)
    thumbnail_url = extract_source_thumbnail(document, url)
    scene_candidates = extract_scene_candidates(document, url)
    if not thumbnail_url and scene_candidates:
        thumb = scene_candidates[0].get("image")
        thumbnail_url = thumb if isinstance(thumb, str) else None

    query = extract_query(url, document)
    remote_site_id = f"search:{query}" if query else urlparse(url).path or Shrmha.STUDIO_SLUG

    result: dict[str, Any] = {
        "title": source_title,
        "urls": [url],
        "details": f"{Shrmha.STUDIO_NAME} source scraped from {url}",
        "source_type": "SEARCH" if query else "SITE_SECTION",
        "thumbnail_url": thumbnail_url,
        "remote_site_id": remote_site_id,
        "parent": {
            "title": Shrmha.STUDIO_NAME,
            "urls": [Shrmha.STUDIO_URL],
            "source_type": "SITE",
            "remote_site_id": Shrmha.STUDIO_SLUG,
        },
        "scene_candidates": scene_candidates,
        "pagination_urls": extract_pagination_urls(document, url),
    }

    return {k: v for k, v in result.items() if v not in (None, [], "")}


def scraper_args() -> tuple[str, dict[str, Any]]:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="operation", required=True)
    subparsers.add_parser("source-by-url").add_argument("--url")
    args = vars(parser.parse_args())

    if not sys.stdin.isatty():
        try:
            args.update(json.load(sys.stdin))
        except json.JSONDecodeError:
            sys.exit(69)

    return args.pop("operation"), args


def get_url_arg(args: dict[str, Any]) -> str | None:
    url = args.get("url")
    if isinstance(url, str) and url:
        return url
    urls = args.get("urls")
    if isinstance(urls, list) and urls:
        first_url = urls[0]
        if isinstance(first_url, str) and first_url:
            return first_url
    return None


def main() -> None:
    operation, args = scraper_args()
    if operation == "source-by-url":
        url = get_url_arg(args)
        if url:
            Shrmha.write_json(scrape_source_by_url(url))
            return

    print(json.dumps({"error": f"Unsupported operation or missing URL: {operation}"}), file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
