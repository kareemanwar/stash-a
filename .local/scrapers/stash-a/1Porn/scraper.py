#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _shared.fetch import fetch_text  # noqa: E402
from _shared.output import write_json  # noqa: E402
from _shared.profiles.kvs import parse_scene_page, parse_source_page  # noqa: E402


SOURCE_NAME = "1Porn"
SOURCE_SLUG = "1porn"
SOURCE_URL = "https://www.1porn.tv/"
USER_AGENT = "Mozilla/5.0 (compatible; Stash-a 1Porn scraper)"


def scrape_scene_by_url(url: str) -> dict[str, Any]:
    document = fetch_text(url, user_agent=USER_AGENT, headers={"Referer": SOURCE_URL})
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
    document = fetch_text(url, user_agent=USER_AGENT, headers={"Referer": SOURCE_URL})
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
    return "/" + "/".join(parts)


def _pagination_page(url: str, root_path: str) -> int | None:
    path = urlparse(url).path.strip("/")
    root = root_path.strip("/")
    if not root or path == root:
        return None
    prefix = root + "/"
    if not path.startswith(prefix):
        return None
    remainder = path[len(prefix):].strip("/")
    if remainders := [part for part in remainder.split("/") if part]:
        if len(remainders) == 1 and remainders[0].isdigit():
            return int(remainders[0])
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
    output: dict[str, Any] | None = None

    while queue and len(visited_pages) < max_pages:
        page_url = queue.pop(0)
        if page_url in visited_pages:
            continue
        visited_pages.add(page_url)

        page_output = scrape_source_page(page_url)
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
