#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from _shared.fetch import fetch_text, http_safe_url  # type: ignore  # noqa: E402
    from _shared.output import write_json  # type: ignore  # noqa: E402
except Exception:  # pragma: no cover - allows fixture-only local smoke tests
    def http_safe_url(url: str) -> str:
        return url

    def fetch_text(url: str, user_agent: str | None = None, headers: dict[str, str] | None = None) -> str:
        raise RuntimeError("_shared.fetch is not available in this smoke-test context")

    def write_json(value: Any) -> None:
        print(json.dumps(value, ensure_ascii=False, indent=2))


SOURCE_NAME = "Arabgy"
SOURCE_SLUG = "arabgy"
SOURCE_URL = "https://arabgy.com/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
FETCH_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}
TRANSIENT_HTTP_CODES = {429, 500, 502, 503, 504}
IGNORED_IFRAME_HOST_PARTS = {
    "diagnosedecorationvideotape.com",
    "googlesyndication.com",
    "google.com",
    "doubleclick.net",
}
GENERIC_CATEGORY_NAMES = {
    "منوع مشاهير",
}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = " ".join(text.split()).strip()
    return text or None


def drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in value.items() if v not in (None, "", [], {})}


def unique_strings(*values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        items = value if isinstance(value, list) else [value]
        for item in items:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if item and item not in seen:
                seen.add(item)
                out.append(item)
    return out


def unique_dicts_by_name(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        name = clean_text(value.get("name"))
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        item = dict(value)
        item["name"] = name
        out.append(drop_empty(item))
    return out


def attr_value(attrs: str, name: str) -> str | None:
    match = re.search(rf"\b{re.escape(name)}\s*=\s*(['\"])(?P<value>.*?)\1", attrs, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return html.unescape(match.group("value")).strip() or None


def absolute_url(base_url: str, value: str | None) -> str | None:
    value = clean_text(value)
    if not value or value.startswith("data:"):
        return None
    return urljoin(base_url, value)


def meta_content(document: str, key: str) -> str | None:
    patterns = [
        rf'<meta\b[^>]*(?:property|name)=(["\']){re.escape(key)}\1[^>]*content=(["\'])(?P<value>.*?)\2',
        rf'<meta\b[^>]*content=(["\'])(?P<value>.*?)\1[^>]*(?:property|name)=(["\']){re.escape(key)}\3',
    ]
    for pattern in patterns:
        match = re.search(pattern, document, re.IGNORECASE | re.DOTALL)
        if match:
            return clean_text(match.group("value"))
    return None


def link_href(document: str, rel: str) -> str | None:
    patterns = [
        rf'<link\b[^>]*rel=["\'][^"\']*\b{re.escape(rel)}\b[^"\']*["\'][^>]*href=(["\'])(?P<value>.*?)\1',
        rf'<link\b[^>]*href=(["\'])(?P<value>.*?)\1[^>]*rel=["\'][^"\']*\b{re.escape(rel)}\b[^"\']*["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, document, re.IGNORECASE | re.DOTALL)
        if match:
            return html.unescape(match.group("value")).strip() or None
    return None


def title_match(document: str, tag: str, element_id: str | None = None) -> str | None:
    if element_id:
        pattern = rf'<{tag}\b[^>]*id=["\']{re.escape(element_id)}["\'][^>]*>(?P<value>.*?)</{tag}>'
    else:
        pattern = rf'<{tag}\b[^>]*>(?P<value>.*?)</{tag}>'
    match = re.search(pattern, document, re.IGNORECASE | re.DOTALL)
    return clean_text(match.group("value")) if match else None


def strip_site_suffix(title: str | None) -> str | None:
    if not title:
        return None
    title = re.sub(r"\s*[-–—|]\s*عربجي\s*$", "", title, flags=re.IGNORECASE).strip()
    title = re.sub(r"\s*[-–—|]\s*موقع عربجي\s*$", "", title, flags=re.IGNORECASE).strip()
    return title or None


def first_non_empty(*values: Any) -> str | None:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return None


def extract_jsonld(document: str) -> list[Any]:
    values: list[Any] = []
    for match in re.finditer(
        r'<script\b[^>]*type\s*=\s*(["\'])application/ld\+json\1[^>]*>(?P<body>.*?)</script>',
        document,
        re.IGNORECASE | re.DOTALL,
    ):
        try:
            values.append(json.loads(html.unescape(match.group("body")).strip()))
        except Exception:
            continue
    return values


def walk_json(value: Any):
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from walk_json(item)
        for child in value.values():
            if isinstance(child, (dict, list)) and child is not graph:
                yield from walk_json(child)
    elif isinstance(value, list):
        for item in value:
            yield from walk_json(item)


def jsonld_objects(document: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for root in extract_jsonld(document):
        for obj in walk_json(root):
            out.append(obj)
    return out


def jsonld_type_matches(obj: dict[str, Any], type_name: str) -> bool:
    value = obj.get("@type")
    if isinstance(value, str):
        return value.casefold() == type_name.casefold()
    if isinstance(value, list):
        return any(isinstance(item, str) and item.casefold() == type_name.casefold() for item in value)
    return False


def first_jsonld_object(document: str, *types: str) -> dict[str, Any]:
    for obj in jsonld_objects(document):
        if any(jsonld_type_matches(obj, type_name) for type_name in types):
            return obj
    return {}


def jsonld_first_string(value: Any) -> str | None:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        for item in value:
            text = jsonld_first_string(item)
            if text:
                return text
    if isinstance(value, dict):
        return first_non_empty(value.get("url"), value.get("contentUrl"))
    return None


def parse_date(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
    return match.group(1) if match else text


def make_stream(label: str, kind: str, url: str, position: int = 0, is_primary: bool = False) -> dict[str, Any]:
    return drop_empty({"label": label, "kind": kind, "url": url, "position": position, "is_primary": is_primary})


def raw_metadata(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _decode_response_body(body: bytes) -> str:
    for charset in ("utf-8", "cp1256", "windows-1256", "latin-1"):
        try:
            return body.decode(charset, errors="replace")
        except LookupError:
            continue
    return body.decode("utf-8", errors="replace")


def _fetch_arabgy_text(url: str, *, referer: str = SOURCE_URL) -> str:
    headers = dict(FETCH_HEADERS)
    headers["Referer"] = referer
    return fetch_text(url, user_agent=USER_AGENT, headers=headers)


def _curl_fetch_text(url: str, *, referer: str = SOURCE_URL, timeout: int = 45) -> str:
    curl = shutil.which("curl")
    if not curl:
        raise RuntimeError("curl executable was not found")

    headers = dict(FETCH_HEADERS)
    headers["Referer"] = referer
    headers["User-Agent"] = USER_AGENT

    cmd = [
        curl,
        "--location",
        "--silent",
        "--show-error",
        "--fail",
        "--compressed",
        "--http1.1",
        "--max-time",
        str(timeout),
    ]
    for key, value in headers.items():
        cmd.extend(["--header", f"{key}: {value}"])
    cmd.append(http_safe_url(url))

    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"curl fetch failed ({result.returncode}) for {url}: {stderr}")
    return _decode_response_body(result.stdout)


def _fetch_text_with_retries(url: str, *, referer: str = SOURCE_URL, attempts: int = 4, delay: float = 2.0) -> str:
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return _fetch_arabgy_text(url, referer=referer)
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code not in TRANSIENT_HTTP_CODES:
                raise
            try:
                return _curl_fetch_text(url, referer=referer)
            except Exception as curl_exc:
                last_exc = curl_exc
                if attempt >= attempts:
                    raise
        except urllib.error.URLError as exc:
            last_exc = exc
            try:
                return _curl_fetch_text(url, referer=referer)
            except Exception as curl_exc:
                last_exc = curl_exc
                if attempt >= attempts:
                    raise
        time.sleep(delay * attempt)
    raise RuntimeError(f"failed to fetch Arabgy page after retries: {url}: {last_exc}")


def extract_post_id(document: str, page_url: str) -> str | None:
    for pattern in [
        r'<article\b[^>]*id=["\']post-(?P<id>\d+)["\']',
        r'\bpost-(?P<id>\d+)\b',
        r'<link\b[^>]*rel=["\']shortlink["\'][^>]*href=["\'][^"\']*[?&]p=(?P<id>\d+)',
        r'<link\b[^>]*href=["\'][^"\']*[?&]p=(?P<id>\d+)[^"\']*["\'][^>]*rel=["\']shortlink["\']',
    ]:
        match = re.search(pattern, document, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group("id")
    path = urlparse(page_url).path.strip("/")
    return path or None


def extract_anchor_dicts(block: str, base_url: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for match in re.finditer(r"<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a>", block, re.IGNORECASE | re.DOTALL):
        name = clean_text(match.group("body"))
        if not name:
            continue
        href = attr_value(match.group("attrs"), "href")
        urls = unique_strings(urljoin(base_url, href)) if href else []
        values.append(drop_empty({"name": name, "urls": urls}))
    return unique_dicts_by_name(values)


def extract_class_block(document: str, class_name: str) -> str | None:
    match = re.search(
        rf'<div\b[^>]*class=["\'][^"\']*\b{re.escape(class_name)}\b[^"\']*["\'][^>]*>(?P<body>.*?)</div>',
        document,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group("body") if match else None


def extract_scene_blocks(document: str) -> list[str]:
    blocks = [match.group(1) for match in re.finditer(r"<!--\s*start preview\s*-->(.*?)<!--\s*end preview\s*-->", document, re.IGNORECASE | re.DOTALL)]
    if blocks:
        return blocks

    blocks = []
    starts = [match.start() for match in re.finditer(r'<div\b[^>]*class=["\'][^"\']*\bpost-preview\b[^"\']*["\']', document, re.IGNORECASE)]
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(document)
        blocks.append(document[start:end])
    return blocks


def remove_generic_performer_categories(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        value
        for value in values
        if clean_text(value.get("name")) not in GENERIC_CATEGORY_NAMES
    ]


def extract_listing_candidates(document: str, page_url: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, block in enumerate(extract_scene_blocks(document)):
        title_attrs = None
        title_body = None
        for link_match in re.finditer(r"<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a>", block, re.IGNORECASE | re.DOTALL):
            attrs = link_match.group("attrs")
            class_name = attr_value(attrs, "class") or ""
            if "preview-title" in class_name:
                title_attrs = attrs
                title_body = link_match.group("body")
                break
        if title_attrs is None:
            h2_match = re.search(r"<h2\b[^>]*>\s*<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a>", block, re.IGNORECASE | re.DOTALL)
            if h2_match:
                title_attrs = h2_match.group("attrs")
                title_body = h2_match.group("body")
        if title_attrs is None:
            continue

        href = attr_value(title_attrs, "href")
        url = absolute_url(page_url, href)
        if not url or url in seen:
            continue
        seen.add(url)

        title = first_non_empty(attr_value(title_attrs, "title"), title_body)
        image = None
        image_match = re.search(r"<img\b(?P<attrs>[^>]*)>", block, re.IGNORECASE | re.DOTALL)
        if image_match:
            image_attrs = image_match.group("attrs")
            image = absolute_url(page_url, attr_value(image_attrs, "data-src") or attr_value(image_attrs, "src"))
            title = title or clean_text(attr_value(image_attrs, "alt"))

        tag_block = extract_class_block(block, "post-preview-tags") or ""
        category_block = extract_class_block(block, "post-preview-category") or ""
        tags = extract_anchor_dicts(tag_block, page_url)
        performers = remove_generic_performer_categories(extract_anchor_dicts(category_block, page_url))
        date_text = clean_text(extract_class_block(block, "preview-date"))
        remote_site_id = extract_post_id(block, url)

        candidates.append(
            drop_empty(
                {
                    "title": title,
                    "urls": [url],
                    "image": image,
                    "details": title,
                    "date": date_text,
                    "studio": {"name": SOURCE_NAME, "urls": [SOURCE_URL], "remote_site_id": SOURCE_SLUG},
                    "performers": performers,
                    "tags": tags,
                    "remote_site_id": remote_site_id,
                    "candidate_status": "NEW",
                    "candidate_position": position,
                    "source_preview": drop_empty({"date_text": date_text}),
                }
            )
        )
    return candidates


def extract_pagination_urls(document: str, base_url: str) -> list[str]:
    urls = []
    seen: set[str] = set()
    rel_next = link_href(document, "next")
    if rel_next:
        url = urljoin(base_url, rel_next)
        seen.add(url)
        urls.append(url)

    for match in re.finditer(r"<a\b(?P<attrs>[^>]*)>", document, re.IGNORECASE | re.DOTALL):
        attrs = match.group("attrs")
        href = attr_value(attrs, "href")
        class_name = attr_value(attrs, "class") or ""
        rel = attr_value(attrs, "rel") or ""
        if not href:
            continue
        candidate = urljoin(base_url, href)
        if "page-numbers" not in class_name and "next" not in class_name and "next" not in rel and not re.search(r"/page/\d+/?", candidate):
            continue
        if candidate not in seen:
            seen.add(candidate)
            urls.append(candidate)
    return urls


def source_root_path(url: str) -> str:
    path = urlparse(url).path.strip("/")
    path = re.sub(r"(?:^|/)page/\d+/?$", "", path).strip("/")
    return "/" + path if path else "/"


def same_search_query(base_url: str, candidate_url: str) -> bool:
    base_query = parse_qs(urlparse(base_url).query)
    candidate_query = parse_qs(urlparse(candidate_url).query)
    if "s" not in base_query:
        return True
    return candidate_query.get("s") == base_query.get("s") or "/search/" in urlparse(candidate_url).path


def is_pagination_url(base_url: str, candidate_url: str) -> bool:
    base = urlparse(base_url)
    candidate = urlparse(candidate_url)
    if candidate.scheme not in ("http", "https"):
        return False
    if candidate.netloc.lower() != base.netloc.lower():
        return False
    if not re.search(r"/page/\d+/?", candidate.path) and "paged=" not in candidate.query:
        return False
    if not same_search_query(base_url, candidate_url):
        return False
    root = source_root_path(base_url).rstrip("/")
    candidate_path = candidate.path.rstrip("/")
    if root == "":
        return True
    if root == "/":
        return bool(re.match(r"^/page/\d+/?$", candidate.path)) or "paged=" in candidate.query or "/search/" in candidate.path
    return candidate_path.startswith(root + "/page/") or candidate_path == root


def infer_source_type(url: str) -> str:
    parsed = urlparse(url)
    if parsed.query and "s=" in parsed.query:
        return "SEARCH"
    if "/category/" in parsed.path:
        return "CATEGORY"
    return "INDEX"


def extract_post_block(document: str) -> str | None:
    match = re.search(r'<div\b[^>]*id=["\']post["\'][^>]*>(?P<body>.*?)(?:<div\b[^>]*id=["\']comments["\']|</article>)', document, re.IGNORECASE | re.DOTALL)
    return match.group("body") if match else None


def extract_iframe_streams(document: str, base_url: str) -> list[dict[str, Any]]:
    streams: list[dict[str, Any]] = []
    post_block = extract_post_block(document) or document
    for match in re.finditer(r"<iframe\b(?P<attrs>[^>]*)>", post_block, re.IGNORECASE | re.DOTALL):
        src = attr_value(match.group("attrs"), "src")
        if not src:
            continue
        url = urljoin(base_url, src)
        host = urlparse(url).netloc.lower()
        if any(part in host for part in IGNORED_IFRAME_HOST_PARTS):
            continue
        streams.append(make_stream(f"Embed {len(streams) + 1}", "embed", url, len(streams), len(streams) == 0))
    return streams


def extract_first_post_paragraph(document: str) -> str | None:
    post_block = extract_post_block(document) or document
    match = re.search(r"<p\b[^>]*>(?P<body>.*?)</p>", post_block, re.IGNORECASE | re.DOTALL)
    return clean_text(match.group("body")) if match else None


def extract_scene_taxonomy(document: str, class_name: str, base_url: str) -> list[dict[str, Any]]:
    block = extract_class_block(document, class_name) or ""
    return extract_anchor_dicts(block, base_url)


def scrape_scene_by_url(url: str) -> dict[str, Any]:
    document = _fetch_text_with_retries(url)
    return parse_scene_page(document, url)


def parse_scene_page(document: str, page_url: str) -> dict[str, Any]:
    article_obj = first_jsonld_object(document, "Article")
    web_page_obj = first_jsonld_object(document, "WebPage")
    canonical_url = absolute_url(page_url, link_href(document, "canonical")) or meta_content(document, "og:url") or page_url
    title = strip_site_suffix(
        first_non_empty(
            meta_content(document, "og:title"),
            article_obj.get("headline"),
            web_page_obj.get("name"),
            title_match(document, "h1", "post-title"),
            title_match(document, "title"),
        )
    )
    description = first_non_empty(
        meta_content(document, "og:description"),
        meta_content(document, "description"),
        web_page_obj.get("description"),
        extract_first_post_paragraph(document),
    )
    image = first_non_empty(
        meta_content(document, "og:image"),
        jsonld_first_string(article_obj.get("thumbnailUrl")),
        jsonld_first_string(web_page_obj.get("thumbnailUrl")),
    )
    if image:
        image = urljoin(canonical_url, image)

    date = parse_date(
        meta_content(document, "article:published_time")
        or article_obj.get("datePublished")
        or web_page_obj.get("datePublished")
    )
    external_id = extract_post_id(document, canonical_url)
    streams = extract_iframe_streams(document, canonical_url)
    embed_url = streams[0]["url"] if streams else None
    tags = extract_scene_taxonomy(document, "post-page-tags", canonical_url)
    performers = remove_generic_performer_categories(extract_scene_taxonomy(document, "post-page-category", canonical_url))
    if not tags:
        keywords = article_obj.get("keywords")
        if isinstance(keywords, list):
            tags = unique_dicts_by_name([{"name": item} for item in keywords if isinstance(item, str)])
    if not performers:
        sections = article_obj.get("articleSection")
        if isinstance(sections, list):
            performers = unique_dicts_by_name([{"name": item} for item in sections if isinstance(item, str)])
        elif isinstance(sections, str):
            performers = unique_dicts_by_name([{"name": sections}])

    online_media = drop_empty(
        {
            "source_name": SOURCE_NAME,
            "source_slug": SOURCE_SLUG,
            "external_id": external_id,
            "embed_url": embed_url,
            "thumbnail_url": image,
            "streams": streams,
        }
    )
    online_media["raw_metadata_json"] = raw_metadata(
        {
            "source": SOURCE_SLUG,
            "external_id": external_id,
            "canonical_url": canonical_url,
            "stream_count": len(streams),
            "embed_stream_count": len([stream for stream in streams if stream.get("kind") == "embed"]),
            "jsonld_article": bool(article_obj),
            "jsonld_web_page": bool(web_page_obj),
            "performers_from_category": bool(performers),
        }
    )

    return drop_empty(
        {
            "title": title,
            "urls": unique_strings(canonical_url, page_url),
            "details": description,
            "date": date,
            "image": image,
            "studio": {"name": SOURCE_NAME, "urls": [SOURCE_URL], "remote_site_id": SOURCE_SLUG},
            "tags": tags,
            "performers": performers,
            "remote_site_id": external_id,
            "online_media": online_media,
        }
    )


def scrape_source_page(url: str) -> dict[str, Any]:
    document = _fetch_text_with_retries(url)
    return parse_source_page(document, url)


def parse_source_page(document: str, page_url: str) -> dict[str, Any]:
    canonical_url = absolute_url(page_url, link_href(document, "canonical")) or meta_content(document, "og:url") or page_url
    title = strip_site_suffix(first_non_empty(meta_content(document, "og:title"), title_match(document, "h1", "taxonomy-name"), title_match(document, "h1", "search-title"), title_match(document, "title")))
    thumbnail_url = absolute_url(page_url, meta_content(document, "og:image"))
    candidates = extract_listing_candidates(document, page_url)
    pagination_urls = extract_pagination_urls(document, page_url)
    return drop_empty(
        {
            "title": title,
            "urls": [canonical_url],
            "details": f"{SOURCE_NAME} source scraped from {canonical_url}",
            "source_type": infer_source_type(page_url),
            "thumbnail_url": thumbnail_url,
            "remote_site_id": urlparse(canonical_url).path.strip("/") or SOURCE_SLUG,
            "scene_candidates": candidates,
            "pagination_urls": pagination_urls,
            "pages_crawled": 1,
            "candidates_returned": len(candidates),
            "scene_hydration": "preview-only",
        }
    )


def candidate_key(candidate: dict[str, Any]) -> str | None:
    urls = candidate.get("urls")
    if isinstance(urls, list):
        for url in urls:
            if isinstance(url, str) and url:
                return url
    return None


def scrape_source_by_url(url: str, *, limit: int | None = None, max_pages: int = 1) -> dict[str, Any]:
    max_pages = max(1, max_pages)
    queue: list[str] = [url]
    visited_pages: set[str] = set()
    seen_candidates: set[str] = set()
    candidates: list[dict[str, Any]] = []
    pagination_urls: list[str] = []
    crawl_errors: list[dict[str, Any]] = []
    output: dict[str, Any] | None = None

    while queue and len(visited_pages) < max_pages:
        page_url = queue.pop(0)
        if page_url in visited_pages:
            continue

        try:
            page_output = scrape_source_page(page_url)
        except Exception as exc:
            crawl_errors.append({"url": page_url, "error": str(exc)})
            if output is None:
                raise
            break

        visited_pages.add(page_url)
        if output is None:
            output = page_output

        for candidate in page_output.get("scene_candidates") or []:
            if not isinstance(candidate, dict):
                continue
            key = candidate_key(candidate)
            if not key or key in seen_candidates:
                continue
            seen_candidates.add(key)
            candidates.append(candidate)
            if limit is not None and limit >= 0 and len(candidates) >= limit:
                break

        for next_url in page_output.get("pagination_urls") or []:
            if not isinstance(next_url, str) or not next_url:
                continue
            if not is_pagination_url(page_url, next_url):
                continue
            if next_url not in pagination_urls:
                pagination_urls.append(next_url)
            if next_url not in visited_pages and next_url not in queue:
                queue.append(next_url)

        if limit is not None and limit >= 0 and len(candidates) >= limit:
            break

    if output is None:
        output = scrape_source_page(url)

    if limit is not None and limit >= 0:
        candidates = candidates[:limit]

    output["scene_candidates"] = candidates
    output["pagination_urls"] = pagination_urls
    output["pages_crawled"] = len(visited_pages)
    output["candidates_returned"] = len(candidates)
    if crawl_errors:
        output["crawl_errors"] = crawl_errors
    return output


def scraper_args() -> tuple[str, dict[str, Any]]:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="operation", required=True)

    scene_by_url = subparsers.add_parser("scene-by-url")
    scene_by_url.add_argument("--url")

    source_by_url = subparsers.add_parser("source-by-url")
    source_by_url.add_argument("--url")
    source_by_url.add_argument("--limit", type=int)
    source_by_url.add_argument("--max-pages", type=int, default=1)
    source_by_url.add_argument("--preview-only", action="store_true")

    args = vars(parser.parse_args())

    if not sys.stdin.isatty():
        stdin_text = sys.stdin.read().strip()
        if stdin_text:
            try:
                stdin_args = json.loads(stdin_text)
                if isinstance(stdin_args, dict):
                    args.update(stdin_args)
            except json.JSONDecodeError:
                print(json.dumps({"error": "Invalid scraper JSON stdin"}), file=sys.stderr)
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
    url = get_url_arg(args)
    if not url:
        print(json.dumps({"error": f"Missing URL for operation: {operation}"}), file=sys.stderr)
        sys.exit(1)

    if operation == "scene-by-url":
        write_json(scrape_scene_by_url(url))
        return

    if operation == "source-by-url":
        limit = args.get("limit")
        max_pages = args.get("max_pages")
        write_json(
            scrape_source_by_url(
                url,
                limit=limit if isinstance(limit, int) else None,
                max_pages=max_pages if isinstance(max_pages, int) else 1,
            )
        )
        return

    print(json.dumps({"error": f"Unsupported operation: {operation}"}), file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
