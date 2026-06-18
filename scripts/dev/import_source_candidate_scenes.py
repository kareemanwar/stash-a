#!/usr/bin/env python3
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

ROOT = Path(__file__).resolve().parents[2]
SCRAPER_ROOT = ROOT / ".local" / "scrapers" / "stash-a"
ENDPOINT = "http://localhost:9999/graphql"
SCRAPERS = {
    "shrmha": {"name": "Shrmha", "source": "Shrmha/ShrmhaSource.py", "scene": "Shrmha/ShrmhaOnline.py"},
    "nafak": {"name": "Nafak", "source": "Nafak/NafakSourceHydrated.py", "scene": "Nafak/NafakOnline.py"},
}


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
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def item_urls(item: dict[str, Any]) -> list[str]:
    ret = strings(item.get("urls"))
    media = item.get("online_media")
    if isinstance(media, dict):
        ret += strings(media.get("embed_url")) + strings(media.get("direct_video_url"))
    return uniq(ret)


def run_json(cmd: list[str], cwd: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run(cmd, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or f"command failed: {p.returncode}")
    data = json.loads(p.stdout)
    if not isinstance(data, dict):
        raise RuntimeError("scraper returned non-object JSON")
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data


def gql(endpoint: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables or {}}, ensure_ascii=False).encode()
    req = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            data = json.loads(res.read().decode())
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GraphQL request failed: {exc}") from exc
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False, indent=2))
    return data.get("data") or {}


def find_scene(endpoint: str, url: str) -> dict[str, Any] | None:
    data = gql(endpoint, """
      query($url: String!) {
        findScenes(scene_filter: { url: { value: $url, modifier: EQUALS } }, filter: { per_page: 20 }) {
          scenes { id title urls }
        }
      }
    """, {"url": url})
    for scene in data.get("findScenes", {}).get("scenes", []):
        if url in strings(scene.get("urls")):
            return scene
    return None


def find_any_scene(endpoint: str, urls: list[str]) -> dict[str, Any] | None:
    for url in uniq(urls):
        found = find_scene(endpoint, url)
        if found:
            return found
    return None


def find_or_create_studio(endpoint: str, studio: Any, cache: dict[str, str]) -> str | None:
    if not isinstance(studio, dict):
        return None
    name = clean(studio.get("name"))
    if not name:
        return None
    key = name.casefold()
    if key in cache:
        return cache[key]
    data = gql(endpoint, "query($q:String!){findStudios(filter:{q:$q,per_page:50}){studios{id name}}}", {"q": name})
    for studio_row in data.get("findStudios", {}).get("studios", []):
        if clean(studio_row.get("name")) == name:
            cache[key] = studio_row["id"]
            return studio_row["id"]
    new_input: dict[str, Any] = {"name": name}
    if strings(studio.get("urls")):
        new_input["urls"] = strings(studio.get("urls"))
    created = gql(endpoint, "mutation($input:StudioCreateInput!){studioCreate(input:$input){id name}}", {"input": new_input})["studioCreate"]
    cache[key] = created["id"]
    log(f"    STUDIO created id={created['id']} name={created['name']!r}")
    return created["id"]


def tag_name(tag: Any) -> str | None:
    return clean(tag.get("name")) if isinstance(tag, dict) else clean(tag)


def find_or_create_tag(endpoint: str, name: str, cache: dict[str, str]) -> str:
    key = name.casefold()
    if key in cache:
        return cache[key]
    data = gql(endpoint, "query($q:String!){findTags(filter:{q:$q,per_page:50}){tags{id name}}}", {"q": name})
    for tag in data.get("findTags", {}).get("tags", []):
        if clean(tag.get("name")) == name:
            cache[key] = tag["id"]
            return tag["id"]
    created = gql(endpoint, "mutation($input:TagCreateInput!){tagCreate(input:$input){id name}}", {"input": {"name": name}})["tagCreate"]
    cache[key] = created["id"]
    log(f"    TAG created id={created['id']} name={created['name']!r}")
    return created["id"]


