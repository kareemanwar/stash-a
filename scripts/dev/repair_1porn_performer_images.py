#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ENDPOINT = "http://localhost:9999/graphql"
DEFAULT_REPORT = Path("scripts/dev/reports/repair_1porn_performer_images_report.json")
USER_AGENT = "Mozilla/5.0 (compatible; Stash-a 1Porn performer image repair)"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def clean(v: Any) -> str | None:
    if not isinstance(v, str):
        return None
    v = " ".join(v.split()).strip()
    return v or None


def strings(v: Any) -> list[str]:
    if isinstance(v, str) and v:
        return [v]
    if isinstance(v, list):
        return [x for x in v if isinstance(x, str) and x]
    return []


def uniq(items: list[str]) -> list[str]:
    ret: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ret.append(item)
    return ret


def gql(endpoint: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables or {}}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            data = json.loads(res.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GraphQL request failed: {exc}") from exc
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False, indent=2))
    return data.get("data") or {}


def fetch_performers(endpoint: str, page: int, per_page: int) -> tuple[int, list[dict[str, Any]]]:
    data = gql(
        endpoint,
        """
        query($page: Int!, $perPage: Int!) {
          findPerformers(filter: { page: $page, per_page: $perPage }) {
            count
            performers { id name urls image_path }
          }
        }
        """,
        {"page": page, "perPage": per_page},
    )
    result = data.get("findPerformers") or {}
    performers = [x for x in result.get("performers") or [] if isinstance(x, dict)]
    return int(result.get("count") or 0), performers


def update_performer_image(endpoint: str, performer_id: str, image_url: str) -> dict[str, Any]:
    data = gql(
        endpoint,
        """
        mutation($input: PerformerUpdateInput!) {
          performerUpdate(input: $input) { id name image_path }
        }
        """,
        {"input": {"id": performer_id, "image": image_url}},
    )
    return data["performerUpdate"]


def oneporn_model_url(performer: dict[str, Any]) -> str | None:
    for url in strings(performer.get("urls")):
        parsed = urllib.parse.urlsplit(url)
        host = parsed.netloc.lower()
        if host in {"1porn.tv", "www.1porn.tv"} and parsed.path.startswith("/models/"):
            return urllib.parse.urlunsplit((parsed.scheme or "https", parsed.netloc or "www.1porn.tv", parsed.path, "", ""))
    return None


def fetch_html(url: str, timeout: int) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        content_type = res.headers.get_content_charset() or "utf-8"
        return res.read().decode(content_type, errors="replace")


class ImageCandidateParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta_images: list[str] = []
        self.link_images: list[str] = []
        self.img_images: list[str] = []
        self.jsonld_texts: list[str] = []
        self._in_jsonld = False
        self._jsonld_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k.lower(): v or "" for k, v in attrs}
        tag = tag.lower()
        if tag == "meta":
            key = (attr.get("property") or attr.get("name") or attr.get("itemprop") or "").lower()
            if key in {"og:image", "og:image:url", "twitter:image", "twitter:image:src", "image"}:
                value = clean(attr.get("content"))
                if value:
                    self.meta_images.append(value)
        elif tag == "link":
            rel = attr.get("rel", "").lower()
            if "image_src" in rel:
                value = clean(attr.get("href"))
                if value:
                    self.link_images.append(value)
        elif tag == "img":
            cls = attr.get("class", "").lower()
            src = clean(attr.get("data-src")) or clean(attr.get("src"))
            if src and ("model" in cls or "avatar" in cls or "thumb" in cls or "poster" in cls or "image" in cls):
                self.img_images.append(src)
        elif tag == "script":
            script_type = attr.get("type", "").lower()
            if "ld+json" in script_type:
                self._in_jsonld = True
                self._jsonld_chunks = []

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self._jsonld_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_jsonld:
            text = "".join(self._jsonld_chunks).strip()
            if text:
                self.jsonld_texts.append(text)
            self._in_jsonld = False
            self._jsonld_chunks = []


def jsonld_images(value: Any) -> list[str]:
    ret: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"image", "thumbnail", "thumbnailUrl", "contentUrl"}:
                ret.extend(strings(item))
                if isinstance(item, dict):
                    ret.extend(jsonld_images(item))
                elif isinstance(item, list):
                    ret.extend(jsonld_images(item))
            else:
                ret.extend(jsonld_images(item))
    elif isinstance(value, list):
        for item in value:
            ret.extend(jsonld_images(item))
    elif isinstance(value, str) and value.startswith("http"):
        ret.append(value)
    return ret


