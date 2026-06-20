from __future__ import annotations

import re
from urllib.parse import urlparse


def stream_quality_score(label: str | None, url: str | None = None) -> int:
    text = " ".join(part for part in [label or "", url or ""] if part)
    numbers = [int(match.group(1)) for match in re.finditer(r"(\d{3,4})p", text, re.IGNORECASE)]
    if numbers:
        return max(numbers)
    if ".m3u8" in text.lower():
        return 1000
    if ".mp4" in text.lower():
        return 500
    return 0


def make_stream(label: str | None, kind: str, url: str) -> dict[str, object]:
    return {
        "label": label or kind,
        "kind": kind,
        "url": url,
        "position": 0,
        "is_primary": False,
    }


def normalize_streams(streams: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    unique: list[dict[str, object]] = []

    for stream in streams:
        url = stream.get("url")
        kind = stream.get("kind")
        if not isinstance(url, str) or not url:
            continue
        if not isinstance(kind, str) or kind not in {"direct", "embed"}:
            continue
        if url in seen:
            continue
        seen.add(url)
        unique.append(dict(stream))

    def sort_key(stream: dict[str, object]) -> tuple[int, int]:
        kind = stream.get("kind")
        label = stream.get("label")
        url = stream.get("url")
        return (
            0 if kind == "direct" else 1,
            -stream_quality_score(label if isinstance(label, str) else None, url if isinstance(url, str) else None),
        )

    unique.sort(key=sort_key)

    for position, stream in enumerate(unique):
        stream["position"] = position
        stream["is_primary"] = position == 0

    return unique


def best_direct_url(streams: list[dict[str, object]]) -> str | None:
    for stream in streams:
        if stream.get("kind") == "direct" and isinstance(stream.get("url"), str):
            return str(stream["url"])
    return None


def best_embed_url(streams: list[dict[str, object]]) -> str | None:
    for stream in streams:
        if stream.get("kind") == "embed" and isinstance(stream.get("url"), str):
            return str(stream["url"])
    return None


def host_family(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None