def resolve_tag_ids(endpoint: str, scene: dict[str, Any], cache: dict[str, str]) -> list[str]:
    ret: list[str] = []
    seen: set[str] = set()
    for tag in scene.get("tags") or []:
        name = tag_name(tag)
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            ret.append(find_or_create_tag(endpoint, name, cache))
    return ret


def create_scene(endpoint: str, scene: dict[str, Any], studio_id: str | None, tag_ids: list[str]) -> dict[str, Any]:
    media = scene.get("online_media") if isinstance(scene.get("online_media"), dict) else {}
    inp: dict[str, Any] = {
        "title": clean(scene.get("title")),
        "details": clean(scene.get("details")),
        "urls": uniq(strings(scene.get("urls"))),
        "date": clean(scene.get("date")),
        "organized": False,
    }
    image = clean(scene.get("image")) or clean(media.get("thumbnail_url"))
    if image:
        inp["cover_image"] = image
    if studio_id:
        inp["studio_id"] = studio_id
    if tag_ids:
        inp["tag_ids"] = tag_ids
    inp = {k: v for k, v in inp.items() if v not in (None, "", [], {})}
    return gql(endpoint, "mutation($input:SceneCreateInput!){sceneCreate(input:$input){id title urls}}", {"input": inp})["sceneCreate"]


def save_online_media(endpoint: str, scene_id: str, media: Any) -> dict[str, Any] | None:
    if not isinstance(media, dict):
        return None
    streams: list[dict[str, Any]] = []
    for index, stream in enumerate(media.get("streams") or []):
        if not isinstance(stream, dict):
            continue
        url, kind = clean(stream.get("url")), clean(stream.get("kind"))
        if url and kind:
            streams.append({"label": clean(stream.get("label")), "kind": kind, "url": url, "position": int(stream.get("position", index)), "is_primary": bool(stream.get("is_primary", index == 0))})
    inp: dict[str, Any] = {
        "scene_id": scene_id,
        "source_name": clean(media.get("source_name")) or "Unknown",
        "source_slug": clean(media.get("source_slug")) or "unknown",
        "external_id": clean(media.get("external_id")),
        "embed_url": clean(media.get("embed_url")),
        "direct_video_url": clean(media.get("direct_video_url")),
        "thumbnail_url": clean(media.get("thumbnail_url")),
        "duration_seconds": media.get("duration_seconds"),
        "external_view_count": media.get("external_view_count"),
        "raw_metadata_json": clean(media.get("raw_metadata_json")),
        "streams": streams,
    }
    inp = {k: v for k, v in inp.items() if v not in (None, "", [], {})}
    if not inp.get("embed_url") and not inp.get("direct_video_url") and not streams:
        return None
    return gql(endpoint, "mutation($input:SceneOnlineMediaInput!){sceneOnlineMediaSave(input:$input){id scene_id streams{id kind url}}}", {"input": inp}).get("sceneOnlineMediaSave")


def scraper_script(conf: dict[str, str], key: str) -> Path:
    path = SCRAPER_ROOT / conf[key]
    if not path.exists():
        raise RuntimeError(f"missing scraper script: {path}")
    return path


def preview_candidates(conf: dict[str, str], url: str, max_pages: int, limit: int | None) -> list[dict[str, Any]]:
    path = scraper_script(conf, "source")
    cmd = [sys.executable, str(path), "source-by-url", "--url", url, "--max-pages", str(max_pages), "--preview-only"]
    if limit is not None:
        cmd += ["--limit", str(limit)]
    data = run_json(cmd, path.parent)
    return [x for x in data.get("scene_candidates") or [] if isinstance(x, dict)]


def scrape_scene(conf: dict[str, str], url: str) -> dict[str, Any]:
    path = scraper_script(conf, "scene")
    return run_json([sys.executable, str(path), "scene-by-url", "--url", url], path.parent)


