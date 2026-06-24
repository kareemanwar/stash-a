#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRAPER_ROOT = ROOT / ".local" / "scrapers" / "stash-a"
ARABGY_SCENE_SCRAPER = SCRAPER_ROOT / "Arabgy" / "ArabgyOnline.py"
ENDPOINT = "http://localhost:9999/graphql"
ARABGY_HOST = "arabgy.com"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def clean(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split()).strip()
    return value or None


def strings(value: Any) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def uniq(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def is_arabgy_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    return host == ARABGY_HOST


def first_arabgy_url(scene: dict[str, Any]) -> str | None:
    for url in strings(scene.get("urls")):
        if is_arabgy_url(url):
            return url
    return None


def gql(endpoint: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables or {}}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            data = json.loads(res.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GraphQL request failed: {exc}") from exc
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False, indent=2))
    return data.get("data") or {}


def find_scene_by_id(endpoint: str, scene_id: str) -> dict[str, Any] | None:
    data = gql(
        endpoint,
        """
        query($id: ID!) {
          findScene(id: $id) { id title urls }
        }
        """,
        {"id": scene_id},
    )
    scene = data.get("findScene")
    return scene if isinstance(scene, dict) else None


def find_scene_by_url(endpoint: str, url: str) -> dict[str, Any] | None:
    data = gql(
        endpoint,
        """
        query($url: String!) {
          findScenes(scene_filter: { url: { value: $url, modifier: EQUALS } }, filter: { per_page: 20 }) {
            scenes { id title urls }
          }
        }
        """,
        {"url": url},
    )
    for scene in data.get("findScenes", {}).get("scenes", []):
        if isinstance(scene, dict) and url in strings(scene.get("urls")):
            return scene
    return None


def iter_all_arabgy_scenes(endpoint: str, *, per_page: int = 200, max_scenes: int | None = None) -> list[dict[str, Any]]:
    page = 1
    scenes: list[dict[str, Any]] = []
    while True:
        data = gql(
            endpoint,
            """
            query($page: Int!, $per_page: Int!) {
              findScenes(filter: { page: $page, per_page: $per_page }) {
                count
                scenes { id title urls }
              }
            }
            """,
            {"page": page, "per_page": per_page},
        )
        result = data.get("findScenes") or {}
        batch = result.get("scenes") or []
        if not batch:
            break

        for scene in batch:
            if not isinstance(scene, dict):
                continue
            if first_arabgy_url(scene):
                scenes.append(scene)
                if max_scenes is not None and len(scenes) >= max_scenes:
                    return scenes

        count = result.get("count")
        if isinstance(count, int) and page * per_page >= count:
            break
        page += 1
    return scenes


def run_json(cmd: list[str], cwd: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"command failed: {proc.returncode}")
    stdout = proc.stdout.strip()
    if not stdout:
        raise RuntimeError("scraper returned empty stdout")
    data = json.loads(stdout)
    if not isinstance(data, dict):
        raise RuntimeError("scraper returned non-object JSON")
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data


def scrape_scene(url: str) -> dict[str, Any]:
    if not ARABGY_SCENE_SCRAPER.exists():
        raise RuntimeError(f"missing Arabgy scene scraper: {ARABGY_SCENE_SCRAPER}")
    return run_json([sys.executable, str(ARABGY_SCENE_SCRAPER), "scene-by-url", "--url", url], ARABGY_SCENE_SCRAPER.parent)


def media_input(scene_id: str, media: Any) -> dict[str, Any] | None:
    if not isinstance(media, dict):
        return None

    streams: list[dict[str, Any]] = []
    for index, stream in enumerate(media.get("streams") or []):
        if not isinstance(stream, dict):
            continue
        url = clean(stream.get("url"))
        kind = clean(stream.get("kind"))
        if not url or not kind:
            continue
        streams.append(
            {
                "label": clean(stream.get("label")),
                "kind": kind,
                "url": url,
                "position": int(stream.get("position", index)),
                "is_primary": bool(stream.get("is_primary", index == 0)),
            }
        )

    inp: dict[str, Any] = {
        "scene_id": scene_id,
        "source_name": clean(media.get("source_name")) or "Arabgy",
        "source_slug": clean(media.get("source_slug")) or "arabgy",
        "external_id": clean(media.get("external_id")),
        "embed_url": clean(media.get("embed_url")),
        "direct_video_url": clean(media.get("direct_video_url")),
        "thumbnail_url": clean(media.get("thumbnail_url")),
        "duration_seconds": media.get("duration_seconds"),
        "external_view_count": media.get("external_view_count"),
        "raw_metadata_json": clean(media.get("raw_metadata_json")),
        "streams": streams,
    }
    inp = {key: value for key, value in inp.items() if value not in (None, "", [], {})}
    if not inp.get("embed_url") and not inp.get("direct_video_url") and not streams:
        return None
    return inp


