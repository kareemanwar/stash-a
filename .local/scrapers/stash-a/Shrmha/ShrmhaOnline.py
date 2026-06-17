import html
import json
import re
from http.cookiejar import CookieJar
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

import Shrmha


ORIGINAL_BUILD_ONLINE_MEDIA = Shrmha.build_online_media

UNAVAILABLE_PLAYER_MARKERS = (
    "file is no longer available",
    "expired or has been deleted",
    "file was deleted",
    "file has been deleted",
    "video has been deleted",
    "file not found",
)


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
    return bytes(value, "utf-8").decode("unicode_escape").replace("\/", "/")


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


def is_unavailable_player_document(document: str) -> bool:
    text = re.sub(r"\s+", " ", html.unescape(document)).lower()
    return any(marker in text for marker in UNAVAILABLE_PLAYER_MARKERS)


def fetch_embed_player_document(embed_url: str, page_url: str) -> tuple[str | None, bool]:
    """Return the player document and whether the embed is confirmed dead.

    A network or extraction failure is not the same as a dead server: keep those
    embeds as browser fallbacks. Only hide embeds that explicitly say the file is
    deleted/expired/unavailable.
    """
    parsed = urlparse(embed_url)
    if not parsed.scheme or not parsed.netloc:
        return None, False

    origin = f"{parsed.scheme}://{parsed.netloc}"
    file_code = parsed.path.rstrip("/").split("/")[-1]
    if not file_code:
        return None, False

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
            embed_document = response.read().decode(
                response.headers.get_content_charset() or "utf-8",
                errors="replace",
            )
    except Exception:
        return None, False

    if is_unavailable_player_document(embed_document):
        return None, True

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
            player_document = response.read().decode(charset, errors="replace")
    except Exception:
        return None, False

    if is_unavailable_player_document(player_document):
        return None, True

    return player_document, False


def fetch_text(url: str, referer: str) -> str | None:
    request = Request(
        url,
        headers={
            "User-Agent": Shrmha.USER_AGENT,
            "Referer": referer,
            "Accept": "*/*",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except Exception:
        return None


def parse_hls_max_height(playlist: str) -> int | None:
    heights: list[int] = []
    for match in re.finditer(r"RESOLUTION=\d+x(?P<height>\d+)", playlist, re.IGNORECASE):
        try:
            heights.append(int(match.group("height")))
        except ValueError:
            continue
    return max(heights) if heights else None


def probe_direct_quality(direct_url: str, referer: str) -> int | None:
    if not re.search(r"\.m3u8(?:\?|$)", direct_url, re.IGNORECASE):
        return None

    playlist = fetch_text(direct_url, referer)
    if not playlist:
        return None
    return parse_hls_max_height(playlist)


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


def extract_player_metadata(
    player_document: str,
    base_url: str,
) -> tuple[str | None, int | None, int | None]:
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

    quality_height = probe_direct_quality(direct_url, base_url) if direct_url else None
    return direct_url, duration_seconds, quality_height


def quality_label(label: str | None, height: int | None) -> str:
    base = Shrmha.clean_text(label) or "Direct video"
    if height and f"{height}p" not in base:
        return f"{base} · {height}p"
    return base


def reset_stream_order(streams: list[dict[str, Any]]) -> None:
    for index, stream in enumerate(streams):
        stream["position"] = index
        stream["is_primary"] = index == 0


def enhance_online_media(media: dict[str, Any], page_url: str) -> dict[str, Any]:
    streams = media.get("streams")
    if not isinstance(streams, list):
        return media

    available_direct_streams: list[tuple[int, int, dict[str, Any]]] = []
    available_embed_streams: list[dict[str, Any]] = []
    unavailable_streams: list[dict[str, Any]] = []
    seen_direct_urls: set[str] = set()
    duration_seconds: int | None = media.get("duration_seconds")

    for source_index, stream in enumerate(list(streams)[:8]):
        if not isinstance(stream, dict) or stream.get("kind") != "embed":
            continue

        embed_url = stream.get("url")
        if not isinstance(embed_url, str) or not embed_url:
            continue

        player_document, confirmed_unavailable = fetch_embed_player_document(embed_url, page_url)
        if confirmed_unavailable:
            unavailable_streams.append(stream)
            continue

        # If the server did not explicitly say the file is unavailable, keep it
        # as an iframe fallback even when the direct extraction/probe fails.
        available_embed_streams.append(stream)

        if not player_document:
            continue

        direct_url, parsed_duration, quality_height = extract_player_metadata(player_document, embed_url)
        if parsed_duration and not duration_seconds:
            duration_seconds = parsed_duration

        if not direct_url or direct_url in seen_direct_urls:
            continue
        seen_direct_urls.add(direct_url)

        available_direct_streams.append(
            (
                quality_height or 0,
                source_index,
                {
                    "label": quality_label(stream.get("label"), quality_height),
                    "kind": "direct",
                    "url": direct_url,
                    "position": 0,
                    "is_primary": False,
                },
            )
        )

    if available_direct_streams:
        available_direct_streams.sort(key=lambda item: (-item[0], item[1]))
        direct_streams = [stream for _, _, stream in available_direct_streams]
        fallback_streams = available_embed_streams or [
            stream for stream in streams if isinstance(stream, dict) and stream not in unavailable_streams
        ]
        streams = direct_streams + fallback_streams
        reset_stream_order(streams)
        media["streams"] = streams
        media["direct_video_url"] = direct_streams[0]["url"]
        media["embed_url"] = fallback_streams[0].get("url") if fallback_streams else media.get("embed_url")
    else:
        fallback_streams = available_embed_streams or [
            stream for stream in streams if isinstance(stream, dict) and stream not in unavailable_streams
        ]
        reset_stream_order(fallback_streams)
        media["streams"] = fallback_streams
        media["direct_video_url"] = None
        media["embed_url"] = next(
            (stream.get("url") for stream in fallback_streams if stream.get("kind") == "embed"),
            None,
        )

    if duration_seconds:
        media["duration_seconds"] = duration_seconds

    media["raw_metadata_json"] = json.dumps(
        {
            "source": Shrmha.STUDIO_SLUG,
            "external_id": media.get("external_id"),
            "direct_video_url": media.get("direct_video_url"),
            "duration_seconds": media.get("duration_seconds"),
            "streams": media.get("streams"),
            "unavailable_streams": unavailable_streams,
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
