import re
from typing import Any

import Shrmha


def html_label(value: str | None) -> str | None:
    if not value:
        return None
    label = re.sub(r"<[^>]+>", " ", value)
    return Shrmha.clean_text(label) or None


def extract_embed_streams(document: str, parser: Shrmha.PageParser, base_url: str) -> list[dict[str, Any]]:
    streams: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Shrmha server selectors are not always <button> elements. Capture any
    # element that calls go('embed-url') and use its visible text as the label.
    go_pattern = re.compile(
        r"<(?P<tag>[a-zA-Z0-9]+)\b(?P<attrs>[^>]*)\bonclick=[\"'][^\"']*\bgo\((?P<quote>[\"'])(?P<url>.*?)(?P=quote)\)[^\"']*[\"'][^>]*>(?P<label>.*?)</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in go_pattern.finditer(document):
        Shrmha.append_stream(
            streams,
            seen,
            url=match.group("url"),
            label=html_label(match.group("label")),
            kind="embed",
            base_url=base_url,
        )

    # Some templates keep embed URLs in data attributes or direct links instead
    # of onclick handlers. Restrict to player/embed-looking paths to avoid
    # collecting the source article URL or thumbnails.
    data_pattern = re.compile(
        r"\b(?:data-(?:src|url|embed)|href|src)=[\"'](?P<url>https?://[^\"']+/(?:e|embed|iframe|player)/[^\"']+)[\"']",
        re.IGNORECASE,
    )
    for match in data_pattern.finditer(document):
        Shrmha.append_stream(
            streams,
            seen,
            url=match.group("url"),
            label="Embed" if streams else "Primary embed",
            kind="embed",
            base_url=base_url,
        )

    for iframe_url in parser.iframes:
        Shrmha.append_stream(
            streams,
            seen,
            url=iframe_url,
            label="Primary embed" if not streams else "Embed",
            kind="embed",
            base_url=base_url,
        )

    return streams


Shrmha.extract_embed_streams = extract_embed_streams
Shrmha.main()
