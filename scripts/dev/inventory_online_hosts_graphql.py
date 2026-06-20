#!/usr/bin/env python3
import ipaddress
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

GRAPHQL_URL = "http://127.0.0.1:9999/graphql"
PAGE_SIZE = 250
OUT_PATH = Path("scripts/dev/reports/online_hosts_inventory_from_graphql.json")

QUERY = """
query FindScenes($page: Int!, $perPage: Int!) {
  findScenes(filter: { page: $page, per_page: $perPage }) {
    count
    scenes {
      id
      title
      details
      date
      urls
      studio {
        id
        name
      }
      tags {
        id
        name
      }
      online_media {
        source_name
        source_slug
        external_id
        embed_url
        direct_video_url
        thumbnail_url
        duration_seconds
        external_view_count
        raw_metadata_json
        streams {
          kind
          label
          url
          position
          is_primary
        }
      }
    }
  }
}
"""

REDACTED = "[REDACTED_LOCAL_OR_DEVICE_INFO]"

# Only redact local/device info. Public URLs, titles, details, tags, and public hosts stay visible.
LOCAL_PATH_VALUE_PATTERNS = [
    re.compile(r"^[A-Za-z]:[\\/].+"),       # C:\Users\...
    re.compile(r"^/[A-Za-z]/Users/.+"),     # /d/Users/...
    re.compile(r"^/mnt/.+"),
    re.compile(r"^/home/.+"),
    re.compile(r"^/Users/.+"),
    re.compile(r"^\\\\[^\\/]+[\\/].+"),     # UNC paths
]

# Important: this must NOT match https://.
PATH_INSIDE_TEXT_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9+.-])[A-Za-z]:[\\/][^\s\"']+"),
    re.compile(r"/[A-Za-z]/Users/[^\s\"']+"),
    re.compile(r"/mnt/[^\s\"']+"),
    re.compile(r"/home/[^\s\"']+"),
    re.compile(r"/Users/[^\s\"']+"),
]

redaction_count = Counter()

def gql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False, indent=2))

    return data["data"]

def normalize_host(raw_host: str | None) -> str | None:
    if not raw_host:
        return None
    h = raw_host.lower().strip()
    if h.startswith("www."):
        h = h[4:]
    return h or None

def is_private_or_local_host(raw_host: str | None) -> bool:
    h = normalize_host(raw_host)
    if not h:
        return False

    if h in {"localhost", "local", "stash.local"}:
        return True

    try:
        ip = ipaddress.ip_address(h.strip("[]"))
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False

def looks_like_local_path(value: str) -> bool:
    v = value.strip()
    return any(pattern.match(v) for pattern in LOCAL_PATH_VALUE_PATTERNS)

def sanitize_string(value: str) -> str:
    if not value:
        return value

    v = value.strip()

    if looks_like_local_path(v):
        redaction_count["local_path_value"] += 1
        return REDACTED

    parsed = urllib.parse.urlsplit(v)
    if parsed.scheme:
        scheme = parsed.scheme.lower()
        if scheme == "file":
            redaction_count["file_url"] += 1
            return REDACTED
        if is_private_or_local_host(parsed.netloc):
            redaction_count["private_or_local_url"] += 1
            return REDACTED

    sanitized = value
    for pattern in PATH_INSIDE_TEXT_PATTERNS:
        sanitized, n = pattern.subn(REDACTED, sanitized)
        if n:
            redaction_count["path_inside_text"] += n

    return sanitized

def sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_string(value)
    if isinstance(value, list):
        return [sanitize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): sanitize_value(v) for k, v in value.items()}
    return value

def sanitize_raw_metadata(raw: str | None) -> Any:
    if not raw:
        return None

    try:
        parsed = json.loads(raw)
        return sanitize_value(parsed)
    except Exception:
        return sanitize_string(raw)

def host(url: str | None) -> str | None:
    if not url:
        return None
    if url == REDACTED:
        return None

    try:
        parsed = urllib.parse.urlsplit(url)
        h = normalize_host(parsed.netloc)
        if not h:
            return None
        if is_private_or_local_host(h):
            return None
        return h
    except Exception:
        return None

def count_url(
    *,
    url: str | None,
    source: str,
    field: str,
    all_hosts: Counter,
    field_hosts: defaultdict,
    source_hosts: defaultdict,
    urls_by_host: defaultdict,
    urls_by_source: defaultdict,
):
    safe_url = sanitize_value(url)
    h = host(safe_url)
    if not h:
        return

    all_hosts[h] += 1
    field_hosts[field][h] += 1
    source_hosts[source][h] += 1
    urls_by_host[h][safe_url] += 1
    urls_by_source[source][safe_url] += 1