def save_online_media(endpoint: str, inp: dict[str, Any]) -> dict[str, Any] | None:
    return gql(
        endpoint,
        """
        mutation($input: SceneOnlineMediaInput!) {
          sceneOnlineMediaSave(input: $input) {
            id
            scene_id
            embed_url
            direct_video_url
            thumbnail_url
            streams { id kind label url position is_primary }
          }
        }
        """,
        {"input": inp},
    ).get("sceneOnlineMediaSave")


def collect_target_scenes(args: argparse.Namespace) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for scene_id in args.scene_id or []:
        scene = find_scene_by_id(args.endpoint, str(scene_id))
        if not scene:
            raise RuntimeError(f"scene not found: {scene_id}")
        if scene["id"] not in seen_ids:
            seen_ids.add(scene["id"])
            scenes.append(scene)

    for url in args.url or []:
        scene = find_scene_by_url(args.endpoint, url)
        if not scene:
            raise RuntimeError(f"scene not found for URL: {url}")
        if scene["id"] not in seen_ids:
            seen_ids.add(scene["id"])
            scenes.append(scene)

    if args.all:
        for scene in iter_all_arabgy_scenes(args.endpoint, max_scenes=args.max_scenes):
            if scene["id"] not in seen_ids:
                seen_ids.add(scene["id"])
                scenes.append(scene)

    return scenes


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair SceneOnlineMedia for existing Arabgy scenes.")
    parser.add_argument("--endpoint", default=ENDPOINT)
    parser.add_argument("--scene-id", action="append", help="Existing scene id to repair. Can be repeated.")
    parser.add_argument("--url", action="append", help="Existing Arabgy scene URL to repair. Can be repeated.")
    parser.add_argument("--all", action="store_true", help="Repair all scenes with an arabgy.com URL.")
    parser.add_argument("--max-scenes", type=int, help="Limit --all repairs after this many Arabgy scenes.")
    parser.add_argument("--apply", action="store_true", help="Save SceneOnlineMedia. Default is dry-run.")
    args = parser.parse_args()

    if not args.scene_id and not args.url and not args.all:
        parser.error("provide --scene-id, --url, or --all")

    targets = collect_target_scenes(args)
    stats = {"targets": len(targets), "saved": 0, "dry_run": 0, "skipped": 0, "errors": 0}
    results: list[dict[str, Any]] = []

    log(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    log(f"Target Arabgy scenes: {len(targets)}")

    for index, scene in enumerate(targets, 1):
        scene_id = str(scene.get("id"))
        title = clean(scene.get("title"))
        url = first_arabgy_url(scene)
        prefix = f"[{index}/{len(targets)} scene={scene_id}]"

        if not url:
            stats["skipped"] += 1
            log(f"{prefix} SKIP no Arabgy URL title={title!r}")
            results.append({"scene_id": scene_id, "status": "skipped", "reason": "no_arabgy_url", "title": title})
            continue

        try:
            log(f"{prefix} SCRAPE {url}")
            scraped = scrape_scene(url)
            inp = media_input(scene_id, scraped.get("online_media"))
            stream_count = len(inp.get("streams") or []) if inp else 0
            if not inp:
                stats["skipped"] += 1
                log(f"{prefix} SKIP no online media title={title!r}")
                results.append({"scene_id": scene_id, "status": "skipped", "reason": "no_online_media", "url": url, "title": title})
                continue

            if not args.apply:
                stats["dry_run"] += 1
                log(f"{prefix} DRY would save streams={stream_count} embed={bool(inp.get('embed_url'))} direct={bool(inp.get('direct_video_url'))}")
                results.append({"scene_id": scene_id, "status": "dry_run", "url": url, "title": title, "streams": stream_count, "embed_url": inp.get("embed_url"), "direct_video_url": inp.get("direct_video_url")})
                continue

            saved = save_online_media(args.endpoint, inp)
            saved_stream_count = len(saved.get("streams") or []) if isinstance(saved, dict) else 0
            stats["saved"] += 1
            log(f"{prefix} SAVED streams={saved_stream_count} title={title!r}")
            results.append({"scene_id": scene_id, "status": "saved", "url": url, "title": title, "streams": saved_stream_count, "online_media_id": saved.get("id") if isinstance(saved, dict) else None})
        except Exception as exc:
            stats["errors"] += 1
            log(f"{prefix} ERROR {url}: {exc}")
            results.append({"scene_id": scene_id, "status": "error", "url": url, "title": title, "error": str(exc)})

    print(json.dumps({"stats": stats, "results": results}, ensure_ascii=False, indent=2))
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
