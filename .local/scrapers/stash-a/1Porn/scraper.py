#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

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


def scrape_source_by_url(url: str) -> dict[str, Any]:
    document = fetch_text(url, user_agent=USER_AGENT, headers={"Referer": SOURCE_URL})
    return parse_source_page(
        document,
        url,
        source_name=SOURCE_NAME,
        source_slug=SOURCE_SLUG,
        source_url=SOURCE_URL,
    )


def scraper_args() -> tuple[str, dict[str, Any]]:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="operation", required=True)

    scene_by_url = subparsers.add_parser("scene-by-url")
    scene_by_url.add_argument("--url")

    source_by_url = subparsers.add_parser("source-by-url")
    source_by_url.add_argument("--url")

    args = vars(parser.parse_args())

    if not sys.stdin.isatty():
        try:
            stdin_args = json.load(sys.stdin)
            if isinstance(stdin_args, dict):
                args.update(stdin_args)
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
    url = get_url_arg(args)
    if not url:
        print(json.dumps({"error": f"Missing URL for operation: {operation}"}), file=sys.stderr)
        sys.exit(1)

    if operation == "scene-by-url":
        write_json(scrape_scene_by_url(url))
        return

    if operation == "source-by-url":
        write_json(scrape_source_by_url(url))
        return

    print(json.dumps({"error": f"Unsupported operation: {operation}"}), file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