def main() -> None:
    all_hosts = Counter()
    field_hosts = defaultdict(Counter)
    source_hosts = defaultdict(Counter)
    stream_kind_hosts = defaultdict(Counter)
    scene_count_by_source = Counter()
    urls_by_host = defaultdict(Counter)
    urls_by_source = defaultdict(Counter)
    stream_kind_counts = Counter()
    stream_label_counts = Counter()

    missing = {
        "embed_url": Counter(),
        "direct_video_url": Counter(),
        "thumbnail_url": Counter(),
        "duration_seconds": Counter(),
        "streams": Counter(),
    }

    scene_records = []
    scenes_total = 0
    scenes_with_online = 0
    scenes_with_direct = 0
    scenes_with_embed = 0
    scenes_with_thumbnail = 0
    scenes_with_duration = 0

    page = 1
    while True:
        data = gql(QUERY, {"page": page, "perPage": PAGE_SIZE})
        result = data["findScenes"]
        scenes = result["scenes"]
        scenes_total = result["count"]

        if not scenes:
            break

        for scene in scenes:
            media = scene.get("online_media")

            record = {
                "id": str(scene.get("id")),
                "title": sanitize_value(scene.get("title")),
                "details": sanitize_value(scene.get("details")),
                "date": scene.get("date"),
                "studio": sanitize_value(scene.get("studio")),
                "tags": sanitize_value(scene.get("tags") or []),
                "urls": sanitize_value(scene.get("urls") or []),
                "online_media": None,
            }

            if not media:
                scene_records.append(record)
                continue

            scenes_with_online += 1
            source = media.get("source_slug") or media.get("source_name") or "unknown"
            scene_count_by_source[source] += 1

            streams = media.get("streams") or []

            safe_media = {
                "source_name": sanitize_value(media.get("source_name")),
                "source_slug": sanitize_value(media.get("source_slug")),
                "external_id": sanitize_value(media.get("external_id")),
                "embed_url": sanitize_value(media.get("embed_url")),
                "direct_video_url": sanitize_value(media.get("direct_video_url")),
                "thumbnail_url": sanitize_value(media.get("thumbnail_url")),
                "duration_seconds": media.get("duration_seconds"),
                "external_view_count": media.get("external_view_count"),
                "raw_metadata": sanitize_raw_metadata(media.get("raw_metadata_json")),
                "streams": sanitize_value(streams),
            }
            record["online_media"] = safe_media
            scene_records.append(record)

            if media.get("direct_video_url"):
                scenes_with_direct += 1
            else:
                missing["direct_video_url"][source] += 1

            if media.get("embed_url"):
                scenes_with_embed += 1
            else:
                missing["embed_url"][source] += 1

            if media.get("thumbnail_url"):
                scenes_with_thumbnail += 1
            else:
                missing["thumbnail_url"][source] += 1

            if media.get("duration_seconds") is not None:
                scenes_with_duration += 1
            else:
                missing["duration_seconds"][source] += 1

            if not streams:
                missing["streams"][source] += 1

            for u in scene.get("urls") or []:
                count_url(
                    url=u,
                    source=source,
                    field="scene.urls",
                    all_hosts=all_hosts,
                    field_hosts=field_hosts,
                    source_hosts=source_hosts,
                    urls_by_host=urls_by_host,
                    urls_by_source=urls_by_source,
                )

            count_url(
                url=media.get("embed_url"),
                source=source,
                field="online_media.embed_url",
                all_hosts=all_hosts,
                field_hosts=field_hosts,
                source_hosts=source_hosts,
                urls_by_host=urls_by_host,
                urls_by_source=urls_by_source,
            )
            count_url(
                url=media.get("direct_video_url"),
                source=source,
                field="online_media.direct_video_url",
                all_hosts=all_hosts,
                field_hosts=field_hosts,
                source_hosts=source_hosts,
                urls_by_host=urls_by_host,
                urls_by_source=urls_by_source,
            )
            count_url(
                url=media.get("thumbnail_url"),
                source=source,
                field="online_media.thumbnail_url",
                all_hosts=all_hosts,
                field_hosts=field_hosts,
                source_hosts=source_hosts,
                urls_by_host=urls_by_host,
                urls_by_source=urls_by_source,
            )

            for stream in streams:
                u = sanitize_value(stream.get("url"))
                h = host(u)
                kind = stream.get("kind") or "unknown"
                label = stream.get("label") or ""

                stream_kind_counts[kind] += 1
                if label:
                    stream_label_counts[label] += 1

                if not h:
                    continue

                all_hosts[h] += 1
                field_hosts["online_media.streams.url"][h] += 1
                stream_kind_hosts[kind][h] += 1
                source_hosts[source][h] += 1
                urls_by_host[h][u] += 1
                urls_by_source[source][u] += 1

        if page * PAGE_SIZE >= scenes_total:
            break
        page += 1

    report = {
        "report_scope": {
            "contains_titles": True,
            "contains_details": True,
            "contains_full_public_urls": True,
            "contains_file_paths": False,
            "local_or_device_info_redacted": True,
            "source": "Stash GraphQL findScenes: native scene metadata + online_media",
            "graphql_url": REDACTED,
        },
        "redactions": dict(redaction_count),
        "summary": {
            "scenes_total": scenes_total,
            "scenes_with_online_media": scenes_with_online,
            "distinct_hosts": len(all_hosts),
            "scenes_with_direct_video_url": scenes_with_direct,
            "scenes_with_embed_url": scenes_with_embed,
            "scenes_with_thumbnail_url": scenes_with_thumbnail,
            "scenes_with_duration_seconds": scenes_with_duration,
        },
        "online_scene_count_by_source": scene_count_by_source.most_common(),
        "hosts_overall": all_hosts.most_common(),
        "hosts_by_field": {
            field: counter.most_common()
            for field, counter in sorted(field_hosts.items())
        },
        "hosts_by_source": {
            source: counter.most_common()
            for source, counter in sorted(source_hosts.items())
        },
        "hosts_by_stream_kind": {
            kind: counter.most_common()
            for kind, counter in sorted(stream_kind_hosts.items())
        },
        "stream_kind_counts": stream_kind_counts.most_common(),
        "stream_label_counts": stream_label_counts.most_common(250),
        "missing_online_media_fields_by_source": {
            field: counter.most_common()
            for field, counter in sorted(missing.items())
        },
        "top_urls_by_host": {
            h: counter.most_common(250)
            for h, counter in sorted(urls_by_host.items())
        },
        "top_urls_by_source": {
            source: counter.most_common(500)
            for source, counter in sorted(urls_by_source.items())
        },
        "scenes": scene_records,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_PATH}")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print("Redactions:", dict(redaction_count))
    print("\nTop hosts:")
    for h, c in all_hosts.most_common(40):
        print(f"{c:5d}  {h}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
