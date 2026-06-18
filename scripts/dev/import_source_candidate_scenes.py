#!/usr/bin/env python3
"""Import hydrated source candidate videos as native Stash scenes with live feedback.

This development utility is intentionally GraphQL-first. It creates native Scenes,
links native tags/studios when present in scraper output, and saves online media
through sceneOnlineMediaSave. It never writes side JSON/database state.

Examples:
  python scripts/dev/import_source_candidate_scenes.py --scraper Nafak --url "https://nafakarab.com/" --limit 10
  python scripts/dev/import_source_candidate_scenes.py --scraper Nafak --url "https://nafakarab.com/" --limit 10 --apply
  python scripts/dev/import_source_candidate_scenes.py --scraper Shrmha --url "https://shrmha.com/" --apply
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
SCRAPER_ROOT = ROOT / ".local" / "scrapers" / "stash-a"
DEFAULT_ENDPOINT = "http://localhost:9999/graphql"

SCRAPERS: dict[str, dict[str, str]] = {
    "shrmha": {
        "display": "Shrmha",
        "source_script": "Shrmha/ShrmhaSource.py",
        "scene_script": "Shrmha/ShrmhaOnline.py",
    },
    "nafak": {
        "display": "Nafak",
        "source_script": "Nafak/NafakSourceHydrated.py",
        "scene_script": "Nafak/NafakOnline.py",
    },
}


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def compact(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split()).strip()
    return value or None


def string_list(value: Any) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def unique_strings(values: list[str]) -> list[str]:
    ret: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ret.append(value)
    return ret


def candidate_urls(item: dict[str, Any]) -> list[str]:
    urls = string_list(item.get("urls"))
    media = item.get("online_media")
    if isinstance(media, dict):
        urls.extend(string_list(media.get("direct_video_url")))
        urls.extend(string_list(media.get("embed_url")))
    return unique_strings(urls)


def first_url(item: dict[str, Any]) -> str | None:
    urls = candidate_urls(item)
    return urls[0] if urls else None


def run_json(command: list[str], cwd: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"command failed with exit code {result.returncode}")

    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise RuntimeError("scraper returned non-object JSON")
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data


def gql(endpoint: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables or {}}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GraphQL request failed: {exc}") from exc

    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False, indent=2))
    return data.get("data") or {}


def find_scene_by_exact_url(endpoint: str, url: str) -> dict[str, Any] | None:
    data = gql(
        endpoint,
        """
        query FindSceneByURL($url: String!) {
          findScenes(
            scene_filter: { url: { value: $url, modifier: EQUALS } }
            filter: { per_page: 20 }
          ) {
            scenes { id title urls }
          }
        }
        """,
        {"url": url},
    )
    for scene in data.get("findScenes", {}).get("scenes", []):
        if url in string_list(scene.get("urls")):
            return scene
    return None


def find_scene_by_any_url(endpoint: str, urls: list[str]) -> dict[str, Any] | None:
    for url in unique_strings(urls):
        scene = find_scene_by_exact_url(endpoint, url)
        if scene:
            return scene
    return None


def find_or_create_studio(endpoint: str, studio: dict[str, Any] | None, cache: dict[str, str]) -> str | None:
    if not isinstance(studio, dict):
        return None
    name = compact(studio.get("name"))
    if not name:
        return None

    key = name.casefold()
    if key in cache:
        return cache[key]

    data = gql(
        endpoint,
        """
        query FindStudio($q: String!) {
          findStudios(filter: { q: $q, per_page: 50 }) {
            studios { id name urls }
          }
        }
        """,
        {"q": name},
    )
    for item in data.get("findStudios", {}).get("studios", []):
        if compact(item.get("name")) == name:
            cache[key] = item["id"]
            return item["id"]

    input_value: dict[str, Any] = {"name": name}
    urls = string_list(studio.get("urls"))
    if urls:
        input_value["urls"] = urls

    data = gql(
        endpoint,
        """
        mutation CreateStudio($input: StudioCreateInput!) {
          studioCreate(input: $input) { id name }
        }
        """,
        {"input": input_value},
    )
    created = data["studioCreate"]
    cache[key] = created["id"]
    log(f"    STUDIO created id={created['id']} name={created['name']!r}")
    return created["id"]


def tag_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return compact(value.get("name"))
    return compact(value)


def find_or_create_tag(endpoint: str, name: str, cache: dict[str, str]) -> str:
    key = name.casefold()
    if key in cache:
        return cache[key]

    data = gql(
        endpoint,
        """
        query FindTag($q: String!) {
          findTags(filter: { q: $q, per_page: 50 }) {
            tags { id name }
          }
        }
        """,
        {"q": name},
    )
    for item in data.get("findTags", {}).get("tags", []):
        if compact(item.get("name")) == name:
            cache[key] = item["id"]
            return item["id"]

    data = gql(
        endpoint,
        """
        mutation CreateTag($input: TagCreateInput!) {
          tagCreate(input: $input) { id name }
        }
        """,
        {"input": {"name": name}},
    )
    created = data["tagCreate"]
    cache[key] = created["id"]
    log(f"    TAG created id={created['id']} name={created['name']!r}")
    return created["id"]


def resolve_tag_ids(endpoint: str, scene: dict[str, Any], cache: dict[str, str]) -> list[str]:
    tags = scene.get("tags")
    if not isinstance(tags, list):
        return []

    ids: list[str] = []
    seen: set[str] = set()

    for tag in tags:
        name = tag_name(tag)
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        ids.append(find_or_create_tag(endpoint, name, cache))

    return ids


def create_scene(endpoint: str, scene: dict[str, Any], studio_id: str | None, tag_ids: list[str]) -> dict[str, Any]:
    input_value: dict[str, Any] = {
        "title": compact(scene.get("title")),
        "details": compact(scene.get("details")),
        "urls": unique_strings(string_list(scene.get("urls"))),
        "date": compact(scene.get("date")),
        "organized": False,
    }

    image = compact(scene.get("image"))
    media = scene.get("online_media")
    if not image and isinstance(media, dict):
        image = compact(media.get("thumbnail_url"))
    if image:
        input_value["cover_image"] = image
    if studio_id:
        input_value["studio_id"] = studio_id
    if tag_ids:
        input_value["tag_ids"] = tag_ids

    input_value = {key: value for key, value in input_value.items() if value not in (None, "", [], {})}

    data = gql(
        endpoint,
        """
        mutation CreateScene($input: SceneCreateInput!) {
          sceneCreate(input: $input) { id title urls }
        }
        """,
        {"input": input_value},
    )
    return data["sceneCreate"]


def save_online_media(endpoint: str, scene_id: str, media: Any) -> dict[str, Any] | None:
    if not isinstance(media, dict):
        return None

    streams: list[dict[str, Any]] = []
    for index, stream in enumerate(media.get("streams") or []):
        if not isinstance(stream, dict):
            continue
        url = compact(stream.get("url"))
        kind = compact(stream.get("kind"))
        if not url or not kind:
            continue
        streams.append(
            {
                "label": compact(stream.get("label")),
                "kind": kind,
                "url": url,
                "position": int(stream.get("position", index)),
                "is_primary": bool(stream.get("is_primary", index == 0)),
            }
        )

    input_value: dict[str, Any] = {
        "scene_id": scene_id,
        "source_name": compact(media.get("source_name")),
        "source_slug": compact(media.get("source_slug")),
        "external_id": compact(media.get("external_id")),
        "embed_url": compact(media.get("embed_url")),
        "direct_video_url": compact(media.get("direct_video_url")),
        "thumbnail_url": compact(media.get("thumbnail_url")),
        "duration_seconds": media.get("duration_seconds"),
        "external_view_count": media.get("external_view_count"),
        "raw_metadata_json": compact(media.get("raw_metadata_json")),
        "streams": streams,
    }
    input_value = {key: value for key, value in input_value.items() if value not in (None, "", [], {})}

    if not input_value.get("source_name"):
        input_value["source_name"] = "Unknown"
    if not input_value.get("source_slug"):
        input_value["source_slug"] = "unknown"

    if not input_value.get("embed_url") and not input_value.get("direct_video_url") and not streams:
        return None

    data = gql(
        endpoint,
        """
        mutation SaveOnlineMedia($input: SceneOnlineMediaInput!) {
          sceneOnlineMediaSave(input: $input) {
            id scene_id direct_video_url embed_url duration_seconds
            streams { id kind url position is_primary }
          }
        }
        """,
        {"input": input_value},
    )
    return data.get("sceneOnlineMediaSave")


def scraper_config(name: str | None, url: str) -> dict[str, str]:
    key = (name or "").strip().casefold()
    if not key:
        host = urlparse(url).netloc.casefold()
        if "nafakarab.com" in host:
            key = "nafak"
        elif "shrmha.com" in host:
            key = "shrmha"

    if key not in SCRAPERS:
        raise RuntimeError(f"unsupported scraper {name!r}; choose one of: {', '.join(sorted(SCRAPERS))}")
    return SCRAPERS[key]


def script_path(relative_path: str) -> Path:
    path = SCRAPER_ROOT / relative_path
    if not path.exists():
        raise RuntimeError(f"missing scraper script: {path}")
    return path


def source_preview_candidates(config: dict[str, str], url: str, max_pages: int, limit: int | None) -> list[dict[str, Any]]:
    source_script = script_path(config["source_script"])
    command = [
        sys.executable,
        str(source_script),
        "source-by-url",
        "--url",
        url,
        "--max-pages",
        str(max_pages),
        "--preview-only",
    ]
    if limit is not None:
        command.extend(["--limit", str(limit)])

    data = run_json(command, source_script.parent)
    candidates = data.get("scene_candidates") or []
    return [candidate for candidate in candidates if isinstance(candidate, dict)]


def scrape_scene(config: dict[str, str], url: str) -> dict[str, Any]:
    scene_script = script_path(config["scene_script"])
    return run_json([sys.executable, str(scene_script), "scene-by-url", "--url", url], scene_script.parent)


def stream_count(scene: dict[str, Any]) -> int:
    media = scene.get("online_media")
    if not isinstance(media, dict):
        return 0
    streams = media.get("streams")
    return len(streams) if isinstance(streams, list) else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--scraper", choices=sorted(SCRAPERS), help="Defaults from URL host when omitted")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start-at", type=int, default=1, help="1-based candidate index for resume")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--skip-studio", action="store_true")
    parser.add_argument("--skip-tags", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = scraper_config(args.scraper, args.url)
    start_at = max(1, args.start_at)

    log(f"Scraper: {config['display']}")
    log("Collecting candidate URLs in preview mode...")
    candidates = source_preview_candidates(config, args.url, args.max_pages, args.limit)
    candidates = candidates[start_at - 1 :]

    total = len(candidates)
    log(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    log(f"Candidates to process: {total}")

    studio_cache: dict[str, str] = {}
    tag_cache: dict[str, str] = {}
    processed_urls: set[str] = set()
    stats = {"created": 0, "existing": 0, "duplicates_in_run": 0, "errors": 0, "online_media_saved": 0, "dry_run": 0}

    for index, preview in enumerate(candidates, 1):
        source_index = start_at + index - 1
        prefix = f"[{index}/{total} source#{source_index}]"
        url = first_url(preview)
        urls = candidate_urls(preview)

        if not url:
            stats["errors"] += 1
            log(f"{prefix} SKIP missing URL")
            continue

        duplicate_url = next((candidate_url for candidate_url in urls if candidate_url in processed_urls), None)
        if duplicate_url:
            stats["duplicates_in_run"] += 1
            log(f"{prefix} SKIP duplicate in this run url={duplicate_url}")
            continue
        processed_urls.update(urls)

        try:
            log(f"{prefix} CHECK {url}")

            existing = find_scene_by_any_url(args.endpoint, urls)
            if existing:
                stats["existing"] += 1
                log(f"{prefix} EXISTS scene={existing['id']} title={existing.get('title')!r}")
                continue

            log(f"{prefix} SCRAPE {url}")
            scene = scrape_scene(config, url)

            for key in ("urls", "title", "image", "date", "tags", "studio"):
                if not scene.get(key) and preview.get(key):
                    scene[key] = preview[key]

            scene_urls = candidate_urls(scene) or urls

            # Critical second check after hydration, because scene-by-url may add/normalise URLs.
            existing = find_scene_by_any_url(args.endpoint, scene_urls)
            if existing:
                stats["existing"] += 1
                log(f"{prefix} EXISTS_AFTER_SCRAPE scene={existing['id']} title={existing.get('title')!r}")
                continue

            log(f"{prefix} SCRAPED title={compact(scene.get('title'))!r} streams={stream_count(scene)}")

            if not args.apply:
                stats["dry_run"] += 1
                log(f"{prefix} DRY would create scene")
                continue

            studio_id = None if args.skip_studio else find_or_create_studio(args.endpoint, scene.get("studio"), studio_cache)
            native_tag_ids = [] if args.skip_tags else resolve_tag_ids(args.endpoint, scene, tag_cache)

            created = create_scene(args.endpoint, scene, studio_id, native_tag_ids)
            stats["created"] += 1
            log(f"{prefix} CREATED scene={created['id']} title={created.get('title')!r}")

            saved = save_online_media(args.endpoint, created["id"], scene.get("online_media"))
            if saved:
                stats["online_media_saved"] += 1
                log(f"{prefix} ONLINE_MEDIA scene={created['id']} streams={len(saved.get('streams') or [])}")
            else:
                log(f"{prefix} ONLINE_MEDIA skipped")

        except Exception as exc:
            stats["errors"] += 1
            log(f"{prefix} ERROR {url}: {exc}")

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
