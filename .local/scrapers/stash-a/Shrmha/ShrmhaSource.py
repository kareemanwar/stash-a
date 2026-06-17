import argparse
import html
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote_plus, urlencode, urljoin, urlparse, urlunparse

import Shrmha


DEFAULT_SOURCE_PAGE_LIMIT = 500
DEFAULT_HYDRATION_DELAY_SECONDS = 1.0
DEFAULT_HYDRATION_JITTER_SECONDS = 0.5
DEFAULT_HYDRATION_RETRIES = 2
DEFAULT_HYDRATION_BACKOFF_SECONDS = 2.0

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


def first_query_value(query: dict[str, list[str]], key: str) -> str | None:
    value = Shrmha.first(query.get(key))
    if isinstance(value, str) and value:
        return value
    return None


def listing_page_number(url: str) -> int:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("paged", "page"):
        value = first_query_value(query, key)
        if value and value.isdigit():
            return max(1, int(value))

    path_page = re.search(r"/page/(\d+)/?", parsed.path)
    if path_page:
        return max(1, int(path_page.group(1)))

    return 1


def canonical_source_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query.pop("paged", None)
    query.pop("page", None)

    path = parsed.path or "/"
    path = re.sub(r"/page/\d+/?$", "/", path)

    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc or urlparse(Shrmha.STUDIO_URL).netloc,
            path or "/",
            "",
            urlencode(query, doseq=True),
            "",
        )
    )


def listing_page_url(seed_url: str, page_number: int) -> str:
    parsed = urlparse(canonical_source_url(seed_url))
    query = parse_qs(parsed.query, keep_blank_values=True)

    if page_number > 1:
        query["paged"] = [str(page_number)]
    else:
        query.pop("paged", None)
        query.pop("page", None)

    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc or urlparse(Shrmha.STUDIO_URL).netloc,
            parsed.path or "/",
            "",
            urlencode(query, doseq=True),
            "",
        )
    )


def normalize_listing_url(url: str, base_url: str) -> str:
    absolute_url = urljoin(base_url, html.unescape(url).strip())
    candidate_page = listing_page_number(absolute_url)
    candidate_query = parse_qs(urlparse(absolute_url).query)
    base_query = parse_qs(urlparse(base_url).query)

    seed_url = absolute_url
    if "s" in base_query and "s" not in candidate_query:
        seed_url = base_url

    return listing_page_url(seed_url, candidate_page)


def is_site_root(url: str) -> bool:
    parsed = urlparse(canonical_source_url(url))
    root = urlparse(Shrmha.STUDIO_URL)
    return parsed.netloc == root.netloc and parsed.path in ("", "/") and not parsed.query


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

    def add(raw_url: str | None) -> None:
        if not raw_url:
            return
        candidate = normalize_listing_url(raw_url, base_url)
        if candidate in seen:
            return
        seen.add(candidate)
        urls.append(candidate)

    for match in re.finditer(
        r'<link\b[^>]*rel=["\'][^"\']*(?:next|prev)[^"\']*["\'][^>]*href=["\'](?P<url>[^"\']+)["\']',
        document,
        re.IGNORECASE | re.DOTALL,
    ):
        add(match.group("url"))

    for match in re.finditer(
        r'<link\b[^>]*href=["\'](?P<url>[^"\']+)["\'][^>]*rel=["\'][^"\']*(?:next|prev)[^"\']*["\']',
        document,
        re.IGNORECASE | re.DOTALL,
    ):
        add(match.group("url"))

    pagination = re.search(r'<div\b[^>]*id=["\']tubeace-pagination["\'][^>]*>(?P<body>.*?)</div>\s*</nav>', document, re.IGNORECASE | re.DOTALL)
    body = pagination.group("body") if pagination else document
    for match in re.finditer(r'<a\b(?P<attrs>[^>]*)>', body, re.IGNORECASE | re.DOTALL):
        attrs = match.group("attrs")
        href = attr_value(attrs, "href")
        class_name = attr_value(attrs, "class") or ""
        if "page-numbers" in class_name or re.search(r"(?:[?&](?:paged|page)=|/page/\d+)", href or ""):
            add(href)

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


def parse_page_limit(value: Any) -> int | None:
    if value in (None, ""):
        return DEFAULT_SOURCE_PAGE_LIMIT
    try:
        max_pages = int(value)
    except (TypeError, ValueError):
        return DEFAULT_SOURCE_PAGE_LIMIT
    if max_pages <= 0:
        return None
    return max_pages


