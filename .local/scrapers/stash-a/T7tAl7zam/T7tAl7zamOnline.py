import re
import sys
from pathlib import Path
from typing import Any

import T7tAl7zam

sys.path.append(str(Path(__file__).resolve().parents[1]))

from _shared.online_hosts import enhance_online_media, html_label, remove_internal_online_media_fields


ORIGINAL_BUILD_ONLINE_MEDIA = T7tAl7zam.build_online_media


def extract_embed_streams(document: str, parser: T7tAl7zam.PageParser, base_url: str) -> list[dict[str, Any]]:
    streams: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Shrmha server selectors are not always <button> elements. Capture any
    # element that calls go('embed-url') and use its visible text as the label.
    go_pattern = re.compile(
        r"<(?P<tag>[a-zA-Z0-9]+)\b(?P<attrs>[^>]*)\bonclick=[\"'][^\"']*\bgo\((?P<quote>[\"'])(?P<url>.*?)(?P=quote)\)[^\"']*[\"'][^>]*>(?P<label>.*?)</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in go_pattern.finditer(document):
        T7tAl7zam.append_stream(
            streams,
            seen,
            url=match.group("url"),
            label=html_label(match.group("label"), T7tAl7zam.clean_text),
            kind="embed",
            base_url=base_url,
        )

    # Some templates keep embed URLs in data attributes or direct links instead
    # of onclick handlers. Restrict to player/embed-looking paths to avoid
    # collecting the source article URL or thumbnails.
    data_pattern = re.compile(
        r"\b(?:data-(?:src|url|embed)|href|src)=[\"'](?P<url>https?://[^\"']+(?:/(?:e|embed|iframe|player)/[^\"']+|/embed-[^\"'/]+\.html(?:\?[^\"']*)?))[\"']",
        re.IGNORECASE,
    )
    for match in data_pattern.finditer(document):
        T7tAl7zam.append_stream(
            streams,
            seen,
            url=match.group("url"),
            label="Embed" if streams else "Primary embed",
            kind="embed",
            base_url=base_url,
        )

    for iframe_url in parser.iframes:
        T7tAl7zam.append_stream(
            streams,
            seen,
            url=iframe_url,
            label="Primary embed" if not streams else "Embed",
            kind="embed",
            base_url=base_url,
        )

    return streams


def build_online_media(*args: Any, **kwargs: Any) -> dict[str, Any]:
    media = ORIGINAL_BUILD_ONLINE_MEDIA(*args, **kwargs)
    page_url = kwargs.get("url")
    if isinstance(page_url, str):
        media = enhance_online_media(
            media,
            page_url,
            user_agent=T7tAl7zam.USER_AGENT,
            source_slug=T7tAl7zam.STUDIO_SLUG,
            clean_text=T7tAl7zam.clean_text,
        )

    return remove_internal_online_media_fields(media)


T7tAl7zam.extract_embed_streams = extract_embed_streams
T7tAl7zam.build_online_media = build_online_media
T7tAl7zam.main()
