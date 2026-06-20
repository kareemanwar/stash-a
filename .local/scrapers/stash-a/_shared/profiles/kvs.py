from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from ..jsonld import extract_jsonld, first_object, first_string
from ..output import drop_empty, raw_metadata
from ..streams import best_direct_url, best_embed_url, make_stream, normalize_streams
from ..text import attr_value, clean_text, first_non_empty, strip_tags, unique_dicts_by_name
from ..urls import absolute_url, unique_strings

GENERIC_PERFORMER_LINK_NAMES = {"pornstars", "porn stars", "models", "pornstar"}


def meta_content(document: str, key: str) -> str | None:
    patterns = [
        rf'<meta\b[^>]*(?:property|name)=["\']{re.escape(key)}["\'][^>]*content=["\'](?P<value>[^"\']*)["\']',
        rf'<meta\b[^>]*content=["\'](?P<value>[^"\']*)["\'][^>]*(?:property|name)=["\']{re.escape(key)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, document, re.IGNORECASE | re.DOTALL)
        if match:
            value = html.unescape(match.group("value")).strip()
            if value:
                return value
    return None


def link_href(document: str, rel: str) -> str | None:
    for pattern in [
        rf'<link\b[^>]*rel=["\'][^"\']*\b{re.escape(rel)}\b[^"\']*["\'][^>]*href=["\'](?P<value>[^"\']+)["\']',
        rf'<link\b[^>]*href=["\'](?P<value>[^"\']+)["\'][^>]*rel=["\'][^"\']*\b{re.escape(rel)}\b[^"\']*["\']',
    ]:
        match = re.search(pattern, document, re.IGNORECASE | re.DOTALL)
        if match:
            value = html.unescape(match.group("value")).strip()
            if value:
                return value
    return None


def parse_iso8601_duration(value: str | None) -> int | None:
    if not value:
        return None
    match = re.match(
        r"^P(?:(?P<days>\d+)D)?T?"
        r"(?:(?P<hours>\d+)H)?"
        r"(?:(?P<minutes>\d+)M)?"
        r"(?:(?P<seconds>\d+)S)?$",
        value.strip(),
        re.IGNORECASE,
    )
    if not match:
        return None
    parts = {key: int(raw or 0) for key, raw in match.groupdict().items()}
    return parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]


def parse_duration_text(value: object) -> int | None:
    text = clean_text(value)
    if not text:
        return None

    if re.fullmatch(r"\d+", text):
        return int(text)

    colon = re.search(r"(?:(\d+):)?(\d{1,2}):(\d{2})", text)
    if colon:
        hours = int(colon.group(1) or 0)
        minutes = int(colon.group(2))
        seconds = int(colon.group(3))
        return hours * 3600 + minutes * 60 + seconds

    return parse_iso8601_duration(text)


def normalize_date(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)
    return text