def parse_candidate_limit(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return None
    return limit if limit > 0 else None


def parse_float(value: Any, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, parsed)


def parse_int(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def crawl_listing_pages(
    url: str,
    max_pages: int | None = DEFAULT_SOURCE_PAGE_LIMIT,
    candidate_limit: int | None = None,
) -> tuple[list[tuple[str, str]], bool]:
    start_urls = [canonical_source_url(url)]
    normalized_input_url = normalize_listing_url(url, url)
    if normalized_input_url not in start_urls:
        start_urls.append(normalized_input_url)

    documents: list[tuple[str, str]] = []
    queued: list[str] = list(start_urls)
    queued_set: set[str] = set(start_urls)
    seen: set[str] = set()
    candidate_urls_seen: set[str] = set()
    truncated = False

    while queued:
        if max_pages is not None and len(documents) >= max_pages:
            truncated = True
            break

        page_url = queued.pop(0)
        queued_set.discard(page_url)
        if page_url in seen:
            continue

        document = Shrmha.fetch_html(page_url)
        seen.add(page_url)
        documents.append((page_url, document))

        for candidate in extract_scene_candidates(document, page_url):
            urls = candidate.get("urls")
            if isinstance(urls, list) and urls:
                first_url = urls[0]
                if isinstance(first_url, str) and first_url:
                    candidate_urls_seen.add(first_url)

        if candidate_limit is not None and len(candidate_urls_seen) >= candidate_limit:
            truncated = True
            break

        for next_url in extract_pagination_urls(document, page_url):
            if next_url in seen or next_url in queued_set:
                continue
            if max_pages is not None and len(seen) + len(queued) >= max_pages:
                truncated = True
                continue
            queued.append(next_url)
            queued_set.add(next_url)

    if queued:
        truncated = True

    return documents, truncated


def collect_scene_candidates(
    documents: list[tuple[str, str]],
    candidate_limit: int | None = None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for page_url, document in documents:
        for candidate in extract_scene_candidates(document, page_url):
            url = candidate["urls"][0]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            candidate["candidate_position"] = len(candidates)
            candidates.append(candidate)
            if candidate_limit is not None and len(candidates) >= candidate_limit:
                return candidates

    return candidates


def candidate_urls(candidate: dict[str, Any]) -> list[str]:
    urls = candidate.get("urls")
    if not isinstance(urls, list):
        return []
    return [url for url in urls if isinstance(url, str) and url]


def merge_unique_strings(*values: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, list):
            items = [item for item in value if isinstance(item, str)]
        else:
            continue

        for item in items:
            if not item or item in seen:
                continue
            seen.add(item)
            merged.append(item)

    return merged


def merge_tags(*tag_lists: Any) -> list[dict[str, str]]:
    tags: list[dict[str, str]] = []
    seen: set[str] = set()
    for tag_list in tag_lists:
        if not isinstance(tag_list, list):
            continue
        for tag in tag_list:
            if isinstance(tag, dict):
                name = tag.get("name")
            elif isinstance(tag, str):
                name = tag
            else:
                continue
            if not isinstance(name, str):
                continue
            name = Shrmha.clean_text(name)
            if not name or name in seen:
                continue
            seen.add(name)
            tags.append({"name": name})
    return tags


def run_scene_by_url(
    url: str,
    retries: int = DEFAULT_HYDRATION_RETRIES,
    backoff_seconds: float = DEFAULT_HYDRATION_BACKOFF_SECONDS,
) -> dict[str, Any]:
    script_dir = Path(__file__).resolve().parent
    script_path = script_dir / "ShrmhaOnline.py"
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    last_error = ""
    for attempt in range(retries + 1):
        result = subprocess.run(
            [sys.executable, str(script_path), "scene-by-url", "--url", url],
            cwd=script_dir,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            scene = json.loads(result.stdout)
            if isinstance(scene, dict) and not scene.get("error"):
                return scene
            last_error = str(scene.get("error") if isinstance(scene, dict) else "scene-by-url returned non-object JSON")
        else:
            last_error = result.stderr.strip() or f"scene-by-url failed with exit code {result.returncode}"

        if attempt < retries:
            sleep_for = backoff_seconds * (attempt + 1)
            if sleep_for > 0:
                time.sleep(sleep_for)

    raise RuntimeError(last_error or f"scene-by-url failed for {url}")


def wait_before_hydration(position: int, delay_seconds: float, jitter_seconds: float) -> None:
    if position <= 0:
        return
    sleep_for = delay_seconds
    if jitter_seconds > 0:
        sleep_for += random.uniform(0, jitter_seconds)
    if sleep_for > 0:
        time.sleep(sleep_for)


def merge_scene_candidate(preview: dict[str, Any], scene: dict[str, Any], position: int) -> dict[str, Any]:
    candidate = dict(scene)

    urls = merge_unique_strings(scene.get("urls"), scene.get("url"), preview.get("urls"))
    if urls:
        candidate["urls"] = urls

    for key in ("title", "image", "date", "details", "remote_site_id", "studio"):
        if candidate.get(key) in (None, "", [], {}):
            fallback = preview.get(key)
            if fallback not in (None, "", [], {}):
                candidate[key] = fallback

    tags = merge_tags(scene.get("tags"), preview.get("tags"))
    if tags:
        candidate["tags"] = tags

    candidate["candidate_status"] = preview.get("candidate_status") or "NEW"
    candidate["candidate_position"] = position
    candidate["source_preview"] = preview
    candidate["hydrated_by"] = "scene-by-url"

    return {k: v for k, v in candidate.items() if v not in (None, [], "")}


def hydrate_scene_candidates(
    preview_candidates: list[dict[str, Any]],
    delay_seconds: float = DEFAULT_HYDRATION_DELAY_SECONDS,
    jitter_seconds: float = DEFAULT_HYDRATION_JITTER_SECONDS,
    retries: int = DEFAULT_HYDRATION_RETRIES,
    backoff_seconds: float = DEFAULT_HYDRATION_BACKOFF_SECONDS,
) -> list[dict[str, Any]]:
    hydrated: list[dict[str, Any]] = []

    for position, preview in enumerate(preview_candidates):
        urls = candidate_urls(preview)
        if not urls:
            fallback = dict(preview)
            fallback["candidate_position"] = position
            fallback["hydration_error"] = "Missing candidate URL"
            hydrated.append(fallback)
            continue

        wait_before_hydration(position, delay_seconds, jitter_seconds)

        try:
            scene = run_scene_by_url(urls[0], retries=retries, backoff_seconds=backoff_seconds)
            hydrated.append(merge_scene_candidate(preview, scene, position))
        except Exception as exc:
            fallback = dict(preview)
            fallback["candidate_position"] = position
            fallback["hydration_error"] = str(exc)
            hydrated.append(fallback)

    return hydrated


def scrape_source_by_url(
    url: str,
    max_pages: int | None = DEFAULT_SOURCE_PAGE_LIMIT,
    candidate_limit: int | None = None,
    hydrate_scenes: bool = True,
    hydration_delay_seconds: float = DEFAULT_HYDRATION_DELAY_SECONDS,
    hydration_jitter_seconds: float = DEFAULT_HYDRATION_JITTER_SECONDS,
    hydration_retries: int = DEFAULT_HYDRATION_RETRIES,
    hydration_backoff_seconds: float = DEFAULT_HYDRATION_BACKOFF_SECONDS,
) -> dict[str, Any]:
    page_documents, crawl_truncated = crawl_listing_pages(
        url,
        max_pages=max_pages,
        candidate_limit=candidate_limit,
    )
    if not page_documents:
        return {"error": f"No Shrmha source pages could be fetched for {url}"}

    first_page_url, first_document = page_documents[0]
    source_url = canonical_source_url(url)
    source_title = extract_source_title(source_url, first_document)
    thumbnail_url = extract_source_thumbnail(first_document, first_page_url)
    preview_candidates = collect_scene_candidates(page_documents, candidate_limit=candidate_limit)
    scene_candidates = (
        hydrate_scene_candidates(
            preview_candidates,
            delay_seconds=hydration_delay_seconds,
            jitter_seconds=hydration_jitter_seconds,
            retries=hydration_retries,
            backoff_seconds=hydration_backoff_seconds,
        )
        if hydrate_scenes
        else preview_candidates
    )
    if not thumbnail_url and scene_candidates:
        thumb = scene_candidates[0].get("image")
        thumbnail_url = thumb if isinstance(thumb, str) else None

    query = extract_query(source_url, first_document)
    if query:
        remote_site_id = f"search:{query}"
        source_type = "SEARCH"
    elif is_site_root(source_url):
        remote_site_id = Shrmha.STUDIO_SLUG
        source_type = "SITE"
    else:
        remote_site_id = urlparse(source_url).path or Shrmha.STUDIO_SLUG
        source_type = "SITE_SECTION"

    hydration_error_count = sum(1 for candidate in scene_candidates if candidate.get("hydration_error"))
    result: dict[str, Any] = {
        "title": source_title,
        "urls": [source_url],
        "details": f"{Shrmha.STUDIO_NAME} source scraped from {source_url}",
        "source_type": source_type,
        "thumbnail_url": thumbnail_url,
        "remote_site_id": remote_site_id,
        "scene_candidates": scene_candidates,
        "pagination_urls": [page_url for page_url, _ in page_documents],
        "pages_crawled": len(page_documents),
        "page_limit": 0 if max_pages is None else max_pages,
        "crawl_truncated": crawl_truncated,
        "candidate_limit": 0 if candidate_limit is None else candidate_limit,
        "candidates_returned": len(scene_candidates),
        "scene_hydration": "scene-by-url" if hydrate_scenes else "preview-only",
        "hydration_delay_seconds": hydration_delay_seconds,
        "hydration_jitter_seconds": hydration_jitter_seconds,
        "hydration_retries": hydration_retries,
        "hydration_backoff_seconds": hydration_backoff_seconds,
        "hydration_error_count": hydration_error_count,
    }

    if source_type != "SITE":
        result["parent"] = {
            "title": Shrmha.STUDIO_NAME,
            "urls": [Shrmha.STUDIO_URL],
            "source_type": "SITE",
            "remote_site_id": Shrmha.STUDIO_SLUG,
        }

    return {k: v for k, v in result.items() if v not in (None, [], "")}


def scraper_args() -> tuple[str, dict[str, Any]]:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="operation", required=True)
    source_by_url = subparsers.add_parser("source-by-url")
    source_by_url.add_argument("--url")
    source_by_url.add_argument("--max-pages", dest="max_pages", type=int)
    source_by_url.add_argument("--limit", dest="limit", type=int)
    source_by_url.add_argument("--preview-only", dest="preview_only", action="store_true")
    source_by_url.add_argument("--hydrate-delay", dest="hydrate_delay", type=float)
    source_by_url.add_argument("--hydrate-jitter", dest="hydrate_jitter", type=float)
    source_by_url.add_argument("--hydrate-retries", dest="hydrate_retries", type=int)
    source_by_url.add_argument("--hydrate-backoff", dest="hydrate_backoff", type=float)
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


def get_max_pages_arg(args: dict[str, Any]) -> int | None:
    return parse_page_limit(args.get("max_pages", args.get("maxPages")))


def get_candidate_limit_arg(args: dict[str, Any]) -> int | None:
    return parse_candidate_limit(args.get("limit", args.get("candidate_limit", args.get("candidateLimit"))))


def get_hydrate_scenes_arg(args: dict[str, Any]) -> bool:
    if args.get("preview_only") or args.get("previewOnly"):
        return False
    hydrate_scenes = args.get("hydrate_scenes", args.get("hydrateScenes"))
    if hydrate_scenes is None:
        return True
    return bool(hydrate_scenes)


def main() -> None:
    operation, args = scraper_args()
    if operation == "source-by-url":
        url = get_url_arg(args)
        if url:
            Shrmha.write_json(
                scrape_source_by_url(
                    url,
                    max_pages=get_max_pages_arg(args),
                    candidate_limit=get_candidate_limit_arg(args),
                    hydrate_scenes=get_hydrate_scenes_arg(args),
                    hydration_delay_seconds=parse_float(args.get("hydrate_delay", args.get("hydrateDelay")), DEFAULT_HYDRATION_DELAY_SECONDS),
                    hydration_jitter_seconds=parse_float(args.get("hydrate_jitter", args.get("hydrateJitter")), DEFAULT_HYDRATION_JITTER_SECONDS),
                    hydration_retries=parse_int(args.get("hydrate_retries", args.get("hydrateRetries")), DEFAULT_HYDRATION_RETRIES),
                    hydration_backoff_seconds=parse_float(args.get("hydrate_backoff", args.get("hydrateBackoff")), DEFAULT_HYDRATION_BACKOFF_SECONDS),
                )
            )
            return

    print(json.dumps({"error": f"Unsupported operation or missing URL: {operation}"}), file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