def normalize_image_url(base_url: str, value: str) -> str | None:
    value = clean(value)
    if not value:
        return None
    if value.startswith("data:"):
        return None
    url = urllib.parse.urljoin(base_url, value)
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    lower = url.lower()
    if any(x in lower for x in ("favicon", "logo", "apple-touch-icon", ".svg")):
        return None
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def score_image(url: str) -> tuple[int, str]:
    lower = url.lower()
    score = 0
    if "img.1porn.tv" in lower:
        score += 50
    if "/models/" in lower or "/model" in lower:
        score += 20
    if any(ext in lower for ext in (".jpg", ".jpeg", ".png", ".webp")):
        score += 10
    if "medium" in lower or "large" in lower or "preview" in lower:
        score += 5
    return (-score, lower)


def extract_image_url(page_url: str, html: str) -> str | None:
    parser = ImageCandidateParser()
    parser.feed(html)
    candidates: list[str] = []
    candidates.extend(parser.meta_images)
    candidates.extend(parser.link_images)
    for text in parser.jsonld_texts:
        try:
            candidates.extend(jsonld_images(json.loads(text)))
        except json.JSONDecodeError:
            continue
    candidates.extend(parser.img_images)

    normalized = [url for value in candidates if (url := normalize_image_url(page_url, value))]
    normalized = uniq(normalized)
    if not normalized:
        return None
    normalized.sort(key=score_image)
    return normalized[0]


def validate_image_url(url: str, timeout: int) -> bool:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Range": "bytes=0-0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            content_type = (res.headers.get("Content-Type") or "").lower()
            if content_type.startswith("image/"):
                return True
            return any(urllib.parse.urlsplit(url).path.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp"))
    except Exception:
        return False


def resolve_performer_image(url: str, timeout: int, validate: bool, cache: dict[str, str | None]) -> str | None:
    if url in cache:
        return cache[url]
    html = fetch_html(url, timeout)
    image_url = extract_image_url(url, html)
    if image_url and validate and not validate_image_url(image_url, timeout):
        image_url = None
    cache[url] = image_url
    return image_url


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=ENDPOINT)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true", help="legacy compatibility; repair already updates matching 1Porn performers by default")
    parser.add_argument("--skip-existing-image", action="store_true", help="skip performers when Stash reports image_path; image_path may be generated even without a real custom image")
    parser.add_argument("--limit", type=int, help="maximum matching performers to process")
    parser.add_argument("--start-at", type=int, default=1, help="1-based matching performer offset")
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--no-validate-images", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    stats = {
        "scanned": 0,
        "matched_1porn_url": 0,
        "skipped_existing_image": 0,
        "skipped_before_start": 0,
        "processed": 0,
        "dry_run": 0,
        "updated": 0,
        "no_image_found": 0,
        "errors": 0,
    }
    entries: list[dict[str, Any]] = []
    image_cache: dict[str, str | None] = {}
    matching_index = 0
    page = 1
    total = None

    log(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    while total is None or (page - 1) * args.per_page < total:
        total, performers = fetch_performers(args.endpoint, page, args.per_page)
        if not performers:
            break
        for performer in performers:
            stats["scanned"] += 1
            performer_id = str(performer.get("id"))
            name = clean(performer.get("name")) or performer_id
            model_url = oneporn_model_url(performer)
            if not model_url:
                continue
            stats["matched_1porn_url"] += 1
            matching_index += 1
            if args.skip_existing_image and clean(performer.get("image_path")) and not args.force:
                stats["skipped_existing_image"] += 1
                continue
            if matching_index < max(1, args.start_at):
                stats["skipped_before_start"] += 1
                continue
            if args.limit is not None and stats["processed"] >= args.limit:
                break

            prefix = f"[performer#{matching_index} id={performer_id}]"
            stats["processed"] += 1
            entry = {"id": performer_id, "name": name, "url": model_url, "status": "pending"}
            try:
                log(f"{prefix} FETCH {name!r} {model_url}")
                image_url = resolve_performer_image(model_url, args.timeout, not args.no_validate_images, image_cache)
                if not image_url:
                    stats["no_image_found"] += 1
                    entry["status"] = "no_image_found"
                    log(f"{prefix} NO_IMAGE {name!r}")
                elif not args.apply:
                    stats["dry_run"] += 1
                    entry.update({"status": "dry_run", "image": image_url})
                    log(f"{prefix} DRY image={image_url}")
                else:
                    updated = update_performer_image(args.endpoint, performer_id, image_url)
                    stats["updated"] += 1
                    entry.update({"status": "updated", "image": image_url, "image_path": updated.get("image_path")})
                    log(f"{prefix} UPDATED image=yes name={name!r}")
            except Exception as exc:
                stats["errors"] += 1
                entry.update({"status": "error", "error": str(exc)})
                log(f"{prefix} ERROR {name!r}: {exc}")
            entries.append(entry)
            if args.sleep:
                time.sleep(args.sleep)

        if args.limit is not None and stats["processed"] >= args.limit:
            break
        page += 1

    report = {"stats": stats, "entries": entries}
    write_report(args.report, report)
    log(f"Report written: {args.report}")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
