import html
import json
import re
from http.cookiejar import CookieJar
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

import Shrmha


ORIGINAL_BUILD_ONLINE_MEDIA = Shrmha.build_online_media


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


def js_string(value: str) -> str:
    return bytes(value, "utf-8").decode("unicode_escape").replace("\\/", "/")


def base_n(value: int, radix: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    result = ""
    while value:
        value, remainder = divmod(value, radix)
        result = digits[remainder] + result
    return result


def unpack_packed_scripts(document: str) -> list[str]:
    unpacked: list[str] = []
    packed_pattern = re.compile(
        r"eval\(function\(p,a,c,k,e,d\).*?\}\('(?P<p>(?:\\.|[^\\'])*)',(?P<a>\d+),(?P<c>\d+),'(?P<k>(?:\\.|[^\\'])*)'\.split\('\|'\)\)\)",
        re.IGNORECASE | re.DOTALL,
    )

    for match in packed_pattern.finditer(document):
        payload = js_string(match.group("p"))
        radix = int(match.group("a"))
        count = int(match.group("c"))
        keywords = js_string(match.group("k")).split("|")

        for index in range(count - 1, -1, -1):
            if index >= len(keywords) or not keywords[index]:
                continue
            token = base_n(index, radix)
            payload = re.sub(rf"\b{re.escape(token)}\b", keywords[index], payload)

        unpacked.append(payload)

    return unpacked


def fetch_embed_player_document(embed_url: str, page_url: str) -> str | None:
    parsed = urlparse(embed_url)
    if not parsed.scheme or not parsed.netloc:
        return None

    origin = f"{parsed.scheme}://{parsed.netloc}"
    file_code = parsed.path.rstrip("/").split("/")[-1]
    if not file_code:
        return None

    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    get_request = Request(
        embed_url,
        headers={
            "User-Agent": Shrmha.USER_AGENT,
            "Referer": page_url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with opener.open(get_request, timeout=30) as response:
            response.read()
    except Exception:
        return None

    data = urlencode(
        {
            "op": "embed",
            "file_code": file_code,
            "auto": "1",
            "referer": page_url,
        }
    ).encode("utf-8")

    post_request = Request(
        urljoin(origin, "/dl"),
        data=data,
        headers={
            "User-Agent": Shrmha.USER_AGENT,
            "Referer": embed_url,
            "Origin": origin,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method="POST",
    )

    try:
        with opener.open(post_request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except Exception:
        return None


def parse_seconds(value: str) -> int | None:
    value = value.strip().strip('"\'')
    if not value:
        return None

    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        seconds = round(float(value))
        return seconds if seconds > 5 else None

    time_match = re.fullmatch(r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})", value)
    if time_match:
        hours = int(time_match.group(1) or 0)
        minutes = int(time_match.group(2))
        seconds = int(time_match.group(3))
        total = hours * 3600 + minutes * 60 + seconds
        return total if total > 5 else None

    return None


def extract_player_metadata(player_document: str, base_url: str) -> tuple[str | None, int | None]:
    documents = [player_document]
    documents.extend(unpack_packed_scripts(player_document))
    joined = "\n".join(html.unescape(doc) for doc in documents)

    direct_url: str | None = None
    direct_patterns = [
        r"https?://[^\"'<>\\\s]+?\.(?:mp4|m3u8)(?:\?[^\"'<>\\\s]*)?",
        r"[\"']file[\"']\s*:\s*[\"']([^\"']+)[\"']",
        r"[\"']src[\"']\s*:\s*[\"']([^\"']+)[\"']",
        r"<source\b[^>]+src=[\"']([^\"']+)[\"']",
    ]
    for pattern in direct_patterns:
        for match in re.finditer(pattern, joined, re.IGNORECASE):
            candidate = match.group(1) if match.groups() else match.group(0)
            if re.search(r"\.(?:mp4|m3u8)(?:\?|$)", candidate, re.IGNORECASE):
                direct_url = urljoin(base_url, candidate)
                break
        if direct_url:
            break

    duration_seconds: int | None = None
    duration_patterns = [
        r"[\"']duration[\"']\s*:\s*[\"']?([^,\"'\}\]\s]+)",
        r"\bduration\s*[:=]\s*[\"']?([^,\"'\}\]\s]+)",
        r"[\"']length[\"']\s*:\s*[\"']?([^,\"'\}\]\s]+)",
        r"(\d{1,2}:\d{2}(?::\d{2})?)",
    ]
    for pattern in duration_patterns:
        for match in re.finditer(pattern, joined, re.IGNORECASE):
            parsed = parse_seconds(match.group(1))
            if parsed:
                duration_seconds = parsed
                break
        if duration_seconds:
            break

    return direct_url, duration_seconds


def enhance_online_media(media: dict[str, Any], page_url: str) -> dict[str, Any]:
    streams = media.get("streams")
    if not isinstance(streams, list):
        return media

    seen = {stream.get("url") for stream in streams if isinstance(stream, dict)}
    for stream in list(streams)[:5]:
        if not isinstance(stream, dict) or stream.get("kind") != "embed":
            continue

        embed_url = stream.get("url")
        if not isinstance(embed_url, str) or not embed_url:
            continue

        player_document = fetch_embed_player_document(embed_url, page_url)
        if not player_document:
            continue

        direct_url, duration_seconds = extract_player_metadata(player_document, embed_url)
        if direct_url and not media.get("direct_video_url"):
            before = len(streams)
            Shrmha.append_stream(
                streams,
                seen,
                url=direct_url,
                label="Direct video",
                kind="direct",
                base_url=embed_url,
            )
            if len(streams) > before:
                media["direct_video_url"] = streams[-1]["url"]

        if duration_seconds and not media.get("duration_seconds"):
            media["duration_seconds"] = duration_seconds

        if media.get("direct_video_url") and media.get("duration_seconds"):
            break

    media["raw_metadata_json"] = json.dumps(
        {
            "source": Shrmha.STUDIO_SLUG,
            "external_id": media.get("external_id"),
            "direct_video_url": media.get("direct_video_url"),
            "duration_seconds": media.get("duration_seconds"),
            "streams": streams,
        },
        ensure_ascii=True,
    )
    return media


def build_online_media(*args: Any, **kwargs: Any) -> dict[str, Any]:
    media = ORIGINAL_BUILD_ONLINE_MEDIA(*args, **kwargs)
    page_url = kwargs.get("url") or media.get("page_url")
    if isinstance(page_url, str):
        return enhance_online_media(media, page_url)
    return media


Shrmha.extract_embed_streams = extract_embed_streams
Shrmha.build_online_media = build_online_media
Shrmha.main()
