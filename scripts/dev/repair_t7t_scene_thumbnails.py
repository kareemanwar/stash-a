#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path.cwd()

DEFAULT_GRAPHQL = "http://127.0.0.1:9999/graphql"
DEFAULT_DOMAIN = "t7t-al7zam.com"
DEFAULT_SCRAPER = ROOT / ".local" / "scrapers" / "stash-a" / "T7tAl7zam" / "T7tAl7zam.py"
REPORT_PATH = ROOT / "scripts" / "dev" / "repair_t7t_scene_thumbnails_report.json"

UA = "stash-a-thumbnail-repair/1.0"


def log(msg: str) -> None:
    print(msg, flush=True)


def request_json(url: str, payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": UA,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False, indent=2))
    return data


def gql(graphql_url: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    return request_json(graphql_url, {"query": query, "variables": variables or {}})["data"]


def abs_stash_url(graphql_url: str, path_or_url: str | None) -> str | None:
    if not path_or_url:
        return None
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    parsed = urllib.parse.urlparse(graphql_url)
    return f"{parsed.scheme}://{parsed.netloc}{path_or_url}"


def fetch_all_scenes(graphql_url: str, per_page: int, max_pages: int | None) -> list[dict[str, Any]]:
    query = """
    query FindScenes($filter: FindFilterType) {
      findScenes(filter: $filter) {
        count
        scenes {
          id
          title
          url
          urls
          paths {
            screenshot
          }
        }
      }
    }
    """

    out: list[dict[str, Any]] = []
    page = 1
    total = None

    while True:
        if max_pages is not None and page > max_pages:
            break

        data = gql(graphql_url, query, {"filter": {"page": page, "per_page": per_page}})
        result = data["findScenes"]
        total = result.get("count")
        scenes = result.get("scenes") or []

        out.extend(scenes)
        log(f"Fetched page {page}: {len(scenes)} scenes; accumulated {len(out)} / {total}")

        if not scenes:
            break
        if total is not None and len(out) >= int(total):
            break

        page += 1

    return out


def scene_urls(scene: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    singular = scene.get("url")
    if isinstance(singular, str) and singular.strip():
        urls.append(singular.strip())

    many = scene.get("urls")
    if isinstance(many, list):
        for u in many:
            if isinstance(u, str) and u.strip():
                urls.append(u.strip())

    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            unique.append(u)
            seen.add(u)
    return unique


def is_target_scene(scene: dict[str, Any], domain: str) -> bool:
    d = domain.lower()
    return any(d in u.lower() for u in scene_urls(scene))


def pick_target_url(scene: dict[str, Any], domain: str) -> str | None:
    d = domain.lower()
    for u in scene_urls(scene):
        if d in u.lower():
            return u
    return None


def http_status_and_type(url: str, timeout: int = 15) -> tuple[int | None, str | None, int | None]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "image/*,*/*"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            chunk = resp.read(512)
            code = resp.getcode()
            ctype = resp.headers.get("Content-Type")
            clen = resp.headers.get("Content-Length")
            size = int(clen) if clen and clen.isdigit() else len(chunk)
            return code, ctype, size
    except Exception:
        return None, None, None


def scene_appears_to_have_cover(graphql_url: str, scene: dict[str, Any]) -> bool:
    paths = scene.get("paths") or {}
    screenshot = paths.get("screenshot") if isinstance(paths, dict) else None
    screenshot_url = abs_stash_url(graphql_url, screenshot)
    if not screenshot_url:
        return False

    code, ctype, size = http_status_and_type(screenshot_url)
    if code != 200:
        return False
    if ctype and "image" not in ctype.lower():
        return False
    if size is not None and size < 200:
        return False
    return True



def ascii_safe_url(url: str) -> str:
    """Convert decoded Arabic/non-ASCII URLs to percent-encoded HTTP-safe URLs."""
    url = (url or "").strip()
    parts = urllib.parse.urlsplit(url)

    # Decode first to avoid double-encoding already escaped URLs, then quote.
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/%")
    query = urllib.parse.quote(
        urllib.parse.unquote(parts.query),
        safe="=&?/:+,%"
    )
    fragment = urllib.parse.quote(
        urllib.parse.unquote(parts.fragment),
        safe="=&?/:+,%"
    )

    return urllib.parse.urlunsplit((
        parts.scheme,
        parts.netloc.encode("idna").decode("ascii") if parts.netloc else parts.netloc,
        path,
        query,
        fragment,
    ))


def run_scraper(scraper: Path, url: str, timeout: int = 60) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    safe_url = ascii_safe_url(url)

    proc = subprocess.run(
        [sys.executable, str(scraper), "scene-by-url", "--url", safe_url],
        cwd=str(ROOT),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )

    if proc.returncode != 0:
        raise RuntimeError(f"scraper failed rc={proc.returncode}\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}")

    return json.loads(proc.stdout)


def download_image_as_data_url(image_url: str, timeout: int = 45) -> tuple[str, int, str]:
    req = urllib.request.Request(
        image_url,
        headers={
            "User-Agent": UA,
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://t7t-al7zam.com/",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        ctype = resp.headers.get("Content-Type") or ""

    if not data or len(data) < 200:
        raise RuntimeError(f"downloaded image is too small: {len(data)} bytes")

    ctype_clean = ctype.split(";")[0].strip().lower()
    if not ctype_clean.startswith("image/"):
        guessed, _ = mimetypes.guess_type(image_url)
        ctype_clean = guessed or "image/jpeg"

    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{ctype_clean};base64,{b64}", len(data), ctype_clean


def update_scene_cover(graphql_url: str, scene_id: str, cover_data_url: str) -> dict[str, Any]:
    mutation = """
    mutation SceneUpdate($input: SceneUpdateInput!) {
      sceneUpdate(input: $input) {
        id
        title
        paths {
          screenshot
        }
      }
    }
    """
    return gql(graphql_url, mutation, {"input": {"id": scene_id, "cover_image": cover_data_url}})["sceneUpdate"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graphql", default=DEFAULT_GRAPHQL)
    ap.add_argument("--domain", default=DEFAULT_DOMAIN)
    ap.add_argument("--scraper", default=str(DEFAULT_SCRAPER))
    ap.add_argument("--per-page", type=int, default=100)
    ap.add_argument("--max-pages", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sleep", type=float, default=0.25)
    ap.add_argument("--apply", action="store_true", help="Actually update Stash. Without this, dry-run only.")
    ap.add_argument("--force", action="store_true", help="Update even if a scene appears to already have a cover.")
    ap.add_argument("--scene-id", action="append", default=[], help="Only process this scene id. Can be repeated.")
    args = ap.parse_args()

    scraper = Path(args.scraper)
    if not scraper.exists():
        raise SystemExit(f"Missing scraper: {scraper}")

    log("=== T7t thumbnail repair ===")
    log(f"mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    log(f"graphql: {args.graphql}")
    log(f"domain: {args.domain}")
    log(f"scraper: {scraper}")

    scenes = fetch_all_scenes(args.graphql, args.per_page, args.max_pages)

    wanted_ids = set(str(x) for x in args.scene_id)
    targets = []
    for s in scenes:
        if wanted_ids and str(s.get("id")) not in wanted_ids:
            continue
        if is_target_scene(s, args.domain):
            targets.append(s)

    log(f"\nTarget scenes matching {args.domain}: {len(targets)}")

    if args.limit is not None:
        targets = targets[: args.limit]
        log(f"Limited to first {len(targets)} target scenes")

    report: list[dict[str, Any]] = []

    for idx, scene in enumerate(targets, 1):
        scene_id = str(scene.get("id"))
        title = scene.get("title") or ""
        url = pick_target_url(scene, args.domain)

        item: dict[str, Any] = {
            "scene_id": scene_id,
            "title": title,
            "url": url,
            "status": None,
            "image": None,
            "error": None,
        }

        log(f"\n[{idx}/{len(targets)}] scene {scene_id}: {title[:100]}")

        try:
            if not url:
                item["status"] = "skip_no_target_url"
                log("  SKIP: no target URL")
                report.append(item)
                continue

            has_cover = scene_appears_to_have_cover(args.graphql, scene)
            item["had_cover"] = has_cover

            if has_cover and not args.force:
                item["status"] = "skip_existing_cover"
                log("  SKIP: appears to already have a cover")
                report.append(item)
                continue

            scraped = run_scraper(scraper, url)
            image_url = scraped.get("image")
            item["image"] = image_url

            if not image_url:
                item["status"] = "skip_scraper_no_image"
                log("  SKIP: scraper returned no image")
                report.append(item)
                continue

            log(f"  scraper image: {image_url}")

            if not args.apply:
                item["status"] = "dry_run_would_update"
                log("  DRY-RUN: would download image and update cover_image")
                report.append(item)
                continue

            cover_data_url, byte_count, ctype = download_image_as_data_url(image_url)
            item["image_bytes"] = byte_count
            item["image_content_type"] = ctype

            updated = update_scene_cover(args.graphql, scene_id, cover_data_url)
            item["status"] = "updated"
            item["updated_screenshot"] = ((updated.get("paths") or {}).get("screenshot"))
            log(f"  UPDATED: {byte_count} bytes, {ctype}")

            time.sleep(args.sleep)

        except Exception as e:
            item["status"] = "error"
            item["error"] = str(e)
            log(f"  ERROR: {e}")

        report.append(item)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    counts: dict[str, int] = {}
    for item in report:
        counts[str(item.get("status"))] = counts.get(str(item.get("status")), 0) + 1

    log("\n=== summary ===")
    for k, v in sorted(counts.items()):
        log(f"{k}: {v}")
    log(f"\nReport: {REPORT_PATH}")
    log("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