def stream_count(scene: dict[str, Any]) -> int:
    media = scene.get("online_media")
    return len(media.get("streams") or []) if isinstance(media, dict) else 0


def prefilter_candidates(endpoint: str, candidates: list[dict[str, Any]], start_at: int, stats: dict[str, int]) -> list[tuple[int, dict[str, Any]]]:
    filtered: list[tuple[int, dict[str, Any]]] = []
    processed_urls: set[str] = set()

    log("Filtering candidates against existing native Scene.urls before scene scraping...")
    for index, preview in enumerate(candidates, start_at):
        prefix = f"[source#{index}]"
        urls = item_urls(preview)
        url = urls[0] if urls else None

        if not url:
            stats["missing_url"] += 1
            log(f"{prefix} SKIP missing URL")
            continue

        if any(u in processed_urls for u in urls):
            stats["duplicates_in_source"] += 1
            log(f"{prefix} SKIP duplicate in source result {url}")
            continue
        processed_urls.update(urls)

        existing = find_any_scene(endpoint, urls)
        if existing:
            stats["existing_prefiltered"] += 1
            log(f"{prefix} EXISTS_PREFILTER scene={existing['id']} title={existing.get('title')!r}")
            continue

        filtered.append((index, preview))

    log(
        "Prefilter summary: "
        f"new={len(filtered)} existing={stats['existing_prefiltered']} "
        f"duplicates={stats['duplicates_in_source']} missing_url={stats['missing_url']}"
    )
    return filtered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--scraper", required=True, choices=sorted(SCRAPERS))
    parser.add_argument("--endpoint", default=ENDPOINT)
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start-at", type=int, default=1)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--skip-studio", action="store_true")
    parser.add_argument("--skip-tags", action="store_true")
    args = parser.parse_args()

    conf = SCRAPERS[args.scraper]
    start_at = max(1, args.start_at)
    log(f"Scraper: {conf['name']}")
    log("Collecting candidate URLs in preview mode...")
    candidates = preview_candidates(conf, args.url, args.max_pages, args.limit)[start_at - 1:]
    log(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    log(f"Source candidates collected: {len(candidates)}")

    studio_cache: dict[str, str] = {}
    tag_cache: dict[str, str] = {}
    stats = {
        "created": 0,
        "existing_prefiltered": 0,
        "existing_after_scrape": 0,
        "duplicates_in_source": 0,
        "missing_url": 0,
        "errors": 0,
        "online_media_saved": 0,
        "dry_run": 0,
    }

    candidates_to_scrape = prefilter_candidates(args.endpoint, candidates, start_at, stats)
    log(f"Candidates to scene-scrape: {len(candidates_to_scrape)}")

    for index, (source_index, preview) in enumerate(candidates_to_scrape, 1):
        prefix = f"[{index}/{len(candidates_to_scrape)} source#{source_index}]"
        urls = item_urls(preview)
        url = urls[0]

        try:
            log(f"{prefix} SCRAPE {url}")
            scene = scrape_scene(conf, url)
            for key in ("urls", "title", "image", "date", "tags", "studio"):
                if not scene.get(key) and preview.get(key):
                    scene[key] = preview[key]
            existing = find_any_scene(args.endpoint, item_urls(scene) or urls)
            if existing:
                stats["existing_after_scrape"] += 1
                log(f"{prefix} EXISTS_AFTER_SCRAPE scene={existing['id']} title={existing.get('title')!r}")
                continue
            log(f"{prefix} SCRAPED title={clean(scene.get('title'))!r} streams={stream_count(scene)}")
            if not args.apply:
                stats["dry_run"] += 1
                log(f"{prefix} DRY would create scene")
                continue
            studio_id = None if args.skip_studio else find_or_create_studio(args.endpoint, scene.get("studio"), studio_cache)
            tag_ids = [] if args.skip_tags else resolve_tag_ids(args.endpoint, scene, tag_cache)
            created = create_scene(args.endpoint, scene, studio_id, tag_ids)
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
