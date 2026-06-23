#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _shared.fetch import fetch_text, http_safe_url  # noqa: E402
from _shared.output import write_json  # noqa: E402
from _shared.profiles.kvs import parse_scene_page, parse_source_page  # noqa: E402


SOURCE_NAME = "1Porn"
SOURCE_SLUG = "1porn"
SOURCE_URL = "https://www.1porn.tv/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
FETCH_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}
SEARCH_SORT_SEGMENTS = {"relevance", "latest-updates", "top-rated"}
TRANSIENT_HTTP_CODES = {429, 500, 502, 503, 504}


def _fetch_1porn_text(url: str, *, referer: str = SOURCE_URL) -> str:
    headers = dict(FETCH_HEADERS)
    headers["Referer"] = referer
    return fetch_text(url, user_agent=USER_AGENT, headers=headers)


def _decode_response_body(body: bytes) -> str:
    for charset in ("utf-8", "cp1256", "latin-1"):
        try:
            return body.decode(charset, errors="replace")
        except LookupError:
            continue
    return body.decode("utf-8", errors="replace")


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
            return _fetch_1porn_text(url, referer=referer)
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
    raise RuntimeError(f"failed to fetch 1Porn page after retries: {url}: {last_exc}")


def scrape_scene_by_url(url: str) -> dict[str, Any]:
    document = _fetch_text_with_retries(url)
    return parse_scene_page(
        document,
        url,
        source_name=SOURCE_NAME,
        source_slug=SOURCE_SLUG,
        source_url=SOURCE_URL,
    )


def candidate_key(candidate: dict[str, Any]) -> str | None:
    urls = candidate.get("urls")
    if isinstance(urls, list):
        for url in urls:
            if isinstance(url, str) and url:
                return url
    return None


def scrape_source_page(url: str) -> dict[str, Any]:
    document = _fetch_text_with_retries(url)
    return parse_source_page(
        document,
        url,
        source_name=SOURCE_NAME,
        source_slug=SOURCE_SLUG,
        source_url=SOURCE_URL,
    )


def _source_root_path(url: str) -> str:
    path = urlparse(url).path.strip("/")
    parts = [part for part in path.split("/") if part]
    if parts and parts[-1].isdigit():
        parts = parts[:-1]
    if len(parts) >= 2 and parts[0] == "search":
        return "/" + "/".join(parts[:2])
    return "/" + "/".join(parts)


def _pagination_page(url: str, root_path: str) -> int | None:
    path_parts = [part for part in urlparse(url).path.strip("/").split("/") if part]
    root_parts = [part for part in root_path.strip("/").split("/") if part]
    if not root_parts or path_parts == root_parts:
        return None
    if path_parts[: len(root_parts)] != root_parts:
        return None

    remainder = path_parts[len(root_parts) :]

    if len(root_parts) >= 2 and root_parts[0] == "search":
        if len(remainder) == 1 and remainder[0].isdigit():
            return int(remainder[0])
        if len(remainder) == 2 and remainder[0] in SEARCH_SORT_SEGMENTS and remainder[1].isdigit():
            return int(remainder[1])
        return None

    if len(remainder) == 1 and remainder[0].isdigit():
        return int(remainder[0])

    return None


def _is_pagination_url(base_url: str, candidate_url: str) -> bool:
    base = urlparse(base_url)
    candidate = urlparse(candidate_url)
    if candidate.scheme not in ("http", "https"):
        return False
    if candidate.netloc != base.netloc:
        return False
    root = _source_root_path(base_url)
    if _source_root_path(candidate_url) != root:
        return False
    return _pagination_page(candidate_url, root) is not None


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
            if not _is_pagination_url(page_url, next_url):
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