def parse_view_count(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        digits = re.sub(r"[^0-9]", "", value)
        if digits:
            return int(digits)
    return None


def interaction_count(video_obj: dict[str, Any], interaction_name: str) -> int | None:
    stats = video_obj.get("interactionStatistic")
    if not isinstance(stats, list):
        return None
    for item in stats:
        if not isinstance(item, dict):
            continue
        interaction = str(item.get("interactionType") or "")
        if interaction_name.lower() not in interaction.lower():
            continue
        return parse_view_count(item.get("userInteractionCount"))
    return None


def extract_video_id(document: str, page_url: str, canonical_url: str | None = None) -> str | None:
    for pattern in [
        r"\bvideoId\s*:\s*['\"](?P<id>\d+)['\"]",
        r"\bdata-object_id\s*=\s*['\"](?P<id>\d+)['\"]",
        r"/embed/(?P<id>\d+)",
        r"/preview/(?P<id>\d+)\.mp4",
    ]:
        match = re.search(pattern, document, re.IGNORECASE)
        if match:
            return match.group("id")

    for candidate in [canonical_url, page_url]:
        if not candidate:
            continue
        slug_digits = re.search(r"/(\d{5,})(?:/|$)", candidate)
        if slug_digits:
            return slug_digits.group(1)

    return None


def strip_site_suffix(title: str) -> str:
    return re.sub(r"\s*\|\s*Free Porn\s*$", "", title, flags=re.IGNORECASE).strip()


def extract_meta_tags(document: str) -> list[str]:
    tags: list[str] = []
    for match in re.finditer(
        r'<meta\b[^>]*(?:property|name)=["\']video:tag["\'][^>]*content=["\'](?P<value>[^"\']+)["\']',
        document,
        re.IGNORECASE | re.DOTALL,
    ):
        tags.append(match.group("value"))
    for match in re.finditer(
        r'<meta\b[^>]*content=["\'](?P<value>[^"\']+)["\'][^>]*(?:property|name)=["\']video:tag["\']',
        document,
        re.IGNORECASE | re.DOTALL,
    ):
        tags.append(match.group("value"))
    return tags


def _path_has_slug(href: str, path_prefix: str) -> bool:
    path = urlparse(href).path.strip("/")
    prefix = path_prefix.strip("/")
    if path == prefix:
        return False
    return path.startswith(prefix + "/")


def _scene_path_key(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return None
    path = re.sub(r"^[a-z]{2}/", "", path, flags=re.IGNORECASE)
    return path.rstrip("/")


def _same_scene_url(left: str | None, right: str | None) -> bool:
    left_key = _scene_path_key(left)
    right_key = _scene_path_key(right)
    return bool(left_key and right_key and left_key == right_key)


def extract_link_names(
    document: str,
    path_prefix: str,
    class_hint: str | None = None,
    require_slug: bool = True,
) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in re.finditer(r"<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a>", document, re.IGNORECASE | re.DOTALL):
        attrs = match.group("attrs")
        href = attr_value(attrs, "href") or ""
        class_name = attr_value(attrs, "class") or ""
        if path_prefix not in href:
            continue
        if require_slug and not _path_has_slug(href, path_prefix):
            continue
        if class_hint and class_hint not in class_name:
            continue

        span_match = re.search(r"<span\b[^>]*>(?P<name>.*?)</span>", match.group("body"), re.IGNORECASE | re.DOTALL)
        name = strip_tags(span_match.group("name") if span_match else match.group("body"))
        if not name or name in seen:
            continue
        seen.add(name)
        values.append({"name": name, "urls": [href] if href.startswith("http") else []})
    return values


def clean_performers(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    performers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for performer in values:
        name = performer.get("name")
        if not isinstance(name, str):
            continue
        if name.strip().lower() in GENERIC_PERFORMER_LINK_NAMES:
            continue
        if name in seen:
            continue
        seen.add(name)
        performers.append(performer)
    return performers


def _before_first_listing_card(document: str) -> str:
    match = re.search(
        r'<div\b[^>]*class=["\'][^"\']*\bitem\b[^"\']*["\']',
        document,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return document
    return document[: match.start()]


def extract_id_block(document: str, element_id: str) -> str | None:
    start = re.search(
        rf'<div\b[^>]*id=["\']{re.escape(element_id)}["\'][^>]*>',
        document,
        re.IGNORECASE | re.DOTALL,
    )
    if not start:
        return None

    # KVS tab panels are sibling divs. Stop before the next tab panel when present.
    end = re.search(
        r'<div\b[^>]*id=["\']tab_[^"\']+["\'][^>]*>',
        document[start.end():],
        re.IGNORECASE | re.DOTALL,
    )
    if end:
        return document[start.start(): start.end() + end.start()]

    return document[start.start():]


def extract_scene_metadata_fallback(
    document: str,
    *,
    source_name: str,
    source_url: str,
    source_slug: str,
) -> dict[str, Any]:
    # Prefer the current scene info tab. It contains Channel/Network/Categories/Pornstars
    # for the active scene and appears before sidebar/related-video lists.
    tab_doc = extract_id_block(document, "tab_video_info")
    if tab_doc:
        metadata_doc = tab_doc
        metadata_source = "tab_video_info"
    else:
        # Last-resort fallback for other KVS pages: only parse before list cards.
        metadata_doc = _before_first_listing_card(document)
        metadata_source = "metadata_prefix" if metadata_doc != document else "full_document"

    performers = clean_performers(extract_link_names(metadata_doc, "/models/"))
    studio = extract_studio(metadata_doc, source_name, source_url, source_slug)
    return {
        "performers": performers,
        "studio": studio,
        "metadata_source": metadata_source,
    }


def extract_studio(document: str, default_name: str, default_url: str, default_slug: str) -> dict[str, Any]:
    studios = extract_link_names(document, "/sites/")
    if not studios:
        studios = extract_link_names(document, "/networks/")

    for studio in studios:
        name = studio.get("name")
        if not name:
            continue
        urls = [urljoin(default_url, u) for u in studio.get("urls", []) if isinstance(u, str)]
        return drop_empty({"name": name, "urls": urls or [default_url]})

    return {"name": default_name, "urls": [default_url], "remote_site_id": default_slug}


def extract_video_sources(document: str, base_url: str) -> list[dict[str, object]]:
    streams: list[dict[str, object]] = []
    for match in re.finditer(r"<source\b(?P<attrs>[^>]*)>", document, re.IGNORECASE | re.DOTALL):
        attrs = match.group("attrs")
        src = attr_value(attrs, "src")
        if not src:
            continue
        label = attr_value(attrs, "label") or attr_value(attrs, "res") or "direct"
        streams.append(make_stream(label, "direct", urljoin(base_url, src)))

    for match in re.finditer(r"<video\b(?P<attrs>[^>]*)>", document, re.IGNORECASE | re.DOTALL):
        src = attr_value(match.group("attrs"), "src")
        if src:
            streams.append(make_stream("direct", "direct", urljoin(base_url, src)))

    return streams


def _title_match(document: str, tag: str) -> str | None:
    match = re.search(rf"<{tag}[^>]*>(?P<title>.*?)</{tag}>", document, re.IGNORECASE | re.DOTALL)
    return match.group("title") if match else None


def parse_scene_page(
    document: str,
    page_url: str,
    *,
    source_name: str,
    source_slug: str,
    source_url: str,
) -> dict[str, Any]:
    jsonld_objects = extract_jsonld(document)
    video_obj = first_object(jsonld_objects, "VideoObject")

    canonical_url = absolute_url(page_url, link_href(document, "canonical")) or meta_content(document, "og:url") or page_url
    title = strip_site_suffix(
        first_non_empty(
            meta_content(document, "og:title"),
            video_obj.get("name") if isinstance(video_obj, dict) else None,
            _title_match(document, "title"),
        )
    )

    description = first_non_empty(
        meta_content(document, "og:description"),
        meta_content(document, "description"),
        video_obj.get("description") if isinstance(video_obj, dict) else None,
    )

    image = first_non_empty(
        meta_content(document, "og:image"),
        first_string(video_obj.get("thumbnailUrl")) if isinstance(video_obj, dict) else None,
    )
    if image:
        image = urljoin(canonical_url, image)

    duration_seconds = (
        parse_duration_text(meta_content(document, "video:duration"))
        or parse_iso8601_duration(video_obj.get("duration") if isinstance(video_obj, dict) else None)
    )

    date = normalize_date(
        meta_content(document, "video:release_date")
        or (video_obj.get("uploadDate") if isinstance(video_obj, dict) else None)
    )

    external_id = extract_video_id(document, page_url, canonical_url)
    embed_url = first_non_empty(
        video_obj.get("embedUrl") if isinstance(video_obj, dict) else None,
        f"https://www.1porn.tv/embed/{external_id}" if external_id else None,
    )

    streams = extract_video_sources(document, canonical_url)
    if embed_url:
        streams.append(make_stream("Embed", "embed", urljoin(canonical_url, embed_url)))
    streams = normalize_streams(streams)

    current_card = extract_current_scene_card(document, page_url, canonical_url)
    card_performers = current_card.get("performers") if isinstance(current_card, dict) else None
    card_studio = current_card.get("studio") if isinstance(current_card, dict) else None
    metadata_fallback = extract_scene_metadata_fallback(
        document,
        source_name=source_name,
        source_url=source_url,
        source_slug=source_slug,
    )

    tags = unique_dicts_by_name(extract_meta_tags(document))
    performers = card_performers if isinstance(card_performers, list) and card_performers else metadata_fallback["performers"]
    studio = card_studio if isinstance(card_studio, dict) else metadata_fallback["studio"]

    online_media = drop_empty(
        {
            "source_name": source_name,
            "source_slug": source_slug,
            "external_id": external_id,
            "embed_url": best_embed_url(streams) or embed_url,
            "direct_video_url": best_direct_url(streams),
            "thumbnail_url": image,
            "duration_seconds": duration_seconds,
            "external_view_count": interaction_count(video_obj, "WatchAction") if isinstance(video_obj, dict) else None,
            "streams": streams,
        }
    )
    online_media["raw_metadata_json"] = raw_metadata(
        {
            "source": source_slug,
            "external_id": external_id,
            "canonical_url": canonical_url,
            "stream_count": len(streams),
            "direct_stream_count": sum(1 for stream in streams if stream.get("kind") == "direct"),
            "embed_stream_count": sum(1 for stream in streams if stream.get("kind") == "embed"),
            "jsonld_video_object": bool(video_obj),
            "matched_scene_card": bool(current_card),
            "metadata_fallback_source": metadata_fallback.get("metadata_source"),
        }
    )

    scene = {
        "title": title,
        "urls": unique_strings(canonical_url, page_url),
        "details": description,
        "date": date,
        "image": image,
        "studio": studio,
        "tags": tags,
        "performers": performers,
        "remote_site_id": external_id,
        "duration": duration_seconds,
        "online_media": online_media,
    }
    return drop_empty(scene)


class KVSListParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.items: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None
        self._div_depth = 0
        self._capture_title = False
        self._capture_duration = False
        self._capture_model: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        class_name = attr.get("class", "")

        if tag == "div" and self._current is None and re.search(r"\bitem\b", class_name):
            self._current = {"performers": [], "tags": []}
            self._div_depth = 1
            preview = attr.get("data-preview")
            if preview:
                self._current["preview_url"] = urljoin(self.base_url, preview)
            return

        if self._current is not None and tag == "div":
            self._div_depth += 1
            preview = attr.get("data-preview")
            if preview and "preview_url" not in self._current:
                self._current["preview_url"] = urljoin(self.base_url, preview)

        if self._current is None:
            return

        if tag == "a":
            href = attr.get("href")
            title = attr.get("title")
            if href and "/videos/" in href and "url" not in self._current:
                self._current["url"] = urljoin(self.base_url, href)
                if title:
                    self._current["title"] = clean_text(title)
            elif href and "/models/" in href and _path_has_slug(href, "/models/"):
                self._capture_model = {"kind": "performer", "href": urljoin(self.base_url, href), "parts": []}
            elif href and "/sites/" in href and _path_has_slug(href, "/sites/"):
                self._capture_model = {"kind": "studio", "href": urljoin(self.base_url, href), "parts": []}
            elif href and "/tags/" in href and _path_has_slug(href, "/tags/"):
                self._capture_model = {"kind": "tag", "href": urljoin(self.base_url, href), "parts": []}

        if tag == "img":
            src = attr.get("data-src") or attr.get("src")
            if src and not src.startswith("data:") and "image" not in self._current:
                self._current["image"] = urljoin(self.base_url, src)
            alt = attr.get("alt")
            if alt and "title" not in self._current:
                self._current["title"] = clean_text(alt)

        if tag == "strong" and "title" in class_name:
            self._capture_title = True

        if tag == "span" and "duration" in class_name:
            self._capture_duration = True

    def handle_data(self, data: str) -> None:
        if self._current is None:
            return

        text = clean_text(data)
        if not text:
            return

        if self._capture_title:
            existing = self._current.get("title")
            self._current["title"] = clean_text(f"{existing} {text}" if existing and existing != text else text)

        if self._capture_duration:
            self._current["duration_text"] = clean_text(f"{self._current.get('duration_text', '')} {text}")

        if self._capture_model is not None:
            self._capture_model["parts"].append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._current is None:
            return

        if tag == "strong":
            self._capture_title = False

        if tag == "span":
            self._capture_duration = False

        if tag == "a" and self._capture_model is not None:
            name = clean_text(" ".join(self._capture_model.get("parts", [])))
            href = self._capture_model.get("href")
            kind = self._capture_model.get("kind")
            if name:
                if kind == "performer" and name.lower() not in GENERIC_PERFORMER_LINK_NAMES:
                    self._current.setdefault("performers", []).append({"name": name, "urls": [href]})
                elif kind == "studio" and "studio" not in self._current:
                    self._current["studio"] = {"name": name, "urls": [href]}
                elif kind == "tag":
                    self._current.setdefault("tags", []).append({"name": name})
            self._capture_model = None

        if tag == "div":
            self._div_depth -= 1
            if self._div_depth <= 0:
                self._finish_item()

    def _finish_item(self) -> None:
        if self._current is None:
            return
        if self._current.get("url"):
            self.items.append(dict(self._current))
        self._current = None
        self._div_depth = 0
        self._capture_title = False
        self._capture_duration = False
        self._capture_model = None


def extract_current_scene_card(document: str, page_url: str, canonical_url: str | None) -> dict[str, Any]:
    parser = KVSListParser(canonical_url or page_url)
    parser.feed(document)
    for item in parser.items:
        item_url = item.get("url")
        if isinstance(item_url, str) and (_same_scene_url(item_url, canonical_url) or _same_scene_url(item_url, page_url)):
            return item
    return {}


def parse_source_page(
    document: str,
    page_url: str,
    *,
    source_name: str,
    source_slug: str,
    source_url: str,
) -> dict[str, Any]:
    parser = KVSListParser(page_url)
    parser.feed(document)

    canonical_url = absolute_url(page_url, link_href(document, "canonical")) or page_url
    source_title = strip_site_suffix(first_non_empty(meta_content(document, "og:title"), _title_match(document, "h1"), _title_match(document, "title")))
    thumbnail_url = absolute_url(page_url, meta_content(document, "og:image"))

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, item in enumerate(parser.items):
        url = item.get("url")
        if not isinstance(url, str) or url in seen:
            continue
        seen.add(url)

        duration_seconds = parse_duration_text(item.get("duration_text"))
        candidate = drop_empty(
            {
                "title": item.get("title"),
                "urls": [url],
                "image": item.get("image"),
                "details": item.get("title"),
                "duration": duration_seconds,
                "studio": item.get("studio") or {"name": source_name, "urls": [source_url], "remote_site_id": source_slug},
                "performers": item.get("performers") or [],
                "tags": item.get("tags") or [],
                "remote_site_id": extract_video_id("", url, url),
                "candidate_status": "NEW",
                "candidate_position": position,
                "source_preview": drop_empty(
                    {
                        "preview_url": item.get("preview_url"),
                        "duration_text": item.get("duration_text"),
                    }
                ),
            }
        )
        candidates.append(candidate)

    pagination_urls = extract_pagination_urls(document, page_url)

    return drop_empty(
        {
            "title": source_title,
            "urls": [canonical_url],
            "details": f"{source_name} source scraped from {canonical_url}",
            "source_type": infer_source_type(canonical_url),
            "thumbnail_url": thumbnail_url,
            "remote_site_id": urlparse(canonical_url).path.strip("/") or source_slug,
            "scene_candidates": candidates,
            "pagination_urls": pagination_urls,
            "pages_crawled": 1,
            "candidates_returned": len(candidates),
            "scene_hydration": "preview-only",
        }
    )


def extract_pagination_urls(document: str, base_url: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    pagination_blocks = re.findall(r'<div\b[^>]*class=["\'][^"\']*pagination[^"\']*["\'][^>]*>(.*?)</div>', document, re.IGNORECASE | re.DOTALL)
    body = "\n".join(pagination_blocks) if pagination_blocks else document
    for match in re.finditer(r"<a\b(?P<attrs>[^>]*)>", body, re.IGNORECASE | re.DOTALL):
        href = attr_value(match.group("attrs"), "href")
        if not href:
            continue
        url = urljoin(base_url, href)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def infer_source_type(url: str) -> str:
    path = urlparse(url).path
    if "/search/" in path:
        return "SEARCH"
    if "/models/" in path:
        return "PERFORMER"
    if "/networks/" in path:
        return "NETWORK"
    if "/sites/" in path:
        return "SITE"
    return "SITE_SECTION"
